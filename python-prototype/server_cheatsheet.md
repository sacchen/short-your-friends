# Order Book Server Cheatsheet

## Server Info
- **IP:** `<YOUR_DROPLET_IP>` # in .env file
- **User:** `root`
- **Port:** `8888`
- **Service Name:** `exchange`
- **Project Path:** `/root/python-prototype/`
- **Local Path:** `/Users/goddess/foundry/sandbox/order-book-global/short-your-friends/python-prototype/`
- **SSH Alias:** `exchange`

---

## Deployment

### Quick Deploy (One Command)
```bash
rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  --exclude '.pytest_cache' \
  --exclude 'state.json' \
  --exclude '*.log' \
  /Users/goddess/foundry/sandbox/order-book-global/short-your-friends/python-prototype/ \
  exchange:~/python-prototype/ && \
ssh exchange 'sudo systemctl restart exchange'
```

### Deploy Alias Setup (Add to ~/.zshrc)
```bash
# Add this to your ~/.zshrc file:
alias deploy-exchange="rsync -avz --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' \
  --exclude '.pytest_cache' --exclude 'state.json' --exclude '*.log' \
  /Users/goddess/foundry/sandbox/order-book-global/short-your-friends/python-prototype/ \
  exchange:~/python-prototype/ && \
  ssh exchange 'sudo systemctl restart exchange' && \
  echo '[+] Deployed!'"

# Then reload your shell:
# source ~/.zshrc
```

### Quick Setup for Deploy Alias
```bash
cat >> ~/.zshrc << 'EOF'

# Deploy order book exchange server
alias deploy-exchange="rsync -avz --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' \
  --exclude '.pytest_cache' --exclude 'state.json' --exclude '*.log' \
  /Users/goddess/foundry/sandbox/order-book-global/short-your-friends/python-prototype/ \
  exchange:~/python-prototype/ && \
  ssh exchange 'sudo systemctl restart exchange' && \
  echo '[+] Deployed!'"
EOF

source ~/.zshrc
```

---

## 🎮 Service Management (systemd)

### Check Status
```bash
ssh exchange 'sudo systemctl status exchange'
```

### Start/Stop/Restart
```bash
ssh exchange 'sudo systemctl start exchange'
ssh exchange 'sudo systemctl stop exchange'
ssh exchange 'sudo systemctl restart exchange'
```

### Enable/Disable (Auto-start on boot)
```bash
ssh exchange 'sudo systemctl enable exchange'
ssh exchange 'sudo systemctl disable exchange'
```

### Reload Config (without restart)
```bash
ssh exchange 'sudo systemctl reload exchange'
```

---

## Logs

### View Recent Logs
```bash
ssh exchange 'journalctl -u exchange -n 50 --no-pager'
```

### Follow Live Logs (Real-time)
```bash
ssh exchange 'journalctl -u exchange -f'
```

### View Logs Since Boot
```bash
ssh exchange 'journalctl -u exchange -b'
```

### View Logs from Today
```bash
ssh exchange 'journalctl -u exchange --since today'
```

### View Logs with Timestamps
```bash
ssh exchange 'journalctl -u exchange -n 100'
```

---

## Debugging & Monitoring

### Check if Server is Running
```bash
ssh exchange 'ps aux | grep server.py'
```

### Check if Port is Listening
```bash
ssh exchange 'netstat -tlnp | grep 8888'
# or
ssh exchange 'ss -tlnp | grep 8888'
```

### Test Connection from Mac
```bash
nc -zv <YOUR_DROPLET_IP> 8888
# or
telnet <YOUR_DROPLET_IP> 8888
```

### Check Firewall Status
```bash
ssh exchange 'sudo ufw status'
```

### View Server State File
```bash
ssh exchange 'cat ~/python-prototype/state.json | jq'
```

### Watch State File (Live Updates)
```bash
ssh exchange 'watch -n 1 "cat ~/python-prototype/state.json | jq"'
```

---

## 📁 File Operations

### SSH into Server
```bash
ssh exchange
```

### View Server Files
```bash
ssh exchange 'ls -la ~/python-prototype/'
```

### Edit Server File (via SSH)
```bash
ssh exchange 'nano ~/python-prototype/server.py'
```

### Download File from Server
```bash
scp exchange:~/python-prototype/state.json ~/Downloads/
```

### Upload Single File to Server
```bash
scp /path/to/local/file.py exchange:~/python-prototype/
```

---

## Testing

### Run Tests Locally
```bash
cd /Users/goddess/foundry/sandbox/order-book-global/short-your-friends/python-prototype
uv run pytest
```

### Run Specific Test
```bash
uv run pytest tests/test_discovery.py
```

### Test Against Live Server
```bash
# Make sure test_discovery.py has: host = "<YOUR_DROPLET_IP>"
uv run pytest tests/test_discovery.py -v
```

---

## Common Issues & Fixes

### Connection Refused
```bash
# 1. Check if service is running
ssh exchange 'sudo systemctl status exchange'

# 2. Check if port is open
ssh exchange 'sudo ufw status'

# 3. Check firewall
ssh exchange 'sudo ufw allow 8888'
```

### Service Won't Start
```bash
# Check detailed error logs
ssh exchange 'journalctl -u exchange -n 100 --no-pager'

# Check Python path
ssh exchange 'which python3'
ssh exchange 'which uv'
```

### Code Changes Not Reflecting
```bash
# 1. Deploy again
deploy-exchange  # or use full rsync command

# 2. Restart service
ssh exchange 'sudo systemctl restart exchange'

# 3. Verify logs show restart
ssh exchange 'journalctl -u exchange -n 20'
```

### Server Crashed
```bash
# Check crash logs
ssh exchange 'journalctl -u exchange --since "1 hour ago"'

# Restart (systemd should auto-restart, but manual restart helps)
ssh exchange 'sudo systemctl restart exchange'
```

---

## Quick Status Check

### One-Liner Health Check
```bash
ssh exchange 'echo "=== Service Status ===" && \
sudo systemctl is-active exchange && \
echo "=== Port Check ===" && \
ss -tlnp | grep 8888 && \
echo "=== Recent Logs ===" && \
journalctl -u exchange -n 5 --no-pager'
```

---

## Security Notes

- Server runs as `root` (consider creating dedicated user later)
- Firewall: Port 22 (SSH) and 8888 (Exchange) are open
- State file: `~/python-prototype/state.json` contains user balances
- Logs: Check `journalctl` for any suspicious activity

---

## Pro Tips

1. **Always check logs after deploying** to catch errors early
2. **Keep state.json backed up** before major changes
3. **Use `-f` flag for logs** to watch real-time during testing
4. **Test locally first** before deploying to production
5. **Monitor system resources** if server seems slow:
   ```bash
   ssh exchange 'htop'
   ```

---

## Quick Reference

| Task | Command |
|------|---------|
| Deploy | `deploy-exchange` (after setup) |
| Restart | `ssh exchange 'sudo systemctl restart exchange'` |
| View Logs | `ssh exchange 'journalctl -u exchange -f'` |
| Check Status | `ssh exchange 'sudo systemctl status exchange'` |
| Test Connection | `nc -zv <YOUR_DROPLET_IP> 8888` |
| SSH In | `ssh exchange` |

## My notes
**Local testing**
Terminal 1: Start your local server
`server`

Terminal 2: Run all tests
`uv run pytest`

**Run test against your remote droplet**
`TEST_SERVER_HOST=<YOUR_DROPLET_IP> uv run pytest`