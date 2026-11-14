#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored bounded ESP-AT query client, 2026-11-14.
"""Query the owner's known UART1 ESP-AT transport without resetting/enabling RF.

Run only after confirming the board wiring and UART1 ownership. Responses are
private until reviewed. Does not support arbitrary AT commands or HCI attach.
"""
import argparse
import fcntl
import glob
import json
import os
from pathlib import Path
import select
import stat
import termios
import time

ALLOWED=('AT','AT+GMR','AT+CWMODE?','AT+BLEINIT?')


def owners(device):
    target=os.stat(device)
    result=[]
    for proc in glob.glob('/proc/[0-9]*'):
        for fd in glob.glob(proc+'/fd/*'):
            try:
                entry=os.stat(fd)
                if stat.S_ISCHR(entry.st_mode) and entry.st_rdev==target.st_rdev:
                    result.append(int(Path(proc).name));break
            except OSError:pass
    return result


def query(fd,command,timeout=2.0,limit=4096):
    if command not in ALLOWED: raise ValueError('command outside read-only allowlist')
    start=time.monotonic();os.write(fd,(command+'\r\n').encode('ascii'));out=bytearray()
    complete=False
    while time.monotonic()-start<timeout:
        if select.select([fd],[],[],min(0.1,max(0,timeout-(time.monotonic()-start))))[0]:
            block=os.read(fd,min(512,limit-len(out)))
            if not block:continue
            out.extend(block)
            if b'\r\nOK\r\n' in out or b'\r\nERROR\r\n' in out:
                complete=True;break
            if len(out)>=limit:break
    return {'command':command,'seconds':round(time.monotonic()-start,3),
            'complete':complete,'limit_reached':len(out)>=limit,
            'response':out.decode('ascii',errors='backslashreplace')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device',default='/dev/ttyS1',choices=['/dev/ttyS1'])
    p.add_argument('commands',nargs='*',choices=ALLOWED,default=list(ALLOWED))
    a=p.parse_args()
    if os.path.realpath(a.device)!='/dev/ttyS1':raise SystemExit('unexpected device alias')
    console=Path('/proc/consoles').read_text()
    if any(line.split()[0]=='ttyS1' for line in console.splitlines() if line.split()):
        raise SystemExit('UART1 is a console; refusing')
    with open('/run/lock/terminal6-esp32-query.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if owners(a.device):raise SystemExit('UART already open: '+str(owners(a.device)))
        fd=os.open(a.device,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
        before=termios.tcgetattr(fd)
        try:
            fcntl.ioctl(fd,termios.TIOCEXCL)
            if any(pid!=os.getpid() for pid in owners(a.device)):
                raise SystemExit('UART ownership race detected')
            attrs=termios.tcgetattr(fd)
            attrs[0]=0;attrs[1]=0;attrs[3]=0
            attrs[2]=(attrs[2]&~(termios.CSIZE|termios.PARENB|termios.CSTOPB|termios.CRTSCTS))|termios.CS8|termios.CREAD|termios.CLOCAL
            attrs[4]=attrs[5]=termios.B115200
            attrs[6][termios.VMIN]=0;attrs[6][termios.VTIME]=0
            termios.tcsetattr(fd,termios.TCSANOW,attrs)
            # Bounded drain of pre-existing input; no unbounded read or tcdrain.
            drained=0;end=time.monotonic()+0.2
            while time.monotonic()<end and drained<4096:
                if select.select([fd],[],[],0.02)[0]:drained+=len(os.read(fd,min(512,4096-drained)))
            print(json.dumps({'drained_bytes':drained}),flush=True)
            for cmd in a.commands:
                result=query(fd,cmd);print(json.dumps(result),flush=True)
                if not result['complete'] or result['limit_reached']:
                    break  # Never send another query into an ambiguous response.
        finally:
            termios.tcsetattr(fd,termios.TCSANOW,before)
            fcntl.ioctl(fd,termios.TIOCNXCL)
            os.close(fd)


if __name__=='__main__':main()
