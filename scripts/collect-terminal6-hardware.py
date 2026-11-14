#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored read-only Linux/sysfs collector, 2026-11-14.
"""Bounded hardware observations. Output is PRIVATE until manually reviewed.

No bus scans, radio activation, raw MMIO, partition writes or watchdog opens.
Device Tree export uses a property allowlist and excludes binary calibration.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def read(path, limit=131072):
    try:
        with open(path, 'rb') as stream:
            return stream.read(limit).decode(errors='replace').strip()
    except OSError as exc:
        return 'ERROR: ' + str(exc)


def device_tree():
    base = Path('/sys/firmware/devicetree/base')
    strings = ['compatible', 'status', 'device_type', 'model', 'clock-names',
               'reset-names', 'power-domain-names', 'interrupt-names', 'phy-mode',
               'label', 'firmware-name', 'reg-names', 'dma-names']
    cells = ['reg', 'interrupts', 'interrupts-extended', 'clocks', 'resets',
             'power-domains', 'iommus', 'dmas', 'phandle', '#address-cells',
             '#size-cells', '#clock-cells', '#reset-cells', 'memory-region',
             'clock-frequency', 'bus-width', 'max-frequency', 'ranges']
    result=[]
    for root, dirs, files in os.walk(base):
        item={'path': '/' + str(Path(root).relative_to(base)).replace('.', '', 1)
              if Path(root)==base else '/' + str(Path(root).relative_to(base))}
        item['properties']=sorted(files)
        for prop in strings + cells:
            if prop not in files:
                continue
            raw=(Path(root)/prop).read_bytes()
            if prop in strings:
                item[prop]=raw.rstrip(b'\0').decode(errors='replace').split('\0')
            elif len(raw)%4==0:
                item[prop]=[hex(int.from_bytes(raw[i:i+4], 'big')) for i in range(0,len(raw),4)]
        result.append(item)
    return sorted(result, key=lambda node:node['path'])


def buses():
    result={}
    for bus in ['platform','pci','usb','i2c','spi','mdio_bus','mmc','sdio','serial','rpmsg']:
        devices=[]
        for path in sorted(Path('/sys/bus/'+bus+'/devices').glob('*')):
            item={'name':path.name}
            for link in ['driver','of_node','iommu_group']:
                if (path/link).is_symlink(): item[link]=os.path.realpath(path/link)
            for name in ['modalias','resource','irq','vendor','device','class','uevent']:
                if (path/name).is_file(): item[name]=read(path/name, 16384)
            devices.append(item)
        result[bus]=devices
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='-')
    parser.add_argument('--metadata-only', action='store_true', help='Compatibility flag; collection is metadata only')
    opts=parser.parse_args()
    report={'schema':1,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'device_tree':device_tree(),'buses':buses(),'sysfs':{},
      'proc':{p:read('/proc/'+p,262144) for p in ['cpuinfo','meminfo','iomem','interrupts','modules','crypto','devices','consoles']},
      'debug':{},'commands':[]}
    payload=json.dumps(report,indent=2)+'\n'
    if opts.output=='-': sys.stdout.write(payload)
    else:
        raise SystemExit('Refusing target-side file output; redirect stdout on the development VM')


if __name__=='__main__': main()
