# Quiz App Deployment Checklist

## Overview
- **App**: Flask Quiz App with Socket.IO
- **Database**: PostgreSQL
- **Deployment**: Docker on Digital Ocean Droplet
- **GitHub**: https://github.com/Lozzalingo/quiz-app

---

## Phase 1: Dockerize (Local)

- [x] Create Dockerfile
- [x] Create docker-compose.yml (Flask + PostgreSQL + Nginx)
- [x] Create .dockerignore
- [x] Create production environment config
- [ ] Test Docker build locally
- [ ] Test docker-compose up locally

---

## Phase 2: GitHub

- [x] Initialize git repository
- [x] Add .gitignore (ensure .env excluded)
- [x] Create GitHub repo: `quiz-app`
- [x] Push code to GitHub
- [x] Verify sensitive data not committed

---

## Phase 3: Digital Ocean Setup

- [ ] Create Droplet (Ubuntu 22.04, 2GB RAM minimum)
- [ ] SSH into droplet
- [ ] Install Docker & Docker Compose
- [ ] Clone repo from GitHub
- [ ] Create production .env file on server
- [ ] Run docker-compose up -d

---

## Phase 4: Data Transfer

- [ ] Export local PostgreSQL database (pg_dump)
- [ ] Transfer dump file to droplet (scp)
- [ ] Import database on droplet (pg_restore)
- [ ] Transfer QR code images (scp static/qrcodes/)
- [ ] Verify data integrity

---

## Phase 5: Production Config

- [ ] Set up SSL with Let's Encrypt (Certbot)
- [ ] Configure domain/DNS (if applicable)
- [ ] Set strong SECRET_KEY
- [ ] Set strong ADMIN_PASSWORD
- [ ] Configure firewall (ufw)
- [ ] Set up automatic Docker restart

---

## Commands Reference

### Local Docker Test
```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
```

### Database Export (Local)
```bash
pg_dump -U postgres quiz_app > quiz_app_backup.sql
```

### Transfer to Droplet
```bash
scp quiz_app_backup.sql root@YOUR_DROPLET_IP:/root/
scp -r static/qrcodes/ root@YOUR_DROPLET_IP:/root/quiz_app/static/
```

### Database Import (Droplet)
```bash
docker exec -i quiz_app_db psql -U quiz_user quiz_app < quiz_app_backup.sql
```

### SSL Setup (Droplet)
```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

---

## Environment Variables (Production)

```bash
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=<generate-strong-key>
ADMIN_PASSWORD=<strong-password>
DATABASE_URL=postgresql://quiz_user:dbpassword@db:5432/quiz_app
BASE_URL=https://yourdomain.com
```

Generate secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Droplet Details

- **IP Address**: 157.245.42.21
- **Domain**: app.fatbigquiz.com
- **SSH**: `ssh -i ~/.ssh/id_ed25519_droplet root@157.245.42.21`

---

## Status

| Phase | Status |
|-------|--------|
| Dockerize | ✅ Done |
| GitHub | ✅ Done |
| Droplet Setup | ✅ Done |
| Data Transfer | ✅ Done |
| Production Config | ✅ Done |
