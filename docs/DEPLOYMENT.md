# Deployment Guide

This document describes how to deploy the Quiz App to production.

---

## Prerequisites

- Linux server (Ubuntu 22.04 recommended)
- Python 3.11+
- PostgreSQL 14+
- Nginx
- SSL certificate (Let's Encrypt recommended)

---

## Quick Start (Development)

```bash
# Clone repository
cd quiz_app

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL
createdb quiz_app

# Create .env file
cp .env.example .env
# Edit .env with your settings

# Initialize database
flask db upgrade

# Run development server
python app.py
```

---

## Production Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Nginx
sudo apt install nginx -y
```

### 2. PostgreSQL Configuration

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE USER quiz_user WITH PASSWORD 'your-strong-password';
CREATE DATABASE quiz_app OWNER quiz_user;
GRANT ALL PRIVILEGES ON DATABASE quiz_app TO quiz_user;
\q
```

**Edit PostgreSQL config for production:**

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Recommended settings:
```
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 768MB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 7864kB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

### 3. Application Setup

```bash
# Create app directory
sudo mkdir -p /var/www/quiz_app
sudo chown $USER:$USER /var/www/quiz_app

# Clone/copy application
cd /var/www/quiz_app
# ... copy files ...

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

### 4. Environment Configuration

Create `/var/www/quiz_app/.env`:

```bash
FLASK_APP=app.py
FLASK_ENV=production

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-256-bit-secret-key-here

# Change this!
ADMIN_PASSWORD=your-strong-admin-password

# Your domain
BASE_URL=https://quiz.yourdomain.com

# PostgreSQL connection
DATABASE_URL=postgresql://quiz_user:your-strong-password@localhost:5432/quiz_app
```

**Important:** Never commit `.env` to version control!

### 5. Initialize Database

```bash
cd /var/www/quiz_app
source venv/bin/activate

flask db upgrade
```

### 6. Gunicorn Setup

Create `/var/www/quiz_app/gunicorn.conf.py`:

```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "eventlet"
timeout = 120
keepalive = 5
errorlog = "/var/log/quiz_app/gunicorn-error.log"
accesslog = "/var/log/quiz_app/gunicorn-access.log"
loglevel = "info"
```

Create log directory:
```bash
sudo mkdir -p /var/log/quiz_app
sudo chown $USER:$USER /var/log/quiz_app
```

### 7. Systemd Service

Create `/etc/systemd/system/quiz_app.service`:

```ini
[Unit]
Description=Quiz App Gunicorn Service
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/quiz_app
Environment="PATH=/var/www/quiz_app/venv/bin"
EnvironmentFile=/var/www/quiz_app/.env
ExecStart=/var/www/quiz_app/venv/bin/gunicorn \
    --config gunicorn.conf.py \
    "app:create_app()"

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable quiz_app
sudo systemctl start quiz_app
sudo systemctl status quiz_app
```

### 8. Nginx Configuration

Create `/etc/nginx/sites-available/quiz_app`:

```nginx
server {
    listen 80;
    server_name quiz.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name quiz.yourdomain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/quiz.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/quiz.yourdomain.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Static files
    location /static/ {
        alias /var/www/quiz_app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Socket.IO
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/quiz_app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 9. SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d quiz.yourdomain.com
```

---

## Security Checklist

- [ ] Change `SECRET_KEY` to random 256-bit value
- [ ] Change `ADMIN_PASSWORD` from default
- [ ] Use strong PostgreSQL password
- [ ] Enable HTTPS (required for production)
- [ ] Set `FLASK_ENV=production`
- [ ] Disable debug mode
- [ ] Set proper file permissions
- [ ] Configure firewall (UFW)
- [ ] Enable fail2ban for SSH

### Firewall Setup

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## Database Backups

### Automated Daily Backup

Create `/usr/local/bin/backup-quiz-db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/quiz_app"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/quiz_app_$TIMESTAMP.sql.gz"

mkdir -p $BACKUP_DIR
pg_dump quiz_app | gzip > $BACKUP_FILE

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

Make executable and schedule:
```bash
sudo chmod +x /usr/local/bin/backup-quiz-db.sh
sudo crontab -e
# Add: 0 2 * * * /usr/local/bin/backup-quiz-db.sh
```

### Manual Backup

```bash
pg_dump quiz_app > backup.sql
```

### Restore from Backup

```bash
psql quiz_app < backup.sql
```

---

## Monitoring

### Application Logs

```bash
# Gunicorn logs
tail -f /var/log/quiz_app/gunicorn-error.log
tail -f /var/log/quiz_app/gunicorn-access.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Systemd logs
journalctl -u quiz_app -f
```

### Process Monitoring

Consider setting up:
- **Supervisor** or **systemd** (included above)
- **Prometheus + Grafana** for metrics
- **Sentry** for error tracking

### Uptime Monitoring

- UptimeRobot (free)
- Pingdom
- StatusCake

---

## Scaling Considerations

### Horizontal Scaling

For high traffic:
1. Use Redis for session storage
2. Use Redis for Socket.IO message queue
3. Run multiple Gunicorn instances behind load balancer
4. Use PostgreSQL read replicas

### Performance Optimization

1. Enable Nginx caching for static files
2. Use CDN for static assets (Cloudflare, etc.)
3. Enable PostgreSQL query caching
4. Add database indexes for frequent queries

---

## Real-Time Features

The application uses Socket.IO for real-time communication:

### Features Requiring Socket.IO

| Feature | Description |
|---------|-------------|
| Timer broadcast | Admin timer visible to all players |
| Round open/close | Players see round status changes instantly |
| Spreadsheet sync | Multiple admins can edit scores; changes sync in real-time |
| Submission updates | Spreadsheet auto-refreshes when teams submit answers |

### Socket.IO Rooms

| Room | Purpose |
|------|---------|
| `game_{id}` | All players and admins in a game (timer, round status) |
| `spreadsheet_{id}` | Admins viewing the grading spreadsheet (score sync) |

### Verifying Socket.IO Works

1. Open the player quiz page and admin live control in separate browsers
2. Start a timer on admin side
3. Timer should appear on player side instantly
4. Check browser console for "Connected to server" message
5. Check server logs for "Client joined room" messages

---

## Troubleshooting

### Application Won't Start

```bash
# Check service status
sudo systemctl status quiz_app

# Check logs
journalctl -u quiz_app -n 50

# Test manually
cd /var/www/quiz_app
source venv/bin/activate
python app.py
```

### Database Connection Issues

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -U quiz_user -d quiz_app -h localhost

# Check pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

### Socket.IO Not Working

1. Check Nginx WebSocket proxy config
2. Verify firewall allows WebSocket connections
3. Check browser console for errors
4. Ensure `eventlet` worker class in Gunicorn

### 502 Bad Gateway

1. Check if Gunicorn is running
2. Check Gunicorn bind address matches Nginx
3. Check file permissions
4. Check logs for errors

---

## Maintenance

### Updating the Application

```bash
cd /var/www/quiz_app
source venv/bin/activate

# Pull updates (if using git)
git pull

# Update dependencies
pip install -r requirements.txt

# Run migrations
flask db upgrade

# Restart service
sudo systemctl restart quiz_app
```

### Database Migrations

```bash
cd /var/www/quiz_app
source venv/bin/activate

# Create migration after model changes
flask db migrate -m "Description"

# Apply migration
flask db upgrade

# Rollback if needed
flask db downgrade
```

---

## Alternative Deployment Options

### Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn eventlet

COPY . .

EXPOSE 8000

CMD ["gunicorn", "--worker-class", "eventlet", "-b", "0.0.0.0:8000", "app:create_app()"]
```

### Platform as a Service

- **Railway** - Easy deployment with PostgreSQL add-on
- **Render** - Free tier available
- **Heroku** - Mature platform, paid plans
- **PythonAnywhere** - Python-focused hosting

---

## Support

For issues:
1. Check this documentation
2. Review application logs
3. Check PostgreSQL logs
4. Verify environment configuration
