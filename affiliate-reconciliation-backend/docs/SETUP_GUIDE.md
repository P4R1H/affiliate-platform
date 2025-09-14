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
- Health check: http://localhost:8000/health

### Test the API
```bash
# Health check
curl http://localhost:8000/health

# View API documentation in browser
open http://localhost:8000/docs
```

### Optional: Discord Bot Setup
```bash
# Set Discord bot token (optional)
echo "DISCORD_BOT_TOKEN=your_bot_token_here" >> .env
echo "ENABLE_DISCORD_BOT=true" >> .env

# Bot will be available for affiliate reporting via Discord
```

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

**Default Configuration:**
```bash
DATABASE_URL=sqlite:///./test.db
```

The application will automatically create the database schema on first run.

#### PostgreSQL (Production - Optional)

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
```bash
DATABASE_URL=postgresql://affiliate_user:secure_password@localhost/affiliate_reconciliation
```

**Note:** The application uses SQLAlchemy, so it supports both SQLite (development) and PostgreSQL (production) seamlessly. Schema migrations are handled automatically.

### Environment Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Database Configuration (SQLite by default)
DATABASE_URL=sqlite:///./test.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Security
SECRET_KEY=your-secret-key-change-in-production

# API Keys for Affiliates
API_KEY_1=test_key_123
API_KEY_2=another_test_key

# Discord Bot Configuration (Optional)
ENABLE_DISCORD_BOT=false
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_COMMAND_GUILDS=123456789,987654321
API_BASE_URL=http://localhost:8000/api/v1
BOT_INTERNAL_TOKEN=internal_bot_token

# Mock Integration Settings
INTEGRATIONS_RANDOM_SEED=12345
MOCK_FAILURE_RATE=0.05

# Network Timeouts
REDDIT_LINK_RESOLVE_TIMEOUT=10

# Reconciliation Settings
RECONCILIATION_SETTINGS_BASE_TOLERANCE_PCT=0.05
RECONCILIATION_SETTINGS_OVERCLAIM_THRESHOLD_PCT=0.20

# Trust Scoring
TRUST_SCORING_MIN_SCORE=0.0
TRUST_SCORING_MAX_SCORE=1.0

# Queue Settings
QUEUE_SETTINGS_MAX_IN_MEMORY=5000
QUEUE_SETTINGS_WARN_DEPTH=1000

# Alerting
ALERTING_SETTINGS_PLATFORM_DOWN_ESCALATION_MINUTES=120

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_OPEN_COOLDOWN_SECONDS=60
CIRCUIT_BREAKER_HALF_OPEN_PROBE_COUNT=3

# CORS Origins (for web frontend)
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### Optional Production Configuration

For production deployments, also configure:

```bash
# PostgreSQL (if using external database)
DATABASE_URL=postgresql://user:password@localhost/dbname

# Real Platform API Keys (replace mocks)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
INSTAGRAM_ACCESS_TOKEN=your_instagram_token
META_ACCESS_TOKEN=your_meta_token
YOUTUBE_API_KEY=your_youtube_api_key
TIKTOK_ACCESS_TOKEN=your_tiktok_token
X_BEARER_TOKEN=your_twitter_token
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

### Simple Production Setup

For MVP production deployment, you can use a simple approach:

#### Using Docker (Recommended for MVP)

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

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and Run:**
```bash
# Build Docker image
docker build -t affiliate-platform .

# Run container
docker run -d \
  --name affiliate-platform \
  -p 8000:8000 \
  -v $(pwd)/logs:/app/logs \
  -e DATABASE_URL=sqlite:///./prod.db \
  -e SECRET_KEY=your-production-secret-key \
  affiliate-platform
```

#### Manual Production Setup

**1. Server Setup:**
```bash
# Install dependencies
sudo apt update
sudo apt install -y python3.11 python3.11-venv nginx

# Create application directory
sudo mkdir -p /opt/affiliate-platform
sudo chown $USER:$USER /opt/affiliate-platform
```

**2. Application Setup:**
```bash
cd /opt/affiliate-platform

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Poetry
pip install poetry

# Clone and install application
git clone <repository-url> .
poetry install --no-dev

# Create .env file with production settings
cp .env.example .env
# Edit .env with production values
```

**3. Start Application:**
```bash
# Start with uvicorn
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**4. Basic Nginx Proxy (Optional):**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
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
- For SQLite (default): Ensure the application has write permissions in the project directory
- For PostgreSQL: Check PostgreSQL is running and connection string is correct
- Verify DATABASE_URL in .env file

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
- Ensure you're running from the project root directory
- Activate Poetry shell: `poetry shell`
- Reinstall dependencies: `poetry install`

**4. Permission Errors:**
```
PermissionError: [Errno 13] Permission denied: 'logs/app.log'
```

**Solutions:**
```bash
# Create logs directory
mkdir -p logs

# Fix permissions (if needed)
chmod 755 logs
```

**5. Discord Bot Not Working:**
- Check ENABLE_DISCORD_BOT=true in .env
- Verify DISCORD_BOT_TOKEN is set correctly
- Ensure bot has proper permissions in Discord server
- Check logs for Discord-related errors

### Health Checks

**Application Health:**
```bash
# Basic health check
curl http://localhost:8000/health

# Should return: {"status": "healthy", "timestamp": "..."}
```

**API Testing:**
```bash
# Test API with authentication
curl -H "Authorization: Bearer test_key_123" http://localhost:8000/api/v1/campaigns/

# Test reconciliation endpoint
curl -X POST http://localhost:8000/api/v1/reports/ \
  -H "Authorization: Bearer test_key_123" \
  -H "Content-Type: application/json" \
  -d '{"campaign_id": 1, "platform_post_url": "https://example.com", "claimed_views": 100, "claimed_clicks": 10, "claimed_conversions": 1}'
```

### Getting Help

**Log Files:**
- Application: `logs/app.log`
- SQLite database: `test.db` (can be viewed with DB browser)
- Test output: Check pytest results

**Debug Mode:**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
poetry run uvicorn app.main:app --reload --log-level debug
```

**Useful Commands:**
```bash
# View recent logs
tail -f logs/app.log

# Run specific tests
poetry run pytest tests/test_unit_backoff.py -v

# Check database content
poetry run python -c "from app.database import SessionLocal; s = SessionLocal(); print(s.query(s.query_property.mapper.class_).count())"
```

**Support Resources:**
- Check API documentation at http://localhost:8000/docs
- Review test files for usage examples
- See [Operations & Observability](OPERATIONS_AND_OBSERVABILITY.md) for monitoring guidance

## Next Steps

After successful installation:

1. **Test the Core Features:**
   - Submit affiliate reports via API
   - Test Discord bot integration (if enabled)
   - Monitor reconciliation jobs and results
   - Check alerts for discrepancies

2. **Explore the API:**
   - Review API documentation at `/docs`
   - Test different endpoints with various scenarios
   - Understand the data flow and reconciliation process

3. **Monitor and Debug:**
   - Check application logs in `logs/app.log`
   - Use health check endpoint for status monitoring
   - Run tests to ensure everything works correctly

4. **Production Considerations:**
   - Set up proper environment variables for production
   - Consider using PostgreSQL for production workloads
   - Configure proper logging and monitoring
   - Set up regular backups of the database

For detailed operational procedures, see [Operations & Observability](OPERATIONS_AND_OBSERVABILITY.md).