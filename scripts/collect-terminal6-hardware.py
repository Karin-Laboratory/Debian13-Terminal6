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


def _class_devices(sys_root, class_name, attributes):
    """Read an allowlist of non-secret attributes from one sysfs class."""
    relative = Path(class_name)
    base = Path(sys_root) / relative if len(relative.parts) > 1 else Path(sys_root) / 'class' / relative
    result = []
    for entry in sorted(base.glob('*')):
        if not entry.exists():
            continue
        item = {'name': entry.name}
        driver = entry / 'device' / 'driver'
        if driver.is_symlink():
            item['driver'] = Path(os.path.realpath(driver)).name
        for attribute in attributes:
            path = entry / attribute
            if path.is_file():
                item[attribute.replace('/', '_')] = read(path, 4096)
        result.append(item)
    return result


def sysfs_inventory(sys_root='/sys'):
    """Bounded runtime inventory; deliberately excludes hardware identifiers.

    In particular, do not collect netdev addresses, MMC CID/serial, USB serial,
    EEPROM/calibration, or arbitrary uevent files into an exportable report.
    The complete collector output remains private until reviewed.
    """
    root = Path(sys_root)
    cpufreq = []
    for entry in sorted((root / 'devices/system/cpu/cpufreq').glob('policy*')):
        item = {'name': entry.name}
        for attr in ('scaling_driver', 'scaling_governor', 'scaling_min_freq',
                     'scaling_max_freq', 'cpuinfo_min_freq', 'cpuinfo_max_freq',
                     'cpuinfo_cur_freq', 'scaling_cur_freq'):
            path = entry / attr
            if path.is_file(): item[attr] = read(path, 4096)
        cpufreq.append(item)

    storage = []
    for entry in sorted((root / 'class/mmc_host').glob('host*/mmc*')):
        item = {'name': entry.name}
        for attr in ('type', 'name', 'manfid', 'oemid', 'date', 'life_time',
                     'pre_eol_info', 'cmdq_en', 'block/size', 'block/ro',
                     'block/partition'):
            path = entry / attr
            if path.is_file(): item[attr.replace('/', '_')] = read(path, 4096)
        storage.append(item)

    blocks = []
    for entry in sorted((root / 'class/block').glob('mmcblk*')):
        item = {'name': entry.name}
        for attr in ('size', 'ro', 'partition'):
            path = entry / attr
            if path.is_file(): item[attr] = read(path, 4096)
        blocks.append(item)

    network = []
    for entry in sorted((root / 'class/net').glob('*')):
        item = {'name': entry.name}
        for attr in ('operstate', 'carrier', 'speed', 'duplex', 'mtu'):
            path = entry / attr
            if path.is_file(): item[attr] = read(path, 4096)
        stats = entry / 'statistics'
        if stats.is_dir():
            item['statistics'] = {}
            for attr in ('rx_bytes', 'rx_packets', 'rx_errors', 'rx_dropped',
                         'tx_bytes', 'tx_packets', 'tx_errors', 'tx_dropped'):
                path = stats / attr
                if path.is_file(): item['statistics'][attr] = read(path, 4096)
        driver = entry / 'device' / 'driver'
        if driver.is_symlink(): item['driver'] = Path(os.path.realpath(driver)).name
        network.append(item)

    thermal = _class_devices(sys_root, 'thermal', ('type', 'temp', 'mode'))
    hwmon = _class_devices(sys_root, 'hwmon', ('name',))
    for item, entry in zip(hwmon, sorted((root / 'class/hwmon').glob('hwmon*'))):
        sensors = {}
        for path in sorted(entry.glob('temp*_input')):
            sensors[path.name] = read(path, 4096)
            label = entry / path.name.replace('_input', '_label')
            if label.is_file(): sensors[path.name.replace('_input', '_label')] = read(label, 4096)
        if sensors: item['temperature_inputs'] = sensors

    return {
        'cpufreq_policies': cpufreq,
        'mmc_cards': storage,
        'mmc_block_devices': blocks,
        'network_interfaces': network,
        'thermal_zones': thermal,
        'hwmon': hwmon,
        'leds': _class_devices(sys_root, 'leds', ('brightness', 'max_brightness', 'trigger')),
        'input_devices': _class_devices(sys_root, 'input', ('name',)),
        'pwm_chips': _class_devices(sys_root, 'pwm', ('npwm',)),
        'rtc': _class_devices(sys_root, 'rtc', ('name', 'date', 'time', 'hctosys')),
        'watchdogs': _class_devices(sys_root, 'watchdog', ('identity', 'state', 'status', 'timeout')),
        'rng': {
            name: read(root / 'devices/virtual/misc/hw_random' / name, 4096)
            for name in ('rng_current', 'rng_available')
            if (root / 'devices/virtual/misc/hw_random' / name).is_file()
        },
        'usb_devices': _class_devices(sys_root, 'bus/usb/devices',
            ('idVendor', 'idProduct', 'manufacturer', 'product', 'speed', 'bDeviceClass')),
        'gpio_chips': _class_devices(sys_root, 'gpio', ('label', 'ngpio', 'base')),
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='-')
    parser.add_argument('--metadata-only', action='store_true', help='Compatibility flag; collection is metadata only')
    opts=parser.parse_args()
    report={'schema':1,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'device_tree':device_tree(),'buses':buses(),'sysfs':sysfs_inventory(),
      'proc':{p:read('/proc/'+p,262144) for p in ['cpuinfo','meminfo','iomem','interrupts','modules','crypto','devices','consoles']},
      'debug':{},'commands':[]}
    payload=json.dumps(report,indent=2)+'\n'
    if opts.output=='-': sys.stdout.write(payload)
    else:
        raise SystemExit('Refusing target-side file output; redirect stdout on the development VM')


if __name__=='__main__': main()
