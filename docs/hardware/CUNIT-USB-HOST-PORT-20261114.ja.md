# C-unit USB host controller live test

Date: 2026-11-14 JST  
Target: SoftBank Air Terminal 6 C-unit, Debian 13 arm64, Linux 6.18.63-debian-t6-proto2.

## A/C baseline

- A has the MTU3 controller bound to `mtu3`, the nested XHCI host bound to `xhci-mtk`, and USB2/USB3 root hubs (`usb1`, `usb2`). No USB peripheral was attached in the read-only sample.
- C DT exposes the same `mediatek,mtu3` controller. The USB PHY at `11ec3000` was already bound to `mtk-xsphy`, but the MTU3/XHCI modules were not installed/loaded, and no USB bus class existed.
- C's matching 6.18 build tree already contained `mtu3.ko`, `xhci-mtk-hcd.ko`, and dependency modules. All were staged in `/run/cunit-usb` (tmpfs); no module or package was written to P44.

## C-unit runtime test

Loaded the matching modules in dependency order: `usb-common`, `roles`, `extcon-core`, `usbcore`, `udc-core`, `xhci-hcd`, `xhci-mtk-hcd`, and `mtu3`.

- `11201000.usb` bound to `mtu3`; the nested `11200000.xhci0` bound to `xhci-mtk`.
- The host registered two root hubs. USB2 reports 480 Mb/s; USB3 reports 20,000 Mb/s and the kernel log identifies USB 3.2 Enhanced SuperSpeed support.
- No downstream USB peripheral appeared. No device transfer, external VBUS load, or physical port test was performed. The XHCI driver reports absent `vbus`/`vusb33` regulators and falls back to dummy regulators, so port power behavior remains unverified.
- C management stayed intact: `lan2@eth1` remained `192.168.3.1/24`, default route via `192.168.3.71`, and SSH, systemd-networkd, UART getty, and Wi-Fi PHY service remained active.

## Result and persistence

Status: **USB host controller and root-hub API verified in RAM; peripheral transfer, VBUS, and reboot persistence unverified.** Modules remain loaded for this boot and reside under `/run`; reboot discards them. No eMMC/rootfs, kernel, DTB, or boot partition writes occurred. A persistent test requires staging the signed kernel's matching module set through a separate low-risk P44 write plan or enabling these features in a signed kernel candidate.
