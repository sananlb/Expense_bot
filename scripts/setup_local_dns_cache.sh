#!/usr/bin/env bash

# Install a host-local Unbound cache for Docker containers.
# A dedicated dummy interface avoids Docker's own DNS handling on bridge IPs.

set -euo pipefail

DNS_LISTEN_IP="${DNS_LISTEN_IP:-10.255.255.53}"
DNS_INTERFACE="${DNS_INTERFACE:-expensebot-dns}"
UNBOUND_CONFIG="/etc/unbound/unbound.conf.d/expense-bot-docker.conf"
UNBOUND_DROPIN="/etc/systemd/system/unbound.service.d/expense-bot-docker.conf"
ADDRESS_SERVICE="/etc/systemd/system/expensebot-dns-address.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo bash scripts/setup_local_dns_cache.sh"
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y unbound dnsutils

install -d -m 0755 "$(dirname "$UNBOUND_CONFIG")"
install -d -m 0755 "$(dirname "$UNBOUND_DROPIN")"

cat > "$ADDRESS_SERVICE" <<EOF
[Unit]
Description=Dedicated local address for Expense Bot DNS cache
Before=unbound.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'ip link show ${DNS_INTERFACE} >/dev/null 2>&1 || ip link add ${DNS_INTERFACE} type dummy; ip -4 address show dev ${DNS_INTERFACE} | grep -q "${DNS_LISTEN_IP}/32" || ip address add ${DNS_LISTEN_IP}/32 dev ${DNS_INTERFACE}; ip link set ${DNS_INTERFACE} up'
ExecStop=/bin/sh -c 'ip link delete ${DNS_INTERFACE} 2>/dev/null || true'

[Install]
WantedBy=multi-user.target
EOF

cat > "$UNBOUND_CONFIG" <<EOF
server:
    interface: ${DNS_LISTEN_IP}
    port: 53

    access-control: ${DNS_LISTEN_IP}/32 allow
    access-control: 172.16.0.0/12 allow
    access-control: 0.0.0.0/0 refuse

    do-ip4: yes
    do-ip6: no
    do-udp: yes
    do-tcp: yes
    tcp-upstream: yes

    cache-min-ttl: 60
    cache-max-ttl: 86400
    prefetch: yes
    serve-expired: yes
    serve-expired-ttl: 86400

    hide-identity: yes
    hide-version: yes

forward-zone:
    name: "."
    forward-addr: 1.1.1.1
    forward-addr: 8.8.8.8
EOF

cat > "$UNBOUND_DROPIN" <<'EOF'
[Unit]
After=expensebot-dns-address.service
Requires=expensebot-dns-address.service
EOF

unbound-checkconf
systemctl daemon-reload
systemctl enable --now expensebot-dns-address.service
systemctl enable unbound
systemctl restart unbound

dig +time=3 +tries=1 "@${DNS_LISTEN_IP}" api.telegram.org A >/dev/null
dig +tcp +time=3 +tries=1 "@${DNS_LISTEN_IP}" api.telegram.org A >/dev/null

echo "Local Docker DNS cache is ready on ${DNS_LISTEN_IP}:53."
