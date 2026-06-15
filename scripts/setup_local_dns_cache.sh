#!/usr/bin/env bash

# Install a host-local Unbound cache for Docker containers.
# Containers send DNS to docker0; Unbound forwards upstream over TCP only.

set -euo pipefail

DNS_LISTEN_IP="${DNS_LISTEN_IP:-172.17.0.1}"
UNBOUND_CONFIG="/etc/unbound/unbound.conf.d/expense-bot-docker.conf"
UNBOUND_DROPIN="/etc/systemd/system/unbound.service.d/expense-bot-docker.conf"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo bash scripts/setup_local_dns_cache.sh"
    exit 1
fi

if ! ip -4 address show docker0 | grep -q "inet ${DNS_LISTEN_IP}/"; then
    echo "docker0 does not own ${DNS_LISTEN_IP}; refusing to install a broken DNS listener."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y unbound dnsutils

install -d -m 0755 "$(dirname "$UNBOUND_CONFIG")"
install -d -m 0755 "$(dirname "$UNBOUND_DROPIN")"

cat > "$UNBOUND_CONFIG" <<EOF
server:
    interface: ${DNS_LISTEN_IP}
    port: 53

    access-control: 127.0.0.0/8 allow
    access-control: 172.16.0.0/12 allow
    access-control: 0.0.0.0/0 refuse

    do-ip4: yes
    do-ip6: no
    do-udp: yes
    do-tcp: yes

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
    forward-tcp-upstream: yes
EOF

cat > "$UNBOUND_DROPIN" <<'EOF'
[Unit]
After=docker.service
Requires=docker.service
EOF

unbound-checkconf
systemctl daemon-reload
systemctl enable unbound
systemctl restart unbound

dig +time=3 +tries=1 "@${DNS_LISTEN_IP}" api.telegram.org A >/dev/null
dig +tcp +time=3 +tries=1 "@${DNS_LISTEN_IP}" api.telegram.org A >/dev/null

echo "Local Docker DNS cache is ready on ${DNS_LISTEN_IP}:53."
