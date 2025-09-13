# Setup & Installation Guide

Complete guide for setting up and running the Affiliate Reconciliation Platform locally and in production environments.

## Quick Start

### Prerequisites
- Python 3.11+ (3.12 recommended)
- Poetry (for dependency management)
- Git

### Fast Setup (Development)
```bash
# Clone the repository
git clone <repository-url>
cd affiliate-reconciliation-backend

# Install dependencies
poetry install

# Run tests to verify setup
poetry run pytest -q

# Start the development server
poetry run uvicorn app.main:app --reload
```

The API will be available at: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Detailed Installation

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 10GB available space
- OS: Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)

**Recommended for Production:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ available space
- OS: Linux (Ubuntu 20.04+ or CentOS 8+)

### Python Installation

**Windows:**
1. Download Python 3.11+ from [python.org](https://python.org)
2. Run installer and check "Add Python to PATH"
3. Verify installation: `python --version`

**macOS:**
```bash
# Using Homebrew (recommended)
brew install python@3.11

# Using pyenv (alternative)
pyenv install 3.11.8
pyenv global 3.11.8
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-pip
```

**Linux (RHEL/CentOS):**
```bash
sudo dnf install python3.11 python3.11-pip
```

### Poetry Installation

```bash
# Install Poetry (cross-platform)
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Windows PowerShell
$env:PATH += ";$env:APPDATA\Python\Scripts"

# Verify installation
poetry --version
```

### Project Setup

```bash
# Clone repository
git clone <repository-url>
cd affiliate-reconciliation-backend

# Install dependencies
poetry install

# Activate virtual environment (optional - Poetry handles this automatically)
poetry shell
```

### Database Setup

#### SQLite (Development - Default)
No additional setup required. SQLite database files are created automatically in the project directory.

#### PostgreSQL (Production)

**Install PostgreSQL:**

*Ubuntu/Debian:*
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

*macOS:*
```bash
brew install postgresql
brew services start postgresql
```

*Windows:*
Download and install from [postgresql.org](https://postgresql.org)

**Create Database:**
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE affiliate_reconciliation;
CREATE USER affiliate_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE affiliate_reconciliation TO affiliate_user;
\q
```

**Update Configuration:**
Create `.env` file in project root:
```bash
DATABASE_URL=postgresql://affiliate_user:secure_password@localhost/affiliate_reconciliation
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=sqlite:///./test.db

# Logging Configuration  
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Security
SECRET_KEY=your-secret-key-change-in-production

# Mock Integration Settings
INTEGRATIONS_RANDOM_SEED=12345
MOCK_FAILURE_RATE=0.05

# Network Timeouts
REDDIT_LINK_RESOLVE_TIMEOUT=10

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Optional: Real Platform API Keys (when migrating from mocks)
# REDDIT_CLIENT_ID=your_reddit_client_id
# REDDIT_CLIENT_SECRET=your_reddit_client_secret
# INSTAGRAM_ACCESS_TOKEN=your_instagram_token
# YOUTUBE_API_KEY=your_youtube_api_key
# TWITTER_BEARER_TOKEN=your_twitter_token
```

### Verify Installation

Run the test suite to ensure everything is working:

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test categories
poetry run pytest tests/test_unit_* -v           # Unit tests only
poetry run pytest tests/test_integration_* -v   # Integration tests only
poetry run pytest tests/test_full_system.py -v  # End-to-end tests
```

### Start the Application

```bash
# Development server with auto-reload
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production server
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Verify the server is running:**
- Visit: http://localhost:8000
- Should see: `{"message": "Affiliate Reconciliation Platform API", ...}`
- API docs: http://localhost:8000/docs

## Production Deployment

### Production Environment Setup

#### Using Docker (Recommended)

**Create Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure Poetry
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Create docker-compose.yml:**
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://affiliate_user:secure_password@db:5432/affiliate_reconciliation
      - LOG_LEVEL=INFO
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=affiliate_reconciliation
      - POSTGRES_USER=affiliate_user
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

**Deploy with Docker:**
```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

#### Manual Production Setup

**1. Server Setup (Ubuntu 20.04):**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv nginx postgresql redis-server

# Create application user
sudo useradd --system --group --home /opt/affiliate-platform affiliate

# Create directories
sudo mkdir -p /opt/affiliate-platform/{app,logs,venv}
sudo chown -R affiliate:affiliate /opt/affiliate-platform
```

**2. Application Setup:**
```bash
# Switch to application user
sudo -u affiliate bash
cd /opt/affiliate-platform

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Poetry
pip install poetry

# Clone and install application
git clone <repository-url> app
cd app
poetry install --no-dev
```

**3. Systemd Service:**

Create `/etc/systemd/system/affiliate-platform.service`:
```ini
[Unit]
Description=Affiliate Reconciliation Platform
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=affiliate
Group=affiliate
WorkingDirectory=/opt/affiliate-platform/app
Environment=PATH=/opt/affiliate-platform/venv/bin
ExecStart=/opt/affiliate-platform/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**4. Nginx Configuration:**

Create `/etc/nginx/sites-available/affiliate-platform`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
```

**5. Enable and Start Services:**
```bash
# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/affiliate-platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Start application service
sudo systemctl enable affiliate-platform
sudo systemctl start affiliate-platform

# Check status
sudo systemctl status affiliate-platform
```

### SSL/TLS Configuration

**Using Let's Encrypt (Recommended):**
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

### Monitoring & Logging

**1. Application Logs:**
```bash
# View application logs
sudo journalctl -u affiliate-platform -f

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

**2. Log Rotation:**

Create `/etc/logrotate.d/affiliate-platform`:
```
/opt/affiliate-platform/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 affiliate affiliate
    postrotate
        systemctl reload affiliate-platform
    endscript
}
```

## Performance Tuning

### Database Optimization

**PostgreSQL Configuration:**

Edit `/etc/postgresql/15/main/postgresql.conf`:
```conf
# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 64MB

# Connection settings
max_connections = 100

# WAL settings
wal_buffers = 16MB
checkpoint_completion_target = 0.7

# Query planner
random_page_cost = 1.1
effective_io_concurrency = 200
```

**Create Database Indexes:**
```sql
-- Performance indexes (run after initial setup)
CREATE INDEX idx_posts_affiliate_campaign ON posts(affiliate_id, campaign_id);
CREATE INDEX idx_reconciliation_logs_status ON reconciliation_logs(status);
CREATE INDEX idx_affiliate_reports_submitted_at ON affiliate_reports(submitted_at);
CREATE INDEX idx_alerts_created_at ON alerts(created_at) WHERE status = 'OPEN';
```

### Application Performance

**1. Worker Configuration:**
```bash
# Calculate workers: (2 x CPU cores) + 1
# For 4 CPU cores: 9 workers
uvicorn app.main:app --workers 9 --worker-class uvicorn.workers.UvicornWorker
```

**2. Memory Usage:**
- Each worker uses ~50-100MB RAM
- Monitor with: `htop` or `ps aux | grep uvicorn`
- Adjust worker count based on available memory

**3. Connection Pooling:**

Update database configuration in `app/database.py`:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## Backup & Recovery

### Database Backup

**Automated Backup Script:**
```bash
#!/bin/bash
# /opt/affiliate-platform/scripts/backup.sh

BACKUP_DIR="/opt/affiliate-platform/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="affiliate_reconciliation"

mkdir -p $BACKUP_DIR

# Create backup
pg_dump -h localhost -U affiliate_user $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 30 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete
```

**Schedule with Cron:**
```bash
# Add to crontab
0 2 * * * /opt/affiliate-platform/scripts/backup.sh
```

### Application Backup

**Code and Configuration:**
```bash
# Backup configuration and logs
tar -czf app_backup_$(date +%Y%m%d).tar.gz \
    /opt/affiliate-platform/app/.env \
    /opt/affiliate-platform/logs/ \
    /etc/nginx/sites-available/affiliate-platform
```

### Recovery Procedure

**1. Database Recovery:**
```bash
# Stop application
sudo systemctl stop affiliate-platform

# Restore database
gunzip -c backup_20240115_020000.sql.gz | psql -h localhost -U affiliate_user affiliate_reconciliation

# Start application
sudo systemctl start affiliate-platform
```

**2. Application Recovery:**
```bash
# Restore from git (recommended)
cd /opt/affiliate-platform/app
git pull origin main
poetry install --no-dev

# Restart services
sudo systemctl restart affiliate-platform
```

## Security Hardening

### Application Security

**1. Environment Variables:**
- Never commit `.env` files to version control
- Use strong, randomly generated SECRET_KEY
- Rotate API keys regularly

**2. API Security:**
```python
# Add to production .env
CORS_ORIGINS=https://your-domain.com
RATE_LIMIT_ENABLED=true
```

### System Security

**1. Firewall Configuration:**
```bash
# Enable UFW
sudo ufw enable

# Allow SSH (adjust port as needed)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow PostgreSQL (only from localhost)
sudo ufw allow from 127.0.0.1 to any port 5432
```

**2. User Permissions:**
```bash
# Ensure application user has minimal permissions
sudo usermod -s /usr/sbin/nologin affiliate
sudo chmod 750 /opt/affiliate-platform
```

**3. Regular Updates:**
```bash
# System updates
sudo apt update && sudo apt upgrade -y

# Application updates
cd /opt/affiliate-platform/app
git pull origin main
poetry update
sudo systemctl restart affiliate-platform
```

## Troubleshooting

### Common Issues

**1. Database Connection Errors:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions:**
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify connection string in `.env`
- Check firewall settings
- Verify user permissions in PostgreSQL

**2. Port Already in Use:**
```
OSError: [Errno 98] Address already in use
```

**Solutions:**
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

**3. Import Errors:**
```
ModuleNotFoundError: No module named 'app'
```

**Solutions:**
- Ensure virtual environment is activated
- Run from correct directory
- Reinstall dependencies: `poetry install`

**4. Permission Errors:**
```
PermissionError: [Errno 13] Permission denied: 'logs/app.log'
```

**Solutions:**
```bash
# Create logs directory
mkdir -p logs

# Fix permissions
sudo chown -R affiliate:affiliate /opt/affiliate-platform/logs
sudo chmod 755 /opt/affiliate-platform/logs
```

### Health Checks

**Application Health:**
```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check  
curl http://localhost:8000/health/detailed

# Check specific endpoints
curl -H "Authorization: Bearer test_key" http://localhost:8000/api/v1/campaigns/
```

**System Health:**
```bash
# Check disk space
df -h

# Check memory usage
free -h

# Check CPU usage
top

# Check service status
sudo systemctl status affiliate-platform postgresql nginx
```

### Getting Help

**Log Files:**
- Application: `/opt/affiliate-platform/logs/app.log`
- System: `journalctl -u affiliate-platform`
- Nginx: `/var/log/nginx/error.log`
- PostgreSQL: `/var/log/postgresql/postgresql-15-main.log`

**Debug Mode:**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
poetry run uvicorn app.main:app --reload --log-level debug
```

**Support Resources:**
- Check existing documentation in `docs/`
- Review test files for usage examples
- See [Operations & Observability](OPERATIONS_AND_OBSERVABILITY.md) for monitoring guidance

## Next Steps

After successful installation:

1. **Create Initial Data:**
   - Create admin affiliate account
   - Set up platforms and campaigns
   - Test submission flow

2. **Configure Monitoring:**
   - Set up log aggregation
   - Configure health check alerts
   - Monitor performance metrics

3. **Security Review:**
   - Review and update default passwords
   - Configure SSL certificates
   - Set up backup procedures

4. **Scale Planning:**
   - Monitor resource usage
   - Plan for horizontal scaling
   - Consider external queue system (Redis/SQS)

For detailed operational procedures, see [Operations & Observability](OPERATIONS_AND_OBSERVABILITY.md).