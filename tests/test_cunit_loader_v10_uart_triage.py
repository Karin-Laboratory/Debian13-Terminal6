#!/usr/bin/env python3
"""Synthetic tests only. No real private UART data included."""
import importlib.util
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / "scripts/triage-cunit-loader-v10-uart.py"
spec = importlib.util.spec_from_file_location("loader_uart_triage", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class UARTPhaseTests(unittest.TestCase):
    def test_stock_b_banner_after_watchdog_cannot_pass_a(self):
        s=b"Kernel_EL 2\nPreparing for EL3 exit to normal world\nel3_exit\nCPU(0) in ATF by WDT\nLinux version 5.4 stock B\n"
        r=mod.summarize(s)
        self.assertEqual(r["verdict"],"EL3_TO_FIRST_LINUX_OUTPUT_UNPROVEN_WDT_OBSERVED")
        self.assertFalse(r["pre_first_watchdog_markers"]["linux_banner"])
        self.assertTrue(r["watchdog_marker_present"])

    def test_loader_ready_before_watchdog_is_distinct(self):
        s=b"el3_exit\nLinux version 6.18.63\nTERMINAL6_LOADER_INIT_STARTED\nTERMINAL6_LOADER_READY\nHW_WDT"
        r=mod.summarize(s)
        self.assertEqual(r["verdict"],"LOADER_READY_MARKER_OBSERVED_BEFORE_FIRST_WDT")

    def test_no_wdt_does_not_imply_success(self):
        r=mod.summarize(b"el3_exit\n")
        self.assertEqual(r["verdict"],"NO_WDT_MARKER_FOUND_PHASE_UNRESOLVED")

    def test_wdt_without_atf_handoff_remains_unknown(self):
        r=mod.summarize(b"boot something\nHW_WDT\n")
        self.assertEqual(r["verdict"],"WDT_OBSERVED_PHASE_UNRESOLVED")

    def test_never_echo_private_uart_fragments(self):
        text=b"SECRET_PRIVATE_TOKEN_NOT_FOR_OUTPUT\nel3_exit\nHW_WDT\n"
        r=mod.summarize(text)
        self.assertNotIn("SECRET_PRIVATE_TOKEN",str(r))
        self.assertEqual(r["log_bytes"],len(text))

if __name__=="__main__":
    unittest.main()
