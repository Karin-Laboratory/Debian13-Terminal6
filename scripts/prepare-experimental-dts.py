#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare explicitly experimental eMMC opt-in from independently authored DTS."""
from pathlib import Path
import re
import sys

def extract(patch):
    lines=patch.splitlines()
    output=[]; active=False
    for line in lines:
        if line.startswith("@@ -0,0 +1,"):
            active=True;continue
        if active and line.startswith("+"):
            output.append(line[1:])
    if len(output)<400 or not output[0].startswith("// SPDX-License-Identifier:"):
        raise ValueError("unrecognized public SoC patch")
    return "\n".join(output)+"\n"

def enable_emmc(board):
    # Modify only &mmc0 block; do not touch reserved-memory or unrelated nodes.
    match=re.search(r"(?ms)^&mmc0\s*\{(.*?)^\};",board)
    if not match or match.group(1).count('status = "disabled";')!=1:
        raise ValueError("MMC0 baseline not recognized")
    # C-unit eMMC mitigation already proved on hardware: 100 MHz, CQE off.
    # This does NOT validate donor SoC clock routing or the board's power pins.
    if 'supports-cqe' in match.group(0) or 'max-frequency' in match.group(0):
        raise ValueError("MMC0 baseline has unexpected CQE/frequency policy")
    new=match.group(0).replace('status = "disabled";',
                                'max-frequency = <100000000>;\n status = "okay";')
    result=board[:match.start()]+new+board[match.end():]
    if result.count('status = "okay";')!=board.count('status = "okay";')+1:
        raise ValueError("unexpected status mutation")
    return result.replace('model = "SoftBank Air Terminal 6 (research)";',
                          'model = "SoftBank Air Terminal 6 (Debian eMMC experimental)";')

if __name__=="__main__":
    if len(sys.argv)!=5:
        sys.exit("usage: prepare-experimental-dts.py soc.patch original.dts soc.dtsi output.dts")
    patch,board,dtsi,out=map(Path,sys.argv[1:])
    dtsi.write_text(extract(patch.read_text()))
    out.write_text(enable_emmc(board.read_text()))
    print("DEBIAN_EXPERIMENTAL_MMC0_OPT_IN; CONTROLLER_ROUTING_UNVERIFIED")
