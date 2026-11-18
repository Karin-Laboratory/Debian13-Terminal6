# C号機 IEEE 802.11s 第3段階: 実通信と再現性の受入証拠 (2026-11-16)

## 判定

- **HOST 3-NODE ASSISTED RECOVERY: PASS / 3 of 3 independent disposable VMs.** mac80211_hwsim + pinned upstream wmediumd + stock wpa_supplicant; **not C-unit hardware**.
- **AUTOMATIC RECOVERY: FAIL / 3 of 3.** Merely bringing B's netdev UP leaves B wpa_state=SCANNING with zero peers; `wpa_cli reconnect` and `disable_network`/`enable_network` each returned OK but did not restore forwarding within their bounded windows.
- **UPSTREAM MESH GROUP REJOIN: PASS / 3 of 3.** On B only, `wpa_cli mesh_group_remove meshB` followed by `wpa_cli mesh_group_add 0` returns OK; secured-mesh-configured peers re-establish, A↔C bidirectional IP returns, and both HWMP routes use B.
- **CRYPTOGRAPHIC AMPE FRAME PROTECTION: NOT INDEPENDENTLY VERIFIED.** The tests observe SAE configuration and mesh peering, not an authenticated PCAP-level AMPE proof.
- **REAL PRIVATE SOURCE REPLAY / REPRODUCIBLE ARM64 BUILD: BLOCKED.** The synthetic source reconstruction/unit tests pass, but the real owner-private MT6990 source and lawful vendor patch provenance were unavailable to this execution environment. No new validated independent Image/modules.
- **C-UNIT INTEGRATION: RUNBOOK ONLY.** No access to physical A/C devices, no device flashing, 6GHz RF, MLO, EasyMesh or PR #6/#9 writes.

## GitHub Actions実証

- Historical [run 43784875228](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43784875228) reached A↔C forwarding through B, but B rejoin failed. The run was deceptively green because `tee` hid a failed shell exit. The workflow is now `set -euo pipefail` and checks explicit pass tokens.
- [Run 43786743042](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43786743042) correctly FAILED with B remaining in SCANNING, peers=0 after automatic, reconnect and disable/enable attempts.
- [Run 43787002837](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43787002837) SUCCEEDED after explicit upstream mesh_group_remove/add. Recovery total 75.252 s including prior failed bounded attempts; 20/20 pings delivered, average RTT 2.802 ms.
- [Independent 3-VM run 43787300664](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43787300664) SUCCEEDED for all three trials. Each new VM independently checked A-B/B-C peering, absence of A-C direct link, reciprocal HWMP via B, A↔C IP, loss during B DOWN, B rejoin, recovered IP/path and ping metrics.
- [Host check run 43787300687](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43787300687) SUCCEEDED. Earlier source-replay unit suite was 9/9 synthetic PASS, which does not prove real vendor replay.

| Independent trial | B auto recovery | B `reconnect` | B `disable/enable` | B mesh remove/add | Total time after B UP | 20-packet loss | RTT avg |
|---|---|---|---|---|---:|---:|---:|
| 1 | FAIL | FAIL | FAIL | PASS | 74.868 s | 0% | 2.938 ms |
| 2 | FAIL | FAIL | FAIL | PASS | 75.851 s | 0% | 1.778 ms |
| 3 | FAIL | FAIL | FAIL | PASS | 75.069 s | 0% | 2.528 ms |

Total recovery time above is deliberately **not** the mesh rejoin latency alone: it includes ~20 s auto trial, ~12 s reconnect trial and ~40 s disable/enable trial before the final remove/add. In the first successful run the final mesh rejoin completed in about 2 s; the three repeat trials showed the same order of magnitude. These are virtual-host measurements, not RF/MT7990 hardware throughput.

## 受入境界と次工程

1. The established hwsim 3-node result is **assisted B recovery PASS**, not autonomous B recovery PASS. If unconditional auto recovery is required, inspect wpa_supplicant's mesh leave/join lifecycle and netdev DOWN/UP notifications to fix the trigger, without implementing a new mesh/HWMP/SAE stack.
2. Verify AMPE frame protection independently using a lawful hwsim capture and an explicit Protected-frame + SAE/AMPE acceptance rule, keeping handshake material or randomized passphrases private.
3. On the owner's private build host, reconstruct `Linux 6.18.63 upstream + private MT6990 vendor/board patch + PR #9 OTP/EEPROM patch`, require full per-file SHA256 source replay before an independent ARM64 Image/modules build. Record compiler/config/outputs hashes privately; content match alone is not proof of redistribution rights.
4. For physical C integration, follow [minimum-diff gated runbook](CUNIT-80211S-REPLAY-HWSIM3-20261116.ja.md), preserve eMMC 100MHz/CQE-disabled, management LAN/SSH/UART and the PR #6 handoff, and avoid 6GHz transmission/320MHz.

## 実装

- [3-node hwsim script](../../scripts/run_80211s_hwsim_3node.sh)
- [Repeatable CI workflow](../../.github/workflows/cunit-80211s-hwsim-live.yml)
- [Private source reconstruction tool](../../scripts/reconstruct_80211s_vendor_patch.py)
- [Fail-closed kernel replay tool](../../scripts/replay_80211s_kernel_source.py)
