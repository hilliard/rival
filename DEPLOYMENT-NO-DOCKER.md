# Rival Deployment Without Docker

This project supports a fully native process model for both Windows 11 development and Ubuntu 24.04 production.

## Why No Docker

- Matches your local reliability preference on Windows 11.
- Uses plain Python processes + PostgreSQL.
- Uses systemd on Ubuntu for resilience.

## Local Development (Windows 11)

1. Ensure PostgreSQL is installed and running.
2. Set values in `.env`.
3. Start stack:

```powershell
./scripts/dev-start.ps1
```

This launches:

- API process: `haynesworld-rival run-api`
- Worker process: `haynesworld-rival poll-loop`

## Production (Hostinger VPS Ubuntu 24.04)

Deploy directly on the VPS using native systemd services. No Docker, no container runtime, no Coolify orchestration — just Python, PostgreSQL, and systemd.

1. Copy this repository to `/opt/rival`.
2. Run setup script:

```bash
bash scripts/ubuntu-setup.sh /opt/rival
```

3. Create `/opt/rival/.env.production` with real values.
4. Initialize DB:

```bash
cd /opt/rival
source .venv/bin/activate
haynesworld-rival init-db
```

5. Install services:

```bash
sudo cp deploy/systemd/rival-api.service /etc/systemd/system/
sudo cp deploy/systemd/rival-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rival-api rival-worker
sudo systemctl start rival-api rival-worker
```

6. Verify:

```bash
sudo systemctl status rival-api --no-pager
sudo systemctl status rival-worker --no-pager
```

## Reverse Proxy (Recommended)

Put Nginx or Caddy in front of the API service.

- Forward HTTPS traffic to `127.0.0.1:8080`
- Restrict `/api/admin/*` to trusted operators

## Operational Commands

```bash
# logs
journalctl -u rival-api -f
journalctl -u rival-worker -f

# restart after code updates
sudo systemctl restart rival-api rival-worker
```
