#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored safety/semantic tests, 2026-11-14.
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import threading
import tty
import unittest


def load(filename):
    spec=importlib.util.spec_from_file_location(filename,Path(__file__).with_name(filename))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


fdt=load('fdt_mmc_policy.py')
at=load('esp32-readonly-at.py')
exporter=load('export-terminal6-dt.py')
collector=load('collect-terminal6-hardware.py')


class SafetyTests(unittest.TestCase):
    def test_sysfs_inventory_is_bounded_and_omits_hardware_identifiers(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def put(rel, value):
                path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
            put('class/thermal/thermal_zone0/type','cpu-little0\n')
            put('class/thermal/thermal_zone0/temp','61234\n')
            put('devices/system/cpu/cpufreq/policy0/scaling_cur_freq','1200000\n')
            put('devices/system/cpu/cpufreq/policy0/scaling_max_freq','1701000\n')
            put('class/net/lan2/operstate','up\n')
            put('class/net/lan2/carrier','1\n')
            put('class/net/lan2/address','02:11:22:33:44:55\n')
            put('class/mmc_host/mmc0/mmc0:0001/name','4FTE4R\n')
            put('class/mmc_host/mmc0/mmc0:0001/life_time','0x01 0x01\n')
            put('class/mmc_host/mmc0/mmc0:0001/cmdq_en','0\n')
            put('class/mmc_host/mmc0/mmc0:0001/cid','PRIVATE-CID\n')
            put('bus/usb/devices/1-1/idVendor','0e8d\n')
            put('bus/usb/devices/1-1/idProduct','0003\n')
            put('bus/usb/devices/1-1/serial','PRIVATE-USB-SERIAL\n')
            report=collector.sysfs_inventory(root)
            serialized=json.dumps(report)
            self.assertEqual(report['thermal_zones'][0]['temp'],'61234')
            self.assertEqual(report['cpufreq_policies'][0]['scaling_cur_freq'],'1200000')
            self.assertEqual(report['network_interfaces'][0]['operstate'],'up')
            self.assertEqual(report['mmc_cards'][0]['name'],'4FTE4R')
            self.assertEqual(report['mmc_cards'][0]['cmdq_en'],'0')
            self.assertEqual(report['usb_devices'][0]['idVendor'],'0e8d')
            for secret in ('02:11:22:33:44:55','PRIVATE-CID','PRIVATE-USB-SERIAL'):
                self.assertNotIn(secret,serialized)

    def test_export_excludes_private_fields_and_chosen(self):
        report={'device_tree':[{'path':'/chosen','reg':['SECRET']},
            {'path':'/rawdata-system','compatible':['SECRET']},
            {'path':'/test','compatible':['test,device'],'reg':['0x1000'],
             'serial-number':'SECRET','mac-address':'SECRET','eeprom':'SECRET'}],
            'buses':{'platform':[]},'proc':{'cpuinfo':'SECRET'}}
        out=exporter.export(report)
        self.assertEqual(out['exported_nodes'],1)
        self.assertNotIn('SECRET',json.dumps(out))

    def test_fdt_policies_preserve_every_other_property(self):
        source='''/dts-v1/; / { #address-cells=<1>; #size-cells=<1>;
          unrelated { secret-test="unchanged"; };
          mmc@11230000 { compatible="mediatek,mt6990-mmc";
            reg=<0x11230000 0x1000>; bus-width=<8>; supports-cqe;
            max-frequency=<200000000>; mmc-hs200-1_8v; mmc-hs400-1_8v;
          }; };'''
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/'base.dtb';subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(base)],input=source.encode(),check=True,capture_output=True)
            sha=hashlib.sha256(base.read_bytes()).hexdigest()
            for mode in ['no-cqe','max100','no-hs400','no-hs200-hs400']:
                out=Path(d)/(mode+'.dtb');receipt=fdt.make_candidate(base,out,sha,mode)
                props,_=fdt.properties(out.read_bytes())
                self.assertEqual(props[('/unrelated','secret-test')],b'unchanged\0')
                self.assertTrue(receipt['only_expected_properties_changed'])
                if mode=='no-cqe':self.assertNotIn((fdt.NODE,'supports-cqe'),props)
            with self.assertRaises(ValueError):fdt.make_candidate(base,Path(d)/'bad.dtb','0'*64,'no-cqe')
            self.assertFalse((Path(d)/'bad.dtb').exists())
            with self.assertRaises(ValueError):fdt.make_candidate(base,base,sha,'no-cqe')
            fragment=Path(__file__).resolve().parent.parent/'patches'
            combined=source+'\n/include/ "mmc-no-cqe.dtsi"\n'
            compiled=Path(d)/'static-fragment.dtb'
            subprocess.run(['dtc','-i',str(fragment),'-I','dts','-O','dtb','-o',str(compiled)],
                           input=combined.encode(),check=True,capture_output=True)
            self.assertNotIn((fdt.NODE,'supports-cqe'),fdt.properties(compiled.read_bytes())[0])

    def test_at_allowlist_timeout_limit_and_success(self):
        master,slave=pty.openpty();tty.setraw(slave)
        try:
            with self.assertRaises(ValueError):at.query(slave,'AT+RST')
            self.assertFalse(at.query(slave,'AT',timeout=0.03)['complete'])
            os.read(master,100) # consume the timed-out request
            def response():
                request=os.read(master,100)
                if request!=b'AT+GMR\r\n':raise AssertionError(request)
                os.write(master,b'\r\nTEST-VERSION\r\nOK\r\n')
            t=threading.Thread(target=response);t.start()
            result=at.query(slave,'AT+GMR',timeout=1);t.join(1)
            self.assertTrue(result['complete'])
            os.write(master,b'x'*128)
            limited=at.query(slave,'AT',timeout=0.2,limit=32)
            self.assertTrue(limited['limit_reached']);self.assertEqual(len(limited['response']),32)
        finally:os.close(master);os.close(slave)


if __name__=='__main__':unittest.main()
