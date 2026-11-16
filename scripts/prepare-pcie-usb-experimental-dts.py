#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create opt-in, EXPLICITLY EXPERIMENTAL P25 Device Tree for PCIe and USB.

Uses only the independently authored public Ethernet+eMMC board candidate.
Does NOT use a vendor-derived board dump or invent reset GPIOs, regulators,
clock frequencies, USB VBUS power, radio calibration or memory mappings.
Enabling a DT node does NOT constitute physical LK/PCI/USB boot validation.
"""
from pathlib import Path
import sys

SOURCE_BASE_INCLUDE = '#include "terminal6-debian-experimental.dts"'
BASE_INCLUDE = '#include "terminal6-debian-ethernet-experimental.dts"'
HEADER = """// SPDX-License-Identifier: GPL-2.0-only
/*
 * SoftBank Air Terminal 6 C-unit: PCIe/USB source-only experiment.
 * NOT PHYSICALLY VERIFIED / DO NOT SIGN OR FLASH without separate review.
 * SoC MMIO, interrupts, ranges and references come from pinned public MT6990
 * DTSI. PCIe PHY fallback is from public MT6980/MT6990 driver port.
 * No board-specific reset GPIO, VBUS source, regulator or calibration is
 * guessed; missing dependencies must remain explicit runtime blockers.
 */
"""
BLOCKS = [
    """&pcie0 {
    status = "okay";
};""",
    """&pcie1 {
    status = "okay";
};""",
    """&pcie2 {
    status = "okay";
};""",
]
for index in range(3):
    BLOCKS.append(f"""&pciephy{index} {{
    compatible = "mediatek,mt6990-pcie-phy", "mediatek,mt6980-pcie-phy";
    phy-id = <{index}>;
    status = "okay";
}};""")
BLOCKS.extend([
    """&xsphy {
    status = "okay";
};""",
    """&usb {
    dr_mode = "host";
    status = "okay";
};""",
    """&xhci {
    status = "okay";
};""",
])

def make_overlay(source: str) -> str:
    if source.count(SOURCE_BASE_INCLUDE) != 1:
        raise ValueError("BASE_ETHERNET_INCLUDE_MUST_BE_EXACTLY_ONE")
    if any(tag in source for tag in ("&pciephy0 {", "&pciephy1 {", "&pciephy2 {", "&xhci {")):
        raise ValueError("BASE_CONTAINS_UNEXPECTED_PCIE_PHY_OR_XHCI_OVERRIDE")
    if "status = \"okay\";" not in source or "&eth {" not in source:
        raise ValueError("BASE_ETHERNET_BOARD_GATE_MISSING")
    return HEADER + BASE_INCLUDE + "\n\n" + "\n\n".join(BLOCKS) + "\n"

def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: prepare-pcie-usb-experimental-dts.py BASE.dts NEW.dts")
    original, new = map(Path, sys.argv[1:])
    if original.resolve() == new.resolve() or new.exists():
        raise SystemExit("REFUSE_INPUT_OVERWRITE")
    new.write_text(make_overlay(original.read_text()))
    print("CUNIT_PCIE0_1_2_PHY0_1_2_USB_XHCI_XSPHY_SOURCE_ENABLED_EXPERIMENTAL")

if __name__ == "__main__":
    main()
