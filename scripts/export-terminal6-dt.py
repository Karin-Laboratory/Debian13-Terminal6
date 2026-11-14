#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Origin: independently authored metadata allowlist exporter, 2026-11-14.
"""Export reviewed DT fields only. Manually review output before publication."""
import argparse
import collections
import json

FIELDS=('path','compatible','status','reg','interrupts','clock-names',
        'reset-names','power-domain-names','reg-names','bus-width','max-frequency')


def export(report):
    bindings=collections.defaultdict(list)
    for bus,devices in report['buses'].items():
        for d in devices:
            path=d.get('of_node','').removeprefix('/sys/firmware/devicetree/base')
            if path:bindings[path].append({'bus':bus,'driver':d.get('driver','').split('/')[-1] or None})
    nodes=[]
    for n in report['device_tree']:
        path=n['path']
        if path=='/chosen' or path.startswith('/chosen/') or 'rawdata' in path.lower():continue
        item={key:n[key] for key in FIELDS if key in n}
        item['declared_status']=n.get('status',['okay'])[0]
        item['bindings']=bindings[path];nodes.append(item)
    return {'schema':1,'source':'Live sysfs metadata, Debian 13 C-unit, 2026-11-14; filtered observation, not a redistributable DTS',
      'dt_total_nodes':len(report['device_tree']),'exported_nodes':len(nodes),
      'disabled_nodes':[n['path'] for n in report['device_tree'] if n.get('status')==['disabled']],
      'bus_counts':{b:len(d) for b,d in report['buses'].items()},
      'platform_bound':sum('driver'in d for d in report['buses'].get('platform',[])),'nodes':nodes}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('private_input');a=p.parse_args()
    with open(a.private_input) as f:print(json.dumps(export(json.load(f)),indent=2,ensure_ascii=False))
