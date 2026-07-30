# BaseLayer Infrastructure Module

Docker, Caddy, systemd, and deployment configurations for BaseLayer.

## Components

### Docker Configuration
- `docker-compose.yml`: Production services
- `docker-compose.dev.yml`: Development environment
- `docker-compose.test.yml`: Testing environment
- `Dockerfile`: Multi-stage application container

### Caddy Reverse Proxy
- `Caddyfile`: Reverse proxy configuration
- `caddy/`: SSL certificates and site configs
- Auto-SSL for LAN deployment
- Security headers and gzip compression

### Systemd Services
- `baselayer-api.service`: API server service
- `baselayer-worker.service`: Background worker service
- `baselayer-agent.service`: Agent orchestration service

### CI/CD Pipeline
- `.github/workflows/`: GitHub Actions
- Build, test, and deployment automation
- Dependency caching and security scanning

### Monitoring & Logging
- Netdata integration configs
- Prometheus metrics scraping
- Log aggregation setup

### Security
- UFW firewall rules
- SSL certificate management
- Security headers configuration
- Access control policies

## Deployment

### Development
```bash
docker-compose -f infra/docker-compose.dev.yml up
```

### Production
```bash
docker-compose -f infra/docker-compose.prod.yml up -d
```

### Systemd (Alternative)
```bash
sudo systemctl enable baselayer-api baselayer-worker
sudo systemctl start baselayer-api baselayer-worker
```

## Hardware Optimization

Configured for i5-2400, 16GB RAM, HDD storage:
- Resource limits and constraints
- I/O optimization for HDD
- Memory usage optimization
- CPU affinity settings
