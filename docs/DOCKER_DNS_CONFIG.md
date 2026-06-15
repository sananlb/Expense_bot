# Docker DNS Configuration

## Problem

Direct UDP queries from Docker containers to public resolvers can intermittently
time out:

```text
Cannot connect to host api.telegram.org:443 ssl:default
[Temporary failure in name resolution]
```

The production setup uses a host-local Unbound cache instead:

- the setup creates a dedicated dummy interface at `10.255.255.53`;
- Unbound listens only on that host-local address;
- containers use `10.255.255.53` as their DNS server;
- cached answers remain available during short upstream failures;
- upstream requests to `1.1.1.1` and `8.8.8.8` use TCP, avoiding the observed
  UDP/53 packet loss.

Docker bridge addresses are deliberately not used because Docker handles DNS
traffic specially on those interfaces.

## Installation

```bash
cd /home/batman/expense_bot
sudo bash scripts/setup_local_dns_cache.sh
```

The script validates the `docker0` address, installs Unbound, writes the scoped
configuration, validates it with `unbound-checkconf`, and runs UDP/TCP lookups.

## Container Configuration

Application services in `docker-compose.yml` use:

```yaml
dns:
  - 10.255.255.53
```

Recreate application containers after changing DNS settings:

```bash
docker compose up -d --no-deps --force-recreate bot celery celery-beat web
```

## Verification

```bash
sudo systemctl status unbound --no-pager
dig @10.255.255.53 api.telegram.org
docker exec expense_bot_celery getent hosts api.telegram.org
sudo journalctl -u docker --since "15 minutes ago" --no-pager \
  | grep "failed to query external DNS server"
```

No Docker daemon restart is required.
