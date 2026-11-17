# SPDX-License-Identifier: MIT
# Origin: independently authored parser/lifecycle/privacy tests, 2026-11-14.
import importlib.util,os,pty,threading,time,tty,unittest,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('ble',Path(__file__).resolve().parents[1]/'scripts/esp32_ble.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ParserTests(unittest.TestCase):
 def test_fragmented_binary_cannot_inject_ok(self):
  f=m.Framer();data=b'\x00\r\nOK\r\n\xff'
  stream=b'\r\n+BLEGATTCRD:0,'+str(len(data)).encode()+b','+data+b'\r\nOK\r\n'
  frames=[]
  for byte in stream:frames+=f.feed(bytes([byte]))
  self.assertEqual([x[0] for x in frames],['binary','line']);self.assertTrue(frames[0][1].endswith(data));self.assertEqual(frames[1][1],b'OK')
 def test_notify_indicate_and_prompt(self):
  f=m.Framer();v=f.feed(b'+NOTIFY:0,4,1,3,a\x00b\r\n+INDICATE:0,4,2,2,xy\r\n>')
  self.assertEqual([x[0] for x in v],['binary','binary','prompt'])
 def test_bounds_and_bad_header(self):
  with self.assertRaises(m.ProtocolError):m.Framer(32).feed(b'x'*33)
  with self.assertRaises(m.ProtocolError):m.Framer().feed(b'+BLEGATTCRD:0,999999,x')
  with self.assertRaises(m.ProtocolError):m.Framer().feed(b'+WRITE:unrecognized\r\n')
 def test_scan_quoted_address_and_privacy(self):
  addr=':'.join(['aa','bb','cc','dd','ee','ff']);stats=m.ScanStats();stats.add(f'+BLESCAN:"{addr}",-60,020106,,0')
  self.assertEqual(stats.summary()['reports'],1);self.assertEqual(stats.summary()['ad_type_counts'],{'0x01':1})
  self.assertNotIn(addr,json.dumps(stats.summary()));self.assertNotIn(addr,m.redact('+BLECONN:0,"'+addr+'"'))
  self.assertEqual(m.redact('+BLESETKEY:123456'),'+BLESETKEY:<private>')
  self.assertEqual(m.redact('+BLEADVDATAEX:personal-name'),'+BLEADVDATAEX:<private>')
class TransactionTests(unittest.TestCase):
 def setUp(self):
  self.master,self.slave=pty.openpty();tty.setraw(self.slave);os.set_blocking(self.slave,False);self.logs=[];self.at=m.AT(self.slave,self.logs.append)
 def tearDown(self):os.close(self.master);os.close(self.slave)
 def emulator(self,fn):
  t=threading.Thread(target=fn);t.start();return t
 def test_ok_without_connection_event_not_success(self):
  def respond():os.read(self.master,100);os.write(self.master,b'\r\nOK\r\n')
  t=self.emulator(respond)
  with self.assertRaises(m.ProtocolError):self.at.command('AT+BLECONN=0,"owned"',timeout=.05,wait_event='+BLECONN:0,')
  t.join();self.assertTrue(self.at.tainted)
  with self.assertRaises(m.ProtocolError):self.at.command('AT')
 def test_error_is_synchronized_and_cleanup_runs(self):
  def respond():
   for reply in [b'ERROR',b'OK',b'+BLEINIT:0\r\nOK']:
    os.read(self.master,100);os.write(self.master,b'\r\n'+reply+b'\r\n')
  t=self.emulator(respond)
  with self.assertRaises(m.ATError):self.at.command('AT+BLEGATTSCHAR?')
  b=m.BLE(self.at);b.owned=True;b.close();t.join(1);self.assertFalse(b.owned);self.assertFalse(self.at.tainted)
 def test_async_mtu_is_separate_from_query(self):
  def respond():
   os.read(self.master,100);os.write(self.master,b'\r\n+BLECFGMTU:0,64\r\n+BLESECPARAM:0,0,0,0,0,0\n\r\nOK\r\n')
  t=self.emulator(respond);r=self.at.command('AT+BLESECPARAM?');t.join(1)
  self.assertEqual(self.at.mtu[0],64);self.assertEqual(r['lines'],['+BLESECPARAM:0,0,0,0,0,0'])
 def test_empty_connection_query(self):
  def respond():
   os.read(self.master,100);os.write(self.master,b'\r\n+BLECONN:\r\nOK\r\n')
  t=self.emulator(respond);r=self.at.command('AT+BLECONN?');t.join(1)
  self.assertEqual(r['lines'],['+BLECONN:']);self.assertFalse(self.at.connections)
 def test_uuid_resolution_rejects_ambiguity(self):
  b=m.BLE(self.at);b.discover=lambda *args:{'lines':['+BLEGATTCPRIMSRV:0,1,"0x1234",1','+BLEGATTCPRIMSRV:0,2,"0x1234",1']}
  with self.assertRaises(m.ProtocolError):b.resolve(0,'1234','5678')
 def test_payload_only_after_prompt(self):
  seen=[]
  def respond():
   seen.append(os.read(self.master,100));os.write(self.master,b'\r\n>');seen.append(os.read(self.master,100));os.write(self.master,b'\r\nOK\r\n')
  t=self.emulator(respond);self.at.command('AT+BLEGATTCWR=0,4,1,,3',payload=b'\x00\xffx');t.join(1)
  self.assertEqual(seen[1],b'\x00\xffx')
 def test_restart_is_not_an_ok(self):
  with self.assertRaises(m.ProtocolError):self.at.event('line',b'ready')
  self.assertTrue(self.at.tainted)
 def test_unowned_connection_and_sink_failure(self):
  self.at.expected_peer=':'.join(['00']*6)
  with self.assertRaises(m.ProtocolError):self.at.event('line',b'+BLECONN:0,"'+(':'.join(['11']*6)).encode()+b'"')
  a=m.AT(self.slave,lambda _:(_ for _ in ()).throw(BrokenPipeError()));a.emit({'cleanup':'must not crash'})
 def test_connect_and_pairing_need_ownership(self):
  b=m.BLE(self.at)
  with self.assertRaises(ValueError):b.connect(':'.join(['00']*6))
  b.owned=True;self.at.connections.add(0)
  with self.assertRaises(ValueError):b.encrypt(0)
if __name__=='__main__':unittest.main()
