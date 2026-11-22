#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored bounded ESP-AT BLE API, 2026-11-14.
"""ESP-AT BLE control. UART1 only; no GPIO, firmware, Wi-Fi-mode or HCI changes.

JSON output is redacted. No automatic pairing, scanning-to-connect, or arbitrary
AT command facility. An owned peer must be provided explicitly for connections.
"""
import argparse
import collections
import csv
import fcntl
import glob
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import termios
import time

MAC=re.compile(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}')
class ProtocolError(RuntimeError): pass
class ATError(RuntimeError): pass


def redact(line):
    if line.startswith(('+BLESCAN:', '+BLENAME:', '+BLEENCDEV:', '+BLEKEY', '+BLEAUTH', '+BLESEC', '+BLESETKEY:', '+BLEADVDATA', '+BLESCANRSPDATA')):
        return line.split(':',1)[0]+':<private>'
    return MAC.sub('<address>',line)


class Framer:
    """CRLF lines, prompt and documented length-prefixed binary replies.

    Binary data containing CRLF/OK cannot complete an AT transaction. Unknown
    binary layouts are not guessed. Buffer and frame lengths are bounded.
    """
    binary=[
      re.compile(rb'^\+BLEGATTCRD:(\d+),(\d+),'),
      re.compile(rb'^\+(?:BLEGATTCNOTIFY|BLEGATTCIND|NOTIFY|INDICATE):\d+,\d+,\d+,(\d+),'),
      re.compile(rb'^\+WRITE:\d+,\d+,\d+,\d*,(\d+),')]
    prefixes=(b'+BLEGATTCRD:',b'+BLEGATTCNOTIFY:',b'+BLEGATTCIND:',b'+NOTIFY:',b'+INDICATE:',b'+WRITE:')
    def __init__(self, limit=16384): self.buffer=bytearray();self.limit=limit
    def feed(self,data):
        self.buffer.extend(data)
        if len(self.buffer)>self.limit: raise ProtocolError('UART buffer limit')
        result=[]
        while self.buffer:
            if self.buffer.startswith(b'\r\n'):del self.buffer[:2];continue
            if self.buffer.startswith(b'>'):
                del self.buffer[:1];result.append(('prompt',b'>'));continue
            binary=False
            for rx in self.binary:
                m=rx.match(self.buffer)
                if not m:continue
                length=int(m.group(m.lastindex))
                if length>self.limit//2:raise ProtocolError('binary frame length limit')
                binary=True
                end=m.end()+length
                if len(self.buffer)<end:return result
                result.append(('binary',bytes(self.buffer[:end])));del self.buffer[:end];break
            if binary:continue
            end=self.buffer.find(b'\r\n')
            if end<0:break
            line=bytes(self.buffer[:end]);del self.buffer[:end+2]
            if line.startswith(self.prefixes):raise ProtocolError('unsupported binary header')
            result.append(('line',line))
        return result


def ad_types(text):
    """Only AD type/length metadata; never names, manufacturer bytes or UUIDs."""
    if not re.fullmatch('[0-9a-fA-F]*',text) or len(text)%2: return None
    data=bytes.fromhex(text);pos=0;types=[]
    while pos<len(data):
        size=data[pos]
        if not size:break
        if pos+size>=len(data):return None
        types.append(data[pos+1]);pos+=size+1
    return types


class ScanStats:
    def __init__(self):
        self.count=0;self.addresses=set();self.rssi=[];self.types=collections.Counter();self.malformed=0;self.shapes=collections.Counter()
    def add(self,line):
        fields=next(csv.reader([line.removeprefix('+BLESCAN:')],skipinitialspace=True))
        fields=[x.strip() for x in fields]
        if len(fields)!=5 or not MAC.fullmatch(fields[0]):self.malformed+=1;return
        try:rssi=int(fields[1]);kind=int(fields[4])
        except ValueError:self.malformed+=1;return
        if not -127<=rssi<=20 or not 0<=kind<=3:self.malformed+=1;return
        self.count+=1;self.addresses.add(fields[0].lower());self.rssi.append(rssi)
        for field in fields[2:4]:
            types=ad_types(field)
            if types is None:self.malformed+=1
            else:self.types.update(types)
    def summary(self):
        return dict(reports=self.count,unique_addresses=len(self.addresses),malformed=self.malformed,
          rssi_min=min(self.rssi) if self.rssi else None,rssi_max=max(self.rssi) if self.rssi else None,
          ad_type_counts={f'0x{k:02x}':v for k,v in sorted(self.types.items())})


def uart_owners(device):
    target=os.stat(device).st_rdev;owners=[]
    for proc in glob.glob('/proc/[0-9]*'):
        for fd in glob.glob(proc+'/fd/*'):
            try:
                st=os.stat(fd)
                if stat.S_ISCHR(st.st_mode) and st.st_rdev==target:
                    owners.append(int(Path(proc).name));break
            except OSError:pass
    return owners


class UART:
    def __init__(self,device='/dev/ttyS1'):self.device=device;self.fd=None;self.lock=None
    def __enter__(self):
        if self.device!='/dev/ttyS1' or os.path.realpath(self.device)!=self.device:
            raise ProtocolError('Only the known UART1 device is allowed')
        if any(x.split()[0]=='ttyS1' for x in Path('/proc/consoles').read_text().splitlines() if x.split()):
            raise ProtocolError('UART1 is a console')
        self.lock=open('/run/lock/terminal6-esp32-query.lock','a')
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if uart_owners(self.device):raise ProtocolError('UART already in use')
            self.fd=os.open(self.device,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
            self.before=termios.tcgetattr(self.fd);fcntl.ioctl(self.fd,termios.TIOCEXCL)
            if any(p!=os.getpid() for p in uart_owners(self.device)):raise ProtocolError('UART ownership race')
            attrs=termios.tcgetattr(self.fd);attrs[0]=attrs[1]=attrs[3]=0
            attrs[2]=(attrs[2]&~(termios.CSIZE|termios.PARENB|termios.CSTOPB|termios.CRTSCTS))|termios.CS8|termios.CLOCAL|termios.CREAD
            attrs[4]=attrs[5]=termios.B115200;attrs[6][termios.VMIN]=attrs[6][termios.VTIME]=0
            termios.tcsetattr(self.fd,termios.TCSANOW,attrs)
            return self
        except BaseException:
            self.__exit__(None,None,None);raise
    def __exit__(self,*args):
        if self.fd is not None:
            try:
                if hasattr(self,'before'):termios.tcsetattr(self.fd,termios.TCSANOW,self.before)
                fcntl.ioctl(self.fd,termios.TIOCNXCL)
            finally:os.close(self.fd);self.fd=None
        if self.lock:self.lock.close();self.lock=None


class AT:
    def __init__(self,fd,emit=None):
        self.fd=fd;self.framer=Framer();self.pending=collections.deque();self._sink=emit or (lambda x:None)
        self.scan=ScanStats();self.connections=set();self.role=None;self.tainted=False;self.byte_count=0;self.binary_events=[];self.expected_peer=None;self.mtu={};self.expected_restart=False;self.restart_seen=False
    def emit(self,obj):
        try:self._sink(obj)
        except (BrokenPipeError,OSError):pass  # Logging loss must not prevent cleanup.
    def read(self,seconds):
        if select.select([self.fd],[],[],max(0,seconds))[0]:
            data=os.read(self.fd,2048)
            if not data:raise ProtocolError('UART EOF')
            self.byte_count+=len(data)
            if self.byte_count>262144:raise ProtocolError('session byte limit')
            return self.framer.feed(data)
        return []
    def event(self,kind,raw):
        if kind=='binary':
            self.binary_events.append(raw)
            if len(self.binary_events)>128:raise ProtocolError('binary event count limit')
            prefix=raw.split(b':',1)[0].decode('ascii')
            self.emit({'event':'binary','type':prefix,'frame_bytes':len(raw),'contents':'private'});return
        line=raw.decode('utf-8',errors='backslashreplace').strip('\r\n')
        if line.startswith('+BLESCAN:'):self.scan.add(line);return
        if line.startswith('+BLECFGMTU:'):
            try:
                index,size=map(int,line.split(':',1)[1].split(','))
                if not 23<=size<=517:raise ValueError()
                self.mtu[index]=size
            except ValueError:raise ProtocolError('bad MTU event')
        if line=='ready':
            if self.expected_restart:
                self.expected_restart=False;self.restart_seen=True;self.connections.clear();self.role=0;self.emit({'restart':'expected'});return
            self.tainted=True;raise ProtocolError('unexpected ESP restart')
        if line.startswith('+BLECONN:'):
            fields=line.split(':',1)[1].split(',')
            address=MAC.search(line)
            if self.expected_peer and (not address or address.group(0).lower()!=self.expected_peer):
                raise ProtocolError('unexpected peer connection')
            try:self.connections.add(int(fields[0]))
            except ValueError:raise ProtocolError('bad connection event')
        if line.startswith('+BLEDISCONN:'):
            try:self.connections.discard(int(line.split(':',1)[1].split(',')[0]))
            except ValueError:raise ProtocolError('bad disconnect event')
        self.emit({'event':'line','line':redact(line)})
    def idle(self,duration):
        end=time.monotonic()+duration
        while time.monotonic()<end:
            for kind,raw in self.read(min(0.1,end-time.monotonic())):self.event(kind,raw)
    def reset_volatile(self,explicit=False):
        if not explicit:raise ValueError('Software restart requires explicit caller authorization')
        if self.command('AT+BLEINIT?')['lines']!=['+BLEINIT:0']:
            raise ProtocolError('Stop BLE before a software restart')
        self.expected_restart=True;self.restart_seen=False
        try:self.command('AT+RST')
        except BaseException:
            self.expected_restart=False;raise
        end=time.monotonic()+6
        while not self.restart_seen and time.monotonic()<end:self.idle(.1)
        if not self.restart_seen:self.tainted=True;raise ProtocolError('restart readiness not observed')
        return self.command('AT+GMR')
    def command(self,command,timeout=3,payload=None,wait_event=None,quiet=False):
        if self.tainted:raise ProtocolError('session tainted; refusing command')
        if payload is not None and (not isinstance(payload,bytes) or not 1<=len(payload)<=512):raise ValueError('payload must be 1..512 bytes')
        if '\r' in command or '\n' in command or not command.isascii():raise ProtocolError('invalid command bytes')
        self.emit({'command':redact(command),'payload_bytes':len(payload) if payload is not None else 0})
        end=time.monotonic()+timeout;start=time.monotonic();total=0;lines=[];ok=False;event_seen=wait_event is None;sent=False
        data=(command+'\r\n').encode();offset=0
        while offset<len(data):
            if time.monotonic()>end:raise ProtocolError('command write timeout')
            if select.select([],[self.fd],[],0.1)[1]:offset+=os.write(self.fd,data[offset:])
        try:
            while time.monotonic()<end:
                for kind,raw in self.read(min(0.1,end-time.monotonic())):
                    total+=len(raw)
                    if total>65536:raise ProtocolError('transaction response limit')
                    if kind=='prompt':
                        if payload is None or sent:raise ProtocolError('unexpected data prompt')
                        sent=True;pos=0
                        while pos<len(payload):
                            if time.monotonic()>end:raise ProtocolError('payload write timeout')
                            if select.select([],[self.fd],[],0.1)[1]:pos+=os.write(self.fd,payload[pos:])
                        continue
                    if kind=='binary':self.event(kind,raw);continue
                    line=raw.decode('utf-8',errors='backslashreplace').strip('\r\n')
                    if not line or line==command:continue
                    if command=='AT+BLECONN?' and line=='+BLECONN:':
                        lines.append(line);self.emit({'reply':line,'connections':0});continue
                    if line=='ERROR' or line.startswith(('+CME ERROR','ERR CODE:')):
                        self.emit({'result':'ERROR'});raise ATError('command rejected')
                    if line=='OK':ok=True;continue
                    if wait_event and line.startswith(wait_event):event_seen=True
                    if line.startswith('+BLECONNPARAM:') and not command.startswith('AT+BLECONNPARAM'):
                        self.event(kind,raw);continue
                    if line.startswith('+BLECFGMTU:') and not command.startswith('AT+BLECFGMTU'):
                        self.event(kind,raw);continue
                    if line=='+BLESCANDONE':self.event(kind,raw);continue
                    if line.startswith('+BLESCAN:') or line.startswith(('+BLECONN:','+BLEDISCONN:')) or line=='ready':
                        self.event(kind,raw)
                    else:
                        lines.append(line)
                        if not quiet:self.emit({'reply':redact(line)})
                if ok and event_seen and (payload is None or sent):
                    result={'ok':True,'seconds':round(time.monotonic()-start,3),'lines':lines}
                    self.emit({'result':'OK','seconds':result['seconds']});return result
            self.tainted=True;raise ProtocolError('local timeout; remote completion unknown')
        except (ProtocolError,OSError,KeyboardInterrupt):self.tainted=True;raise


class BLE:
    def __init__(self,at):self.at=at;self.owned=False;self.scanning=False;self.advertising=False
    def status(self,catalog=False):
        result={}
        for cmd in ['AT','AT+GMR','AT+CWMODE?','AT+BLEINIT?','AT+SYSRAM?','AT+SYSSTORE?']:
            result[cmd]=self.at.command(cmd)
        if catalog:result['AT+CMD?']=self.at.command('AT+CMD?',timeout=5)
        return result
    def init(self,role):
        if role not in [1,2]:raise ValueError('role must be 1 or 2')
        before=self.at.command('AT+BLEINIT?')['lines']
        if before!=['+BLEINIT:0']:raise ProtocolError('Refusing to adopt an existing BLE session')
        self.at.command(f'AT+BLEINIT={role}',timeout=6);self.owned=True
        after=self.at.command('AT+BLEINIT?')['lines']
        if after!=[f'+BLEINIT:{role}']:raise ProtocolError('role readback mismatch')
        self.at.role=role
    def scan(self,seconds=3):
        if not 1<=seconds<=5:raise ValueError('scan duration must be 1..5 seconds')
        if not self.owned:raise ProtocolError('BLE not owned')
        self.at.command('AT+BLESCANPARAM=0,0,0,100,50')
        self.scanning=True
        self.at.command(f'AT+BLESCAN=1,{seconds}',timeout=seconds+3)
        self.at.idle(seconds+0.25)
        self.at.command('AT+BLESCAN=0');self.scanning=False
        self.at.emit({'scan_summary':self.at.scan.summary()})
        return self.at.scan.summary()
    def advertise(self,seconds=3):
        if not 1<=seconds<=5:raise ValueError('advertising duration must be 1..5 seconds')
        if not self.owned:raise ProtocolError('BLE not owned')
        # Nonconnectable undirected legacy advertising: unknown peers cannot connect.
        name=b'T6-BLE-LAB';data=b'\x02\x01\x06'+bytes([len(name)+1,9])+name
        self.at.command('AT+BLEADVPARAM=160,160,3,0,7,0')
        self.at.command('AT+BLEADVDATA="'+data.hex()+'"')
        self.at.command('AT+BLEADVSTART');self.advertising=True
        self.at.idle(seconds)
        self.at.command('AT+BLEADVSTOP');self.advertising=False
    def server(self):
        if not self.owned:raise ProtocolError('BLE not owned')
        for cmd in ['AT+BLEGATTSSRVCRE','AT+BLEGATTSSRVSTART','AT+BLEGATTSSRV?','AT+BLEGATTSCHAR?']:
            self.at.command(cmd)
    def connect(self,peer,owned_peer=False,index=0):
        if not owned_peer or not MAC.fullmatch(peer):raise ValueError('Explicit owned peer required')
        if not self.owned:raise ProtocolError('BLE not owned')
        self.at.expected_peer=peer.lower()
        self.at.command(f'AT+BLECONN={index},"{peer}"',timeout=33,wait_event=f'+BLECONN:{index},')
        if index not in self.at.connections:raise ProtocolError('no connection completion')
    def disconnect(self,index=0):
        if index not in self.at.connections:raise ProtocolError('unknown connection index')
        self.at.command(f'AT+BLEDISCONN={index}',timeout=8,wait_event=f'+BLEDISCONN:{index}')
    def discover(self,index=0,service=None):
        self._connected(index)
        if service is None:return self.at.command(f'AT+BLEGATTCPRIMSRV={index}',timeout=8)
        self._indices(service,1)
        return self.at.command(f'AT+BLEGATTCCHAR={index},{service}',timeout=8)
    @staticmethod
    def _indices(service,char,descriptor=None):
        if not 1<=service<=32 or not 1<=char<=64 or (descriptor is not None and not 1<=descriptor<=16):raise ValueError('attribute index bounds')
    def _connected(self,index):
        if index not in self.at.connections:raise ProtocolError('connection not established')
    def resolve(self,index,service_uuid,char_uuid):
        def normalize(value):
            value=value.lower().removeprefix('0x').replace('-','')
            if len(value) not in [4,8,32] or not re.fullmatch('[0-9a-f]+',value):raise ValueError('invalid UUID')
            return value
        wanted_service,wanted_char=normalize(service_uuid),normalize(char_uuid)
        matches=[]
        for line in self.discover(index)['lines']:
            if not line.startswith('+BLEGATTCPRIMSRV:'):continue
            fields=next(csv.reader([line.split(':',1)[1]]))
            if len(fields)==4 and normalize(fields[2])==wanted_service:matches.append(int(fields[1]))
        if len(matches)!=1:raise ProtocolError('service UUID missing or ambiguous')
        service=matches[0];matches=[]
        for line in self.discover(index,service)['lines']:
            if not line.startswith('+BLEGATTCCHAR:'):continue
            fields=next(csv.reader([line.split(':',1)[1]]))
            if len(fields)==6 and fields[0]=='char' and normalize(fields[4])==wanted_char:matches.append(int(fields[3]))
        if len(matches)!=1:raise ProtocolError('characteristic UUID missing or ambiguous')
        return service,matches[0]
    def read(self,index,service,char,descriptor=None):
        self._connected(index);self._indices(service,char,descriptor)
        suffix='' if descriptor is None else ','+str(descriptor)
        before=len(self.at.binary_events)
        self.at.command(f'AT+BLEGATTCRD={index},{service},{char}{suffix}',timeout=8)
        frames=self.at.binary_events[before:]
        replies=[x for x in frames if x.startswith(b'+BLEGATTCRD:')]
        if len(replies)!=1:raise ProtocolError('missing or ambiguous GATT read response')
        header=Framer.binary[0].match(replies[0]);return replies[0][header.end():]
    def write(self,index,service,char,value,descriptor=None):
        self._connected(index);self._indices(service,char,descriptor)
        desc='' if descriptor is None else str(descriptor)
        self.at.command(f'AT+BLEGATTCWR={index},{service},{char},{desc},{len(value)}',timeout=8,payload=value)
    def subscribe(self,index,service,char,descriptor=1,indicate=False):
        self.write(index,service,char,b'\x02\x00' if indicate else b'\x01\x00',descriptor)
    def unsubscribe(self,index,service,char,descriptor=1):
        self.write(index,service,char,b'\x00\x00',descriptor)
    def set_mtu(self,index,size):
        self._connected(index)
        if not 23<=size<=517:raise ValueError('MTU bounds')
        self.at.command(f'AT+BLECFGMTU={index},{size}')
        return self.at.command('AT+BLECFGMTU?')  # Readback, not the requested size, is authoritative.
    def encrypt(self,index,allow_pairing=False):
        self._connected(index)
        if not allow_pairing or not self.at.expected_peer:raise ValueError('Explicit owned-peer pairing policy required')
        return self.at.command(f'AT+BLEENC={index},1',timeout=15,wait_event=f'+BLEAUTHCMPL:{index},')
    def set_local(self,service,char,value,descriptor=None):
        if not self.owned:raise ProtocolError('BLE not owned')
        self._indices(service,char,descriptor);desc='' if descriptor is None else str(descriptor)
        self.at.command(f'AT+BLEGATTSSETATTR={service},{char},{desc},{len(value)}',payload=value)
    def notify(self,index,service,char,value,indicate=False):
        self._connected(index);self._indices(service,char)
        cmd='BLEGATTSIND' if indicate else 'BLEGATTSNTFY'
        self.at.command(f'AT+{cmd}={index},{service},{char},{len(value)}',timeout=8,payload=value)
    def close(self):
        if not self.owned:return
        if self.at.tainted:
            self.at.emit({'cleanup':'BLOCKED','reason':'UART synchronization unknown; radio state must be checked'});return
        failures=[]
        for cmd in (['AT+BLESCAN=0'] if self.scanning else [])+(['AT+BLEADVSTOP'] if self.advertising else []):
            try:self.at.command(cmd)
            except ATError:failures.append(cmd)
        for index in list(self.at.connections):
            try:self.disconnect(index)
            except ATError:failures.append('disconnect rejected')
        self.at.command('AT+BLEINIT=0',timeout=6)
        state=self.at.command('AT+BLEINIT?')['lines']
        if state!=['+BLEINIT:0']:raise ProtocolError('deinit verification failed')
        self.owned=False;self.at.role=0;self.at.connections.clear()
        self.at.emit({'cleanup':'VERIFIED','ble_role':0,'stop_commands_rejected':len(failures)})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['status','catalog','scan','advertise','server','connect','gatt-read','gatt-write','gatt-watch'])
    p.add_argument('--seconds',type=int,default=3,choices=range(1,6))
    p.add_argument('--peer');p.add_argument('--owned-peer',action='store_true')
    p.add_argument('--service-uuid');p.add_argument('--char-uuid')
    p.add_argument('--data-hex');p.add_argument('--include-data',action='store_true',help='Private output: never publish')
    a=p.parse_args()
    if a.action in ['connect','gatt-read','gatt-write','gatt-watch'] and (not a.peer or not a.owned_peer):p.error('connect requires --peer and --owned-peer')
    if a.action.startswith('gatt-') and (not a.service_uuid or not a.char_uuid):p.error('GATT operations require service and characteristic UUIDs')
    if a.action=='gatt-write' and (not a.data_hex or not re.fullmatch(r'(?:[0-9a-fA-F]{2}){1,512}',a.data_hex)):p.error('write requires 1..512 bytes of hex data')
    def emit(obj):print(json.dumps(obj,ensure_ascii=True),flush=True)
    def interrupt(signum,frame):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGHUP,interrupt)
    try:
        with UART() as uart:
            at=AT(uart.fd,emit);at.idle(0.15);ble=BLE(at)
            try:
                ble.status(catalog=a.action=='catalog')
                if a.action in ['status','catalog']:return
                ble.init(1 if a.action in ['scan','connect','gatt-read','gatt-write','gatt-watch'] else 2)
                if a.action=='scan':ble.scan(a.seconds)
                elif a.action=='advertise':ble.advertise(a.seconds)
                elif a.action=='server':ble.server()
                elif a.action in ['connect','gatt-read','gatt-write','gatt-watch']:
                    ble.connect(a.peer,a.owned_peer)
                    if a.action=='connect':ble.discover()
                    else:
                        service,char=ble.resolve(0,a.service_uuid,a.char_uuid)
                        if a.action=='gatt-read':
                            value=ble.read(0,service,char)
                            emit({'value_bytes':len(value),'value_hex':value.hex() if a.include_data else '<private>'})
                        elif a.action=='gatt-write':ble.write(0,service,char,bytes.fromhex(a.data_hex))
                        else:
                            ble.subscribe(0,service,char);at.idle(a.seconds);ble.unsubscribe(0,service,char)
                    ble.disconnect()
            finally:ble.close()
    except (OSError,ATError,ProtocolError,KeyboardInterrupt,ValueError) as e:
        emit({'error':type(e).__name__,'message':redact(str(e)),'hardware_success':False});raise SystemExit(1)


if __name__=='__main__':main()
