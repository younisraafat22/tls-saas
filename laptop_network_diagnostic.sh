#!/usr/bin/env bash
# TLS laptop network diagnostics (safe, read-only except optional --fix mode)
set -u

MODE="diag"
if [[ "${1:-}" == "--fix" ]]; then
  MODE="fix"
fi

TS="$(date +%Y%m%d_%H%M%S)"
OUT="/tmp/tls_laptop_network_${TS}.log"

log() {
  echo "\n===== $1 =====" | tee -a "$OUT"
}

run() {
  echo "$ $*" | tee -a "$OUT"
  "$@" 2>&1 | tee -a "$OUT"
}

echo "Writing diagnostics to: $OUT"

log "SYSTEM"
run uname -a
run hostnamectl
run bash -lc 'cat /etc/os-release'

log "NETWORK SERVICES"
run systemctl is-active NetworkManager
run systemctl is-enabled NetworkManager
run systemctl is-active systemd-networkd
run systemctl is-active wpa_supplicant

log "NMCLI OVERVIEW"
run nmcli general status
run nmcli device status
run nmcli radio all
run nmcli connection show --active

log "ADAPTER VISIBILITY"
run ip -br link
run ip -br addr
run rfkill list all
run bash -lc 'ls -l /sys/class/net'

log "PCI/USB NETWORK DEVICES"
run bash -lc "lspci -nnk | grep -A4 -Ei 'network|wireless|wifi|ethernet'"
run lsusb

log "DRIVER/MODULE STATUS"
run bash -lc "lsmod | grep -Ei 'iwlwifi|rtw|rtl|ath|mt76|brcm|r8169|r8168|e1000e|igc|tg3'"

log "ROUTING/DNS"
run ip route
run resolvectl status

log "KERNEL / NETWORK LOGS"
run bash -lc "dmesg -T | grep -Ei 'iwlwifi|wlan|wifi|wlp|firmware|r8169|eth|NetworkManager' | tail -n 250"
run journalctl -b -u NetworkManager --no-pager -n 250

if [[ "$MODE" == "fix" ]]; then
  log "SAFE NETWORK STACK RESET"
  run sudo rfkill unblock all
  run sudo systemctl restart NetworkManager
  run nmcli networking on
  run nmcli radio wifi on

  # Try DHCP renew on all non-loopback interfaces that are UP or UNKNOWN
  for IFACE in $(ip -o link show | awk -F': ' '{print $2}' | cut -d'@' -f1 | grep -v '^lo$'); do
    STATE=$(cat "/sys/class/net/${IFACE}/operstate" 2>/dev/null || echo "unknown")
    echo "Interface ${IFACE} state=${STATE}" | tee -a "$OUT"
    if [[ "$STATE" == "up" || "$STATE" == "unknown" ]]; then
      echo "$ sudo dhclient -v ${IFACE}" | tee -a "$OUT"
      sudo dhclient -v "$IFACE" 2>&1 | tee -a "$OUT" || true
    fi
  done

  log "POST-FIX STATUS"
  run nmcli device status
  run ip -br addr
  run ip route
fi

echo "\nDone. Share this file output:" | tee -a "$OUT"
echo "$OUT" | tee -a "$OUT"
