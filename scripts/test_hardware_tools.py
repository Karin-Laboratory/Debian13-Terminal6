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


class SafetyTests(unittest.TestCase):
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
