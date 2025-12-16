# Quiz App Deployment Guide

## Overview

- **App URL**: https://app.fatbigquiz.com
- **Server IP**: 157.245.42.21
- **Stack**: Flask + PostgreSQL + Nginx (all in Docker)
- **GitHub**: https://github.com/Lozzalingo/quiz-app

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Digital Ocean                     │
│                   157.245.42.21                      │
│  ┌─────────────────────────────────────────────┐    │
│  │              Docker Network                  │    │
│  │                                              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐   │    │
│  │  │  Nginx   │  │  Flask   │  │ Postgres │   │    │
│  │  │  :80/443 │──│  :5000   │──│  :5432   │   │    │
│  │  └──────────┘  └──────────┘  └──────────┘   │    │
│  │                                              │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## DNS Configuration

| Type  | Name               | Value               | TTL  |
|-------|-------------------|---------------------|------|
| A     | app.fatbigquiz.com | 157.245.42.21      | 3600 |
| A     | fatbigquiz.com     | 157.245.42.21      | 3600 |
| CNAME | cdn.fatbigquiz.com | fatbigquiz.com     | 43200|

---

## Server Access

```bash
# SSH into server
ssh -i ~/.ssh/id_ed25519_droplet root@157.245.42.21

# Or if using ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_droplet
ssh root@157.245.42.21
```

---

## File Locations on Server

```
/root/quiz-app/              # App root
├── docker-compose.yml       # Container orchestration
├── Dockerfile               # Flask app image
├── nginx.conf               # Nginx config
├── .env                     # Environment variables (secrets)
├── app.py                   # Main Flask application
├── static/                  # Static files
│   ├── qrcodes/             # Generated QR codes
│   └── uploads/             # Question images
└── certbot/                 # SSL certificates
    └── conf/                # Let's Encrypt certs
```

---

## Common Commands

### View logs
```bash
# All containers
docker compose logs -f

# Specific container
docker compose logs -f web
docker compose logs -f db
docker compose logs -f nginx
```

### Restart services
```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart web
```

### Update deployment
```bash
cd /root/quiz-app
git pull origin main
docker compose build
docker compose up -d
```

### Database access
```bash
# Connect to PostgreSQL
docker exec -it quiz_app_db psql -U quiz_user quiz_app

# Backup database
docker exec quiz_app_db pg_dump -U quiz_user quiz_app > backup.sql

# Restore database
docker exec -i quiz_app_db psql -U quiz_user quiz_app < backup.sql
```

### SSL certificate renewal
```bash
# Certificates auto-renew, but to manually renew:
docker compose run --rm certbot renew
docker compose restart nginx
```

---

## Environment Variables

The `.env` file contains sensitive configuration:

```bash
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=<random-64-char-hex>
ADMIN_PASSWORD=<your-admin-password>
DB_PASSWORD=<database-password>
BASE_URL=https://app.fatbigquiz.com
```

**Generate new secret key:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Troubleshooting

### App not responding
```bash
# Check if containers are running
docker compose ps

# Check container health
docker compose logs web

# Restart everything
docker compose down && docker compose up -d
```

### Database connection issues
```bash
# Check db container is healthy
docker compose ps db

# Check db logs
docker compose logs db
```

### SSL certificate issues
```bash
# Check certificate status
docker compose run --rm certbot certificates

# Force renewal
docker compose run --rm certbot renew --force-renewal
```

### Out of memory
```bash
# Check memory usage
free -h
docker stats

# If needed, restart containers to free memory
docker compose restart
```

---

## Backup Strategy

### Database
```bash
# Create backup
docker exec quiz_app_db pg_dump -U quiz_user quiz_app > /root/backups/quiz_$(date +%Y%m%d).sql

# Automate with cron (add to crontab -e)
0 3 * * * docker exec quiz_app_db pg_dump -U quiz_user quiz_app > /root/backups/quiz_$(date +\%Y\%m\%d).sql
```

### QR Codes and Uploads
```bash
# Backup static files
tar -czf /root/backups/static_$(date +%Y%m%d).tar.gz /root/quiz-app/static/
```

---

## Initial Data Transfer

After deployment, transfer existing data from local:

### Database
```bash
# On local machine - export
pg_dump -U postgres quiz_app > quiz_app_backup.sql

# Transfer to server
scp -i ~/.ssh/id_ed25519_droplet quiz_app_backup.sql root@157.245.42.21:/root/

# On server - import
docker exec -i quiz_app_db psql -U quiz_user quiz_app < /root/quiz_app_backup.sql
```

### Images/QR Codes
```bash
# Transfer static files
scp -i ~/.ssh/id_ed25519_droplet -r static/qrcodes/ root@157.245.42.21:/root/quiz-app/static/
scp -i ~/.ssh/id_ed25519_droplet -r static/uploads/ root@157.245.42.21:/root/quiz-app/static/
```

---

## Security Notes

- SSH key authentication only (no passwords)
- All traffic over HTTPS (Let's Encrypt SSL)
- Database not exposed externally (Docker internal network)
- Secrets stored in `.env` file (not in git)
- Firewall: Only ports 22, 80, 443 open
