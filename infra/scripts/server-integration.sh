#!/bin/bash
# =============================================================================
# BaseLayer Server Integration Script
# =============================================================================
# Configures Ubuntu 22.04 server for BaseLayer deployment
# Optimized for i5-2400, 16GB RAM, HDD storage
# =============================================================================

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check Ubuntu version
check_ubuntu() {
    local version=$(lsb_release -rs)
    if [[ "$version" != "22.04" ]]; then
        log_warning "This script is optimized for Ubuntu 22.04. Current version: $version"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Check hardware requirements
check_hardware() {
    log_info "Checking hardware requirements..."
    
    # Check CPU
    local cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d':' -f2 | xargs)
    local cpu_cores=$(nproc)
    log_info "CPU: $cpu_model ($cpu_cores cores)"
    
    # Check RAM
    local total_ram=$(free -h | awk '/^Mem:/ {print $2}')
    log_info "RAM: $total_ram"
    
    # Check disk space
    local disk_space=$(df -h / | awk 'NR==2 {print $4}')
    log_info "Available disk space: $disk_space"
    
    # Check if i5-2400
    if [[ "$cpu_model" =~ "i5-2400" ]]; then
        log_success "Detected i5-2400 CPU - applying optimizations"
    else
        log_warning "i5-2400 CPU not detected - optimizations may not be optimal"
    fi
}

# Configure UFW firewall
configure_firewall() {
    log_info "Configuring UFW firewall..."
    
    # Reset UFW to default state
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH (already configured)
    ufw allow ssh
    
    # BaseLayer ports (LAN only)
    ufw allow from 192.168.1.0/24 to any port 8000 comment "BaseLayer API"
    ufw allow from 192.168.1.0/24 to any port 3000 comment "BaseLayer Frontend"
    ufw allow from 192.168.1.0/24 to any port 5432 comment "PostgreSQL"
    ufw allow from 192.168.1.0/24 to any port 6379 comment "Redis"
    ufw allow from 192.168.1.0/24 to any port 80 comment "HTTP"
    ufw allow from 192.168.1.0/24 to any port 443 comment "HTTPS"
    ufw allow from 192.168.1.0/24 to any port 9090 comment "Prometheus Metrics"
    ufw allow from 192.168.1.0/24 to any port 19999 comment "Netdata"
    
    # Enable UFW
    ufw --force enable
    
    log_success "UFW firewall configured"
}

# Create baselayer user
create_user() {
    log_info "Creating baselayer user..."
    
    if ! id "baselayer" &>/dev/null; then
        useradd -r -m -s /bin/bash -d /opt/baselayer baselayer
        log_success "Created baselayer user"
    else
        log_info "baselayer user already exists"
    fi
    
    # Create necessary directories
    mkdir -p /opt/baselayer/{.venv,uploads,logs,config}
    mkdir -p /var/lib/baselayer/{uploads,logs}
    mkdir -p /var/log/baselayer
    mkdir -p /run/baselayer
    mkdir -p /etc/baselayer
    mkdir -p /backup/baselayer
    
    # Set permissions
    chown -R baselayer:baselayer /opt/baselayer
    chown -R baselayer:baselayer /var/lib/baselayer
    chown -R baselayer:baselayer /var/log/baselayer
    chown -R baselayer:baselayer /run/baselayer
    chmod 755 /opt/baselayer
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    # Update package lists
    apt update
    
    # Install required packages
    apt install -y \
        python3.12 \
        python3.12-venv \
        python3.12-dev \
        python3-pip \
        postgresql-16 \
        postgresql-contrib \
        redis-server \
        nginx \
        curl \
        wget \
        git \
        build-essential \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        htop \
        iotop \
        netstat \
        lsof \
        unzip \
        zip
    
    # Install uv for fast Python package management
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    log_success "System dependencies installed"
}

# Configure PostgreSQL
configure_postgresql() {
    log_info "Configuring PostgreSQL..."
    
    # Start PostgreSQL
    systemctl enable postgresql
    systemctl start postgresql
    
    # Create baselayer database and user
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS baselayer_prod;" || true
    sudo -u postgres psql -c "DROP USER IF EXISTS baselayer;" || true
    sudo -u postgres psql -c "CREATE USER baselayer WITH PASSWORD 'secure_password_change_me';"
    sudo -u postgres psql -c "CREATE DATABASE baselayer_prod OWNER baselayer;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE baselayer_prod TO baselayer;"
    
    # Configure PostgreSQL for performance
    cat >> /etc/postgresql/16/main/postgresql.conf << EOF

# BaseLayer Performance Configuration (i5-2400 optimization)
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
max_connections = 100
EOF
    
    # Restart PostgreSQL
    systemctl restart postgresql
    
    log_success "PostgreSQL configured"
}

# Configure Redis
configure_redis() {
    log_info "Configuring Redis..."
    
    # Configure Redis for performance
    cat >> /etc/redis/redis.conf << EOF

# BaseLayer Performance Configuration (i5-2400 optimization)
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF
    
    # Start Redis
    systemctl enable redis-server
    systemctl start redis-server
    
    log_success "Redis configured"
}

# Configure system limits
configure_limits() {
    log_info "Configuring system limits..."
    
    # Create limits configuration
    cat > /etc/security/limits.d/baselayer.conf << EOF
baselayer soft nofile 65536
baselayer hard nofile 65536
baselayer soft nproc 4096
baselayer hard nproc 4096
baselayer soft memlock unlimited
baselayer hard memlock unlimited
EOF
    
    # Configure sysctl
    cat > /etc/sysctl.d/99-baselayer.conf << EOF
# BaseLayer System Configuration
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 5000
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
fs.file-max = 2097152
EOF
    
    # Apply sysctl settings
    sysctl -p /etc/sysctl.d/99-baselayer.conf
    
    log_success "System limits configured"
}

# Setup systemd services
setup_systemd() {
    log_info "Setting up systemd services..."
    
    # Copy service files
    cp infra/systemd/baselayer-api.service /etc/systemd/system/
    cp infra/systemd/baselayer-worker.service /etc/systemd/system/
    
    # Create BaseLayer target
    cat > /etc/systemd/system/baselayer.target << EOF
[Unit]
Description=BaseLayer Service Target
Documentation=https://github.com/baselayer/baselayer
Requires=network.target
After=network.target

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable services
    systemctl enable baselayer-api
    systemctl enable baselayer-worker
    systemctl enable baselayer.target
    
    log_success "Systemd services configured"
}

# Configure log rotation
configure_logrotate() {
    log_info "Configuring log rotation..."
    
    cat > /etc/logrotate.d/baselayer << EOF
/var/log/baselayer/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 baselayer baselayer
    postrotate
        systemctl reload baselayer-api || true
        systemctl reload baselayer-worker || true
    endscript
}
EOF
    
    log_success "Log rotation configured"
}

# Setup backup script
setup_backup() {
    log_info "Setting up backup script..."
    
    cat > /usr/local/bin/baselayer-backup.sh << 'EOF'
#!/bin/bash
# =============================================================================
# BaseLayer Backup Script
# =============================================================================

set -euo pipefail

BACKUP_DIR="/backup/baselayer"
DATE=$(date +%Y%m%d_%H%M%S)
DB_BACKUP_FILE="$BACKUP_DIR/db_$DATE.sql"
REDIS_BACKUP_FILE="$BACKUP_DIR/redis_$DATE.rdb"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
pg_dump -h localhost -U baselayer -d baselayer_prod > "$DB_BACKUP_FILE"
gzip "$DB_BACKUP_FILE"

# Backup Redis
redis-cli --rdb "$REDIS_BACKUP_FILE"
gzip "$REDIS_BACKUP_FILE"

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF
    
    chmod +x /usr/local/bin/baselayer-backup.sh
    
    # Add to cron
    (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/baselayer-backup.sh") | crontab -
    
    log_success "Backup script configured"
}

# Main function
main() {
    log_info "Starting BaseLayer server integration..."
    
    check_root
    check_ubuntu
    check_hardware
    
    configure_firewall
    create_user
    install_dependencies
    configure_postgresql
    configure_redis
    configure_limits
    setup_systemd
    configure_logrotate
    setup_backup
    
    log_success "BaseLayer server integration completed!"
    echo
    log_info "Next steps:"
    echo "1. Copy your BaseLayer application to /opt/baselayer"
    echo "2. Configure environment variables in /etc/baselayer/baselayer.env"
    echo "3. Install Python dependencies: sudo -u baselayer uv pip install -e /opt/baselayer/backend"
    echo "4. Start services: sudo systemctl start baselayer-api baselayer-worker"
    echo "5. Check status: sudo systemctl status baselayer-api baselayer-worker"
    echo
    log_info "Access URLs:"
    echo "  - API: http://192.168.1.50:8000"
    echo "  - Frontend: http://192.168.1.50:3000"
    echo "  - Netdata: http://192.168.1.50:19999"
    echo "  - Health: http://192.168.1.50:8000/health"
}

# Run main function
main "$@"
