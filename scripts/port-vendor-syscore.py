#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Port reviewed static vendor syscore registrations to 6.18.63 data API."""
import hashlib
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
header = (root/'include/linux/syscore_ops.h').read_text()
assert 'struct syscore {' in header and 'int (*suspend)(void *data)' in header
inputs = {
 'eccci/hif/ccci_hif_dpmaif.c': ('6b9a636b781ee32de1cfa4b7d1538407e16de62881268d699895038393be365a', 'dpmaif_sysops'),
 'medmcu/rv33/medmcu_helper.c': ('c7937c999e60257a5472ee410721b7bf6a956388967c9e5c51d659bee3a3c5e3', 'scp_ipi_dbg_syscore_ops'),
 'eccci/modem_sys1.c': ('ca78468fd6796ce55353fb26f4ddef9a33fe30f32bf3797b504c7a51a143f543', 'ccci_modem_sysops'),
 'hsapif/hif/ccci_hif_cldma.c': ('ac5605d2071c1d1df79f5afe60bc7e03a17441eab7090f880c8e0d39d4ea6a1c', 'hsapif_sysops'),
}
for rel, (expected, name) in inputs.items():
    p = root/'drivers/misc/mediatek'/rel
    s = p.read_text()
    instance = name + '_instance'
    if 'static struct syscore ' + instance + ' = {' in s:
        assert 'register_syscore_ops(&' + name + ')' not in s
        continue
    assert hashlib.sha256(p.read_bytes()).hexdigest() == expected, rel
    pattern = r'static struct syscore_ops ' + name + r' = \{(.*?)\n\};'
    matches = list(re.finditer(pattern, s, re.S))
    assert len(matches) == 1, rel
    m = matches[0]
    fields = re.findall(r'\.(suspend|resume)\s*=\s*(\w+)\s*,', m[1])
    assert len(fields) == 2 and {x[0] for x in fields} == {'suspend', 'resume'}
    assert not re.sub(r'\.(suspend|resume)\s*=\s*\w+\s*,', '', m[1]).strip()
    wrappers = []
    new_fields = []
    for kind, callback in fields:
        ret = 'int' if kind == 'suspend' else 'void'
        wrapper = name + '_' + kind + '_data'
        wrappers.append('static ' + ret + ' ' + wrapper + '(void *data)\n{\n\t' + ('return ' if ret == 'int' else '') + callback + '();\n}\n')
        new_fields.append('\t.' + kind + ' = ' + wrapper + ',')
    replacement = '\n'.join(wrappers) + '\nstatic const struct syscore_ops ' + name + ' = {\n' + '\n'.join(new_fields) + '\n};\nstatic struct syscore ' + instance + ' = {\n\t.ops = &' + name + ',\n};'
    s = s[:m.start()] + replacement + s[m.end():]
    old = 'register_syscore_ops(&' + name + ')'
    assert s.count(old) == 1
    s = s.replace(old, 'register_syscore(&' + instance + ')')
    p.write_text(s)
print('VENDOR_SYSCORE_DATA_API_PORT_PASS')
