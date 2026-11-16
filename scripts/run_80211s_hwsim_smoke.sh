#!/usr/bin/env bash
# Host-only 2-node SAE mesh smoke test using virtual radios; never touches real RF.
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'run as root (e.g. sudo)' >&2; exit 2; }
IW=${IW:-iw}
IP=${IP:-ip}
MODPROBE=${MODPROBE:-modprobe}
RMMOD=${RMMOD:-modprobe}
WPA_SUPPLICANT=${WPA_SUPPLICANT:-wpa_supplicant}
WPA_CLI=${WPA_CLI:-wpa_cli}
for tool in "$IW" "$IP" "$MODPROBE" "$WPA_SUPPLICANT" "$WPA_CLI" openssl; do
    command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 2; }
done

if grep -q '^mac80211_hwsim ' /proc/modules; then
    echo 'refusing: mac80211_hwsim is already loaded; test would not own its radios' >&2
    exit 2
fi
for phy in /sys/class/ieee80211/phy*; do
    [[ -e $phy ]] || continue
    driver=$(basename "$(readlink -f "$phy/device/driver" 2>/dev/null || true)")
    [[ $driver == mac80211_hwsim ]] || {
        echo 'refusing: a non-hwsim wireless phy exists' >&2
        exit 2
    }
done

umask 077
tmp=$(mktemp -d /tmp/cunit-80211s-hwsim.XXXXXX)
ns_a="mesh-a-${BASHPID}"
ns_b="mesh-b-${BASHPID}"
module_loaded=0
cleanup() {
    for pidfile in "$tmp/a.pid" "$tmp/b.pid"; do
        if [[ -s $pidfile ]]; then
            pid=$(cat "$pidfile")
            [[ $pid =~ ^[0-9]+$ ]] && kill "$pid" >/dev/null 2>&1 || true
        fi
    done
    sleep 1
    "$IP" netns del "$ns_a" >/dev/null 2>&1 || true
    "$IP" netns del "$ns_b" >/dev/null 2>&1 || true
    if (( module_loaded )); then
        "$RMMOD" -r mac80211_hwsim >/dev/null 2>&1 || true
    fi
    rm -rf -- "$tmp"
}
trap cleanup EXIT INT TERM

"$MODPROBE" mac80211_hwsim radios=2
module_loaded=1
mapfile -t phys < <("$IW" phy | sed -n 's/^Wiphy //p' | sort -V)
[[ ${#phys[@]} -eq 2 ]] || { echo 'expected exactly two virtual phys' >&2; exit 1; }
mapfile -t ifs < <("$IW" dev | awk '
    /^phy#/ { p=$0; sub("phy#", "", p) }
    /^[[:space:]]*Interface / { print p, $2 }
' | sort -n -k1,1 | awk '{print $2}')
[[ ${#ifs[@]} -eq 2 ]] || { echo 'expected exactly two default hwsim interfaces' >&2; exit 1; }

"$IP" netns add "$ns_a"
"$IP" netns add "$ns_b"
"$IW" phy "${phys[0]}" interface add meshA type mp
"$IW" phy "${phys[1]}" interface add meshB type mp
for iface in "${ifs[@]}"; do "$IW" dev "$iface" del; done
"$IW" phy "${phys[0]}" set netns name "$ns_a"
"$IW" phy "${phys[1]}" set netns name "$ns_b"
"$IP" -n "$ns_a" link set lo up
"$IP" -n "$ns_b" link set lo up
"$IP" -n "$ns_a" link set meshA up
"$IP" -n "$ns_b" link set meshB up

ssid="cunit-mesh-${BASHPID}"
passphrase=$(openssl rand -hex 16)
mkdir -m 700 "$tmp/ctrl-a" "$tmp/ctrl-b"
for node in a b; do
    iface=meshA; ns=$ns_a; ctrl="$tmp/ctrl-a"; log="$tmp/a.log"
    [[ $node == b ]] && { iface=meshB; ns=$ns_b; ctrl="$tmp/ctrl-b"; log="$tmp/b.log"; }
    cat > "$tmp/$node.conf" <<EOF
ctrl_interface=$ctrl
network={
    ssid="$ssid"
    mode=5
    frequency=2437
    key_mgmt=SAE
    psk="$passphrase"
    mesh_fwding=1
}
EOF
    chmod 600 "$tmp/$node.conf"
    "$IP" netns exec "$ns" "$WPA_SUPPLICANT" -B -dd -Dnl80211 -i "$iface" \
        -c "$tmp/$node.conf" -f "$log" -P "$tmp/$node.pid"
done

ready=0
for _ in $(seq 1 60); do
    status_a=$("$IP" netns exec "$ns_a" "$WPA_CLI" -p "$tmp/ctrl-a" -i meshA status 2>/dev/null || true)
    status_b=$("$IP" netns exec "$ns_b" "$WPA_CLI" -p "$tmp/ctrl-b" -i meshB status 2>/dev/null || true)
    if grep -q '^wpa_state=COMPLETED$' <<<"$status_a" &&
       grep -q '^wpa_state=COMPLETED$' <<<"$status_b" &&
       grep -q 'MESH-PEER-CONNECTED' "$tmp/a.log" &&
       grep -q 'MESH-PEER-CONNECTED' "$tmp/b.log"; then
        ready=1
        break
    fi
    sleep 1
done
if (( ! ready )); then
    echo '80211S_SAE_PEERING_FAIL' >&2
    exit 1
fi

"$IP" -n "$ns_a" addr add 10.253.15.1/24 dev meshA
"$IP" -n "$ns_b" addr add 10.253.15.2/24 dev meshB
"$IP" netns exec "$ns_a" ping -c 3 -W 2 10.253.15.2 >/dev/null
"$IP" netns exec "$ns_b" ping -c 3 -W 2 10.253.15.1 >/dev/null

echo 'HWSIM_80211S_SAE_CONFIGURED_PEERING=PASS'
echo 'HWSIM_BIDIRECTIONAL_IP=PASS'
echo "HWSIM_FREQ_MHZ=2437"
echo 'HWSIM_TOPOLOGY=2-node virtual-radio; multi-hop not tested'
