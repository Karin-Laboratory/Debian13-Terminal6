#!/usr/bin/env bash
# Strict host-only 3-node SAE mesh / HWMP multi-hop test.
# Requires wmediumd to make the A-C radio link genuinely unreachable.
# Never run this on a production host with active wireless devices.
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'root required' >&2; exit 2; }
for tool in iw ip modprobe wmediumd wpa_supplicant wpa_cli ping openssl; do
    command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 2; }
done
if grep -q '^mac80211_hwsim ' /proc/modules; then
    echo 'refusing: hwsim already loaded (not owned by this test)' >&2; exit 2
fi
for phy in /sys/class/ieee80211/phy*; do
    [[ -e "$phy" ]] || continue
    echo 'refusing: existing PHY; run in an isolated hwsim-only VM' >&2; exit 2
done
if command -v pgrep >/dev/null && pgrep -x wmediumd >/dev/null; then
    echo 'refusing: wmediumd already running' >&2; exit 2
fi

umask 077
tmp=$(mktemp -d /tmp/cunit-80211s-three.XXXXXX)
tag="cmesh-${BASHPID}"
a="$tag-a"; b="$tag-b"; c="$tag-c"
mac_a=42:00:00:00:00:01
mac_b=42:00:00:00:00:02
mac_c=42:00:00:00:00:03
module_loaded=0
medium_pid=''
cleanup() {
    for node in a b c; do
        if [[ -s "$tmp/$node.pid" ]]; then
            pid=$(cat "$tmp/$node.pid")
            [[ $pid =~ ^[0-9]+$ ]] && kill "$pid" 2>/dev/null || true
        fi
    done
    [[ -z "$medium_pid" ]] || kill "$medium_pid" 2>/dev/null || true
    sleep 1
    for ns in "$a" "$b" "$c"; do ip netns del "$ns" 2>/dev/null || true; done
    if ((module_loaded)); then modprobe -r mac80211_hwsim 2>/dev/null || true; fi
    rm -rf -- "$tmp"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

modprobe mac80211_hwsim radios=3
module_loaded=1
mapfile -t phys < <(iw phy | sed -n 's/^Wiphy //p' | sort -V)
[[ ${#phys[@]} -eq 3 ]] || { echo 'expected exactly 3 virtual PHYs' >&2; exit 1; }
mapfile -t ifs < <(iw dev | awk '
    /^phy#/ {p=$0; sub("phy#", "", p)}
    /^[[:space:]]*Interface / {print p, $2}
' | sort -n -k1,1 | awk '{print $2}')
[[ ${#ifs[@]} -eq 3 ]] || { echo 'expected 3 default hwsim interfaces' >&2; exit 1; }

for ns in "$a" "$b" "$c"; do
    ip netns add "$ns"
    ip -n "$ns" link set lo up
done
for idx in 0 1 2; do
    case $idx in
        0) ns=$a; ifname=meshA; addr=$mac_a ;;
        1) ns=$b; ifname=meshB; addr=$mac_b ;;
        2) ns=$c; ifname=meshC; addr=$mac_c ;;
    esac
    iw phy "${phys[$idx]}" interface add "$ifname" type mp
    iw dev "${ifs[$idx]}" del
    iw phy "${phys[$idx]}" set netns name "$ns"
    ip -n "$ns" link set dev "$ifname" address "$addr"
    ip -n "$ns" link set dev "$ifname" up
done

# 0% loss on A-B and B-C; 100% loss on all other links, including A-C.
# https://github.com/ramonfontes/wmediumd#per-link-loss-probability-model
cat > "$tmp/medium.cfg" <<EOF
ifaces : {
    ids = [ "$mac_a", "$mac_b", "$mac_c" ];
};
model: {
    type = "prob";
    default_prob = 1.0;
    links = (
        (0, 1, 0.0),
        (1, 2, 0.0)
    );
};
EOF
wmediumd -c "$tmp/medium.cfg" >"$tmp/medium.log" 2>&1 &
medium_pid=$!
sleep 2
kill -0 "$medium_pid" || { echo 'wmediumd failed to start' >&2; exit 1; }

ssid="cunit-three-${BASHPID}"
secret=$(openssl rand -hex 16)
for node in a b c; do
    case $node in
        a) ns=$a; ifname=meshA ;;
        b) ns=$b; ifname=meshB ;;
        c) ns=$c; ifname=meshC ;;
    esac
    mkdir -m 700 "$tmp/ctrl-$node"
    cat > "$tmp/$node.conf" <<EOF
ctrl_interface=$tmp/ctrl-$node
network={
    ssid="$ssid"
    mode=5
    frequency=2437
    key_mgmt=SAE
    psk="$secret"
    mesh_fwding=1
}
EOF
    chmod 600 "$tmp/$node.conf"
    ip netns exec "$ns" wpa_supplicant -B -dd -Dnl80211 -i "$ifname" \
        -c "$tmp/$node.conf" -f "$tmp/$node.log" -P "$tmp/$node.pid"
done
unset secret

# SAE peer establishment: edge nodes must have B as their only peer.
# Requiring B's two established peers also proves a non-trivial topology.
edge_ready=0
for _ in $(seq 1 90); do
    kill -0 "$medium_pid" || { echo 'wmediumd exited unexpectedly' >&2; exit 1; }
    pa=$(ip netns exec "$a" iw dev meshA station dump 2>/dev/null || true)
    pb=$(ip netns exec "$b" iw dev meshB station dump 2>/dev/null || true)
    pc=$(ip netns exec "$c" iw dev meshC station dump 2>/dev/null || true)
    if grep -iq "$mac_b" <<<"$pa" &&
       grep -iq "$mac_a" <<<"$pb" &&
       grep -iq "$mac_c" <<<"$pb" &&
       grep -iq "$mac_b" <<<"$pc" &&
       ! grep -iq "$mac_c" <<<"$pa" &&
       ! grep -iq "$mac_a" <<<"$pc" &&
       grep -q 'MESH-PEER-CONNECTED' "$tmp/a.log" &&
       grep -q 'MESH-PEER-CONNECTED' "$tmp/b.log" &&
       grep -q 'MESH-PEER-CONNECTED' "$tmp/c.log" &&
       grep -q 'mesh plink:.*ESTAB' <<<"$pa" &&
       grep -q 'mesh plink:.*ESTAB' <<<"$pc"; then
        edge_ready=1; break
    fi
    sleep 1
done
((edge_ready)) || { echo 'FAIL: no isolated A-B-C established mesh' >&2; exit 1; }
echo 'HWSIM_3NODE_SAE_CONFIGURED_PEERING=PASS'
echo 'HWSIM_AC_DIRECT_PEER_ABSENT=PASS'
echo 'HWSIM_MEDIUM_AC_LOSS=100_PERCENT_CONFIGURED'

ip -n "$a" addr add 10.253.16.1/24 dev meshA
ip -n "$b" addr add 10.253.16.2/24 dev meshB
ip -n "$c" addr add 10.253.16.3/24 dev meshC
ip netns exec "$a" ping -c 5 -W 2 10.253.16.3 > "$tmp/ping-ac"
ip netns exec "$c" ping -c 5 -W 2 10.253.16.1 > "$tmp/ping-ca"
echo 'HWSIM_3NODE_BIDIRECTIONAL_IP=PASS'

# A's HWMP destination C MUST use B as next hop; reverse must use B.
path_a=$(ip netns exec "$a" iw dev meshA mpath dump)
path_c=$(ip netns exec "$c" iw dev meshC mpath dump)
grep -Eiq "^$mac_c[[:space:]]+$mac_b[[:space:]]" <<<"$path_a" ||
    { echo 'FAIL: HWMP A->C next hop is not B' >&2; exit 1; }
grep -Eiq "^$mac_a[[:space:]]+$mac_b[[:space:]]" <<<"$path_c" ||
    { echo 'FAIL: HWMP C->A next hop is not B' >&2; exit 1; }
echo 'HWSIM_HWMP_AC_VIA_B=PASS'

# Distinguish automatic peer/HWMP reconvergence from userspace-initiated rejoin.
links_ready() {
    local pa pb pc
    pa=$(ip netns exec "$a" iw dev meshA station dump 2>/dev/null || true)
    pb=$(ip netns exec "$b" iw dev meshB station dump 2>/dev/null || true)
    pc=$(ip netns exec "$c" iw dev meshC station dump 2>/dev/null || true)
    grep -iq "$mac_b" <<<"$pa" &&
        grep -iq "$mac_a" <<<"$pb" &&
        grep -iq "$mac_c" <<<"$pb" &&
        grep -iq "$mac_b" <<<"$pc" &&
        grep -q 'mesh plink:.*ESTAB' <<<"$pa" &&
        grep -q 'mesh plink:.*ESTAB' <<<"$pc" &&
        [[ $(grep -c 'mesh plink:.*ESTAB' <<<"$pb") -ge 2 ]]
}
paths_ready() {
    local pa pc
    pa=$(ip netns exec "$a" iw dev meshA mpath dump 2>/dev/null || true)
    pc=$(ip netns exec "$c" iw dev meshC mpath dump 2>/dev/null || true)
    grep -Eiq "^$mac_c[[:space:]]+$mac_b[[:space:]]" <<<"$pa" &&
        grep -Eiq "^$mac_a[[:space:]]+$mac_b[[:space:]]" <<<"$pc"
}
wait_recovery() {
    local attempts=$1 n
    for ((n=0; n<attempts; n++)); do
        kill -0 "$medium_pid" 2>/dev/null || return 1
        if links_ready &&
           ip netns exec "$a" ping -n -c 1 -W 1 10.253.16.3 >/dev/null 2>&1 &&
           ip netns exec "$c" ping -n -c 1 -W 1 10.253.16.1 >/dev/null 2>&1 &&
           paths_ready; then
            return 0
        fi
        sleep 1
    done
    return 1
}
recovery_diag() {
    local item ns iface state peers established
    for item in a b c; do
        case $item in
            a) ns=$a; iface=meshA ;;
            b) ns=$b; iface=meshB ;;
            c) ns=$c; iface=meshC ;;
        esac
        state=$(ip netns exec "$ns" wpa_cli -p "$tmp/ctrl-$item" -i "$iface" status 2>/dev/null |
                grep '^wpa_state=' || true)
        peers=$(ip netns exec "$ns" iw dev "$iface" station dump 2>/dev/null |
                grep -c '^Station ' || true)
        established=$(ip netns exec "$ns" iw dev "$iface" station dump 2>/dev/null |
                      grep -c 'mesh plink:.*ESTAB' || true)
        [[ -n "$state" ]] || state=unknown
        echo "HWSIM_DIAG_$item=$state peers:$peers estab:$established" >&2
    done
}
ip -n "$b" link set meshB down
sleep 3
if ip netns exec "$a" ping -n -c 3 -W 1 10.253.16.3 >/dev/null 2>&1; then
    echo 'FAIL: A-C remains reachable with B down' >&2; exit 1
fi
echo 'HWSIM_B_DOWN_AC_UNREACHABLE=PASS'
recovery_started_ms=$(date +%s%3N)
ip -n "$b" link set meshB up
recovered=0
recovery_mode=NONE
# Phase 1: no intervention after netdev UP.
if wait_recovery 20; then
    echo 'HWSIM_B_AUTO_RECOVERY=PASS'
    recovery_mode=AUTO
    recovered=1
else
    echo 'HWSIM_B_AUTO_RECOVERY=FAIL'
    recovery_diag
fi
# Phase 2: wpa_cli reconnect (may not rejoin an already-started mesh).
if (( ! recovered )); then
    action=$(ip netns exec "$b" wpa_cli -p "$tmp/ctrl-b" -i meshB reconnect 2>/dev/null || true)
    echo "HWSIM_B_WPA_CLI_RECONNECT=$action"
    if [[ $action == OK ]] && wait_recovery 12; then
        echo 'HWSIM_B_WPA_CLI_RECOVERY=PASS'
        recovery_mode=WPA_CLI_RECONNECT
        recovered=1
    else
        echo 'HWSIM_B_WPA_CLI_RECOVERY=FAIL'
        recovery_diag
    fi
fi
# Phase 3: existing upstream wpa_supplicant network lifecycle (leave/join).
# Its result must not be called automatic recovery.
if (( ! recovered )); then
    disabled=$(ip netns exec "$b" wpa_cli -p "$tmp/ctrl-b" -i meshB disable_network 0 2>/dev/null || true)
    enabled=$(ip netns exec "$b" wpa_cli -p "$tmp/ctrl-b" -i meshB enable_network 0 2>/dev/null || true)
    echo "HWSIM_B_NETWORK_REJOIN_COMMANDS=disable:$disabled enable:$enabled"
    if [[ $disabled == OK && $enabled == OK ]]; then
        ip -n "$b" link set meshB up
        if wait_recovery 40; then
            echo 'HWSIM_B_NETWORK_REJOIN=PASS'
            recovery_mode=ASSISTED_B_NETWORK_REJOIN
            recovered=1
        fi
    fi
    if (( ! recovered )); then
        echo 'HWSIM_B_NETWORK_REJOIN=FAIL'
        recovery_diag
    fi
fi
if (( ! recovered )); then
    echo 'FAIL: neither auto nor explicit B rejoin restored 3-node HWMP' >&2
    exit 1
fi
echo "HWSIM_B_RECOVERY_MODE=$recovery_mode"
echo "HWSIM_B_RECOVERY_MS=$(($(date +%s%3N) - recovery_started_ms))"
links_ready && paths_ready || { echo 'FAIL: recovered HWMP/peering regressed' >&2; exit 1; }
echo 'HWSIM_B_RECOVERY_HWMP=PASS'

ip netns exec "$a" ping -c 20 -i 0.1 -W 2 10.253.16.3 > "$tmp/metrics"
grep -E 'packet loss|rtt min/avg/max|round-trip min/avg/max' "$tmp/metrics"
echo 'HWSIM_LATENCY_LOSS=MEASURED_ABOVE'
echo 'HWSIM_SAE=CONFIGURED_AND_PEERING_OBSERVED'
echo 'HWSIM_AMPE_FRAME_PROTECTION=NOT_INDEPENDENTLY_VERIFIED'
echo 'HWSIM_REBOOT_PERSISTENCE=NOT_TESTED'
echo 'HWSIM_SCOPE=HOST_SYNTHETIC_ONLY'
