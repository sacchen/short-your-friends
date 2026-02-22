# Server operations cheatsheet

Minimal commands for running and operating the Python backend remotely.

## Assumptions
- Host alias: `exchange` (or replace with your host)
- App path on host: `~/python-prototype`
- Service name: `exchange`

## Deploy

```bash
rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude 'state.json' \
  python-prototype/ exchange:~/python-prototype/

ssh exchange 'sudo systemctl restart exchange'
```

## Service management

```bash
ssh exchange 'sudo systemctl status exchange'
ssh exchange 'sudo systemctl restart exchange'
ssh exchange 'journalctl -u exchange -n 100 --no-pager'
ssh exchange 'journalctl -u exchange -f'
```

## Health checks

```bash
nc -zv <server-ip> 8888
ssh exchange 'ss -tlnp | grep 8888'
```

## Troubleshooting
- Connection refused:
  - confirm service is running
  - confirm port `8888` is listening
  - confirm firewall rules allow TCP `8888`
- Service crash:
  - inspect `journalctl` logs
  - restart service after fixing config/runtime error
