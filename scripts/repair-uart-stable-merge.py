#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Remove a retained UPIO_AU label superseded by the 6.18.63 serial fix."""
import hashlib
from pathlib import Path
import sys

p = Path(sys.argv[1]) / 'drivers/tty/serial/8250/8250_port.c'
s = p.read_text()
old = '\tcase UPIO_PORT:\n\tcase UPIO_AU:\n\t\tp->serial_in = io_serial_in;'
new = '\tcase UPIO_PORT:\n\t\tp->serial_in = io_serial_in;'
if old in s:
    if hashlib.sha256(p.read_bytes()).hexdigest() != '026c4bd6e60ebef998fd7a72af5221ffb64bea70fcb57970b46a500c16bd7c4b':
        raise SystemExit('unexpected retained/stable UART merge')
    s = s.replace(old, new)
    p.write_text(s)
elif new not in s:
    raise SystemExit('unexpected UART serial I/O selection')
# Stable now leaves Alchemy accessors supplied by its own driver intact.
fn = s.split('static void set_io_from_upio(', 1)[1].split('static void\nserial_port_out_sync', 1)[0]
assert fn.count('case UPIO_AU:') == 1
assert '\tcase UPIO_AU:\n\t\tbreak;' in fn
print('UART_STABLE_IO_SELECTION_PASS')
