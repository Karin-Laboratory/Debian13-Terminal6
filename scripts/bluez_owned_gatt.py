#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored owner-only BlueZ test fixture, 2026-11-14.
"""Bounded test GATT server on the owned gateway. Requires python3-dbus/GI.

T6_ALLOWED_PEER supplies the explicitly owned ESP address, never scan-and-pick.
Optional owner-only pairing agent; no bond deletion. Only test bytes stored.
"""
import os,json,signal,time,re,subprocess
import dbus,dbus.service,dbus.mainloop.glib
from gi.repository import GLib
ROOT='/t6blelab';SVC='fa1c7e10-7bea-4a8e-a9f0-5f476d6a0001';CHAR='fa1c7e11-7bea-4a8e-a9f0-5f476d6a0001'
VALUE=b'T6\x00lab\r\nOK\r\nend';WRITE=b'T6-client\x00\r\nOK\r\n';IF='org.freedesktop.DBus.Properties'
ALLOWED=os.environ['T6_ALLOWED_PEER'].lower()
if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',ALLOWED):raise SystemExit('invalid owned peer')
def log(**kw):print(json.dumps(kw),flush=True)
def ay(b):return dbus.Array([dbus.Byte(x) for x in b],signature='y')
class Denied(dbus.DBusException):_dbus_error_name='org.bluez.Error.NotAuthorized'

class Obj(dbus.service.Object):
 def __init__(self,bus,path,iface,props):super().__init__(bus,path);self.path=path;self.iface=iface;self.props=props
 @dbus.service.method(IF,in_signature='s',out_signature='a{sv}')
 def GetAll(self,iface):
  if iface!=self.iface:raise Denied('interface')
  return self.props
 @dbus.service.method(IF,in_signature='ss',out_signature='v')
 def Get(self,iface,name):return self.GetAll(iface)[name]
 @dbus.service.signal(IF,signature='sa{sv}as')
 def PropertiesChanged(self,iface,changed,invalidated):pass

class App(dbus.service.Object):
 def __init__(self,bus,objects):super().__init__(bus,ROOT);self.objects=objects
 @dbus.service.method('org.freedesktop.DBus.ObjectManager',out_signature='a{oa{sa{sv}}}')
 def GetManagedObjects(self):return {o.path:{o.iface:o.props} for o in self.objects}

class Characteristic(Obj):
 def __init__(self,bus,index=0):
  self.kind=['notify','indicate','encrypted'][index]
  super().__init__(bus,ROOT+'/service0/char'+str(index),'org.bluez.GattCharacteristic1',
   {'UUID':CHAR.replace('7e11','7e1'+str(index+1)),'Service':dbus.ObjectPath(ROOT+'/service0'),
    'Flags':dbus.Array(['read','write']+([self.kind] if index<2 else ['encrypt-read','encrypt-write']),signature='s'),'Value':ay(VALUE),'Notifying':dbus.Boolean(False)})
  self.bus=bus;self.value=VALUE;self.sequence=0
 def check(self,options):
  path=str(options.get('device',''))
  if not path:raise Denied('missing peer identity')
  if path!='/org/bluez/hci0/dev_'+ALLOWED.upper().replace(':','_'):raise Denied('not the owned test peer')
 @dbus.service.method('org.bluez.GattCharacteristic1',in_signature='a{sv}',out_signature='ay')
 def ReadValue(self,options):
  self.check(options);offset=int(options.get('offset',0));log(read=True,kind=self.kind,bytes=len(self.value),mtu=int(options.get('mtu',0)))
  return ay(self.value[offset:])
 @dbus.service.method('org.bluez.GattCharacteristic1',in_signature='aya{sv}')
 def WriteValue(self,value,options):
  self.check(options);raw=bytes(value)
  if raw!=WRITE:raise Denied('only test fixture data accepted')
  self.value=raw;self.props['Value']=ay(raw);log(write=True,kind=self.kind,bytes=len(raw),fixture_match=True,mtu=int(options.get('mtu',0)))
 @dbus.service.method('org.bluez.GattCharacteristic1')
 def StartNotify(self):
  self.props['Notifying']=dbus.Boolean(True);self.sequence=0;log(subscription=True,kind=self.kind);GLib.timeout_add(300,self.pulse)
 @dbus.service.method('org.bluez.GattCharacteristic1')
 def StopNotify(self):self.props['Notifying']=dbus.Boolean(False);log(subscription=False,kind=self.kind)
 @dbus.service.method('org.bluez.GattCharacteristic1')
 def Confirm(self):log(indication_confirmed=True,kind=self.kind)
 def pulse(self):
  if not self.props['Notifying'] or self.sequence>=3:return False
  self.sequence+=1;value=b'T6-notify'+bytes([self.sequence])+b'\r\nOK\r\n'
  self.PropertiesChanged(self.iface,{'Value':ay(value)},[]);log(notification_sent=self.sequence,kind=self.kind,bytes=len(value));return True

class Adv(Obj):
 def __init__(self,bus):super().__init__(bus,ROOT+'/adv','org.bluez.LEAdvertisement1',
  {'Type':'peripheral'})
 @dbus.service.method('org.bluez.LEAdvertisement1')
 def Release(self):log(advertisement_released=True)

class Agent(dbus.service.Object):
 def check(self,device):
  if str(device)!='/org/bluez/hci0/dev_'+ALLOWED.upper().replace(':','_'):raise Denied('unowned peer')
 @dbus.service.method('org.bluez.Agent1')
 def Release(self):pass
 @dbus.service.method('org.bluez.Agent1',in_signature='o')
 def RequestAuthorization(self,device):self.check(device)
 @dbus.service.method('org.bluez.Agent1',in_signature='os')
 def AuthorizeService(self,device,uuid):self.check(device)
 @dbus.service.method('org.bluez.Agent1',in_signature='ou')
 def RequestConfirmation(self,device,passkey):raise Denied('numeric comparison needs a separate human test')
 @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='u')
 def RequestPasskey(self,device):raise Denied('no passkey test')
 @dbus.service.method('org.bluez.Agent1',in_signature='o',out_signature='s')
 def RequestPinCode(self,device):raise Denied('no legacy PIN test')
 @dbus.service.method('org.bluez.Agent1')
 def Cancel(self):log(pairing_cancelled=True)

def main():
 dbus.mainloop.glib.DBusGMainLoop(set_as_default=True);bus=dbus.SystemBus();loop=GLib.MainLoop()
 adapter=bus.get_object('org.bluez','/org/bluez/hci0');props=dbus.Interface(adapter,IF)
 before=bool(props.Get('org.bluez.Adapter1','Powered'));props.Set('org.bluez.Adapter1','Powered',True)
 svc=Obj(bus,ROOT+'/service0','org.bluez.GattService1',{'UUID':SVC,'Primary':dbus.Boolean(True),'Characteristics':dbus.Array([dbus.ObjectPath(ROOT+'/service0/char'+str(i)) for i in range(3)],signature='o')})
 chars=[Characteristic(bus,i) for i in range(3)];app=App(bus,[svc]+chars);adv=Adv(bus)
 manager=dbus.Interface(adapter,'org.bluez.GattManager1');advertiser=dbus.Interface(adapter,'org.bluez.LEAdvertisingManager1')
 agent=None;agent_manager=None
 if os.environ.get('T6_ALLOW_PAIR')=='1':
  agent=Agent(bus,ROOT+'/agent');agent_manager=dbus.Interface(bus.get_object('org.bluez','/org/bluez'),'org.bluez.AgentManager1')
  agent_manager.RegisterAgent(ROOT+'/agent','NoInputNoOutput');agent_manager.RequestDefaultAgent(ROOT+'/agent')
 registered={'app':False,'adv':False};state={'discovering':False,'device':None,'legacy':False}
 def failed(error):log(error=error.get_dbus_name(),message=re.sub(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}','<address>',error.get_dbus_message()));loop.quit()
 def adv_ready():registered['adv']=True;log(ready=True,test_service=SVC)
 def app_ready():
  registered['app']=True;log(application_registered=True,ready=True)
  if os.environ.get('T6_GATEWAY_ADVERTISE')=='1':
   state['legacy']=True
   for args in [['btmgmt','--index','0','connectable','on'],['btmgmt','--index','0','advertising','on']]:
    result=subprocess.run(args,capture_output=True,timeout=8);log(legacy_mgmt=args[-2],returncode=result.returncode)
    if result.returncode:loop.quit();return
   state['legacy']=True;return
  client=dbus.Interface(adapter,'org.bluez.Adapter1')
  if props.Get('org.bluez.Adapter1','Discovering'):failed(dbus.DBusException('discovery already active'));return
  client.SetDiscoveryFilter({'Transport':'le','Pattern':ALLOWED.upper(),'DuplicateData':False})
  client.StartDiscovery()
  state['discovering']=True
  GLib.timeout_add(200,connect_owned)
 def connect_owned():
  om=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager')
  for path,interfaces in om.GetManagedObjects().items():
   d=interfaces.get('org.bluez.Device1',{})
   if str(d.get('Address','')).lower()!=ALLOWED:continue
   if d.get('Connected'):log(error='already-connected');loop.quit();return False
   dbus.Interface(adapter,'org.bluez.Adapter1').StopDiscovery();state['discovering']=False
   state['device']=str(path)
   device=dbus.Interface(bus.get_object('org.bluez',path),'org.bluez.Device1')
   device.Connect(reply_handler=lambda:log(connected_owned_peer=True),error_handler=failed)
   return False
  return True
 def quit_loop(*args):loop.quit();return False
 signal.signal(signal.SIGTERM,quit_loop);signal.signal(signal.SIGINT,quit_loop);signal.signal(signal.SIGHUP,quit_loop)
 GLib.timeout_add_seconds(180,quit_loop)
 manager.RegisterApplication(ROOT,{},reply_handler=app_ready,error_handler=failed)
 try:loop.run()
 finally:
  if state['legacy']:
   subprocess.run(['btmgmt','--index','0','advertising','off'],capture_output=True,timeout=8)
   subprocess.run(['btmgmt','--index','0','connectable','off'],capture_output=True,timeout=8)
  if state['discovering']:
   try:dbus.Interface(adapter,'org.bluez.Adapter1').StopDiscovery()
   except dbus.DBusException:pass
  if state['device']:
   try:dbus.Interface(bus.get_object('org.bluez',state['device']),'org.bluez.Device1').Disconnect()
   except dbus.DBusException:pass
  if registered['adv']:
   try:advertiser.UnregisterAdvertisement(adv.path)
   except dbus.DBusException:pass
  if registered['app']:
   try:manager.UnregisterApplication(ROOT)
   except dbus.DBusException:pass
  if agent_manager:
   try:agent_manager.UnregisterAgent(ROOT+'/agent')
   except dbus.DBusException:pass
  props.Set('org.bluez.Adapter1','Powered',before);log(cleanup=True,adapter_power_restored=before)

if __name__=='__main__':main()
