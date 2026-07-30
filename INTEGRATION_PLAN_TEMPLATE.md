# BaseLayer to Nexus Main Server Integration Plan

## 🎯 Objective
Complete migration of BaseLayer multi-agent system to Nexus main server with zero downtime and data integrity.

## 📋 Current System Analysis

### BaseLayer Architecture Overview
- **System Type**: Modular, governance-grade operational system
- **Core Components**: 7 subsystems with 63 core components
- **Tech Stack**: Python 3.12 + FastAPI + React 19 + PostgreSQL 16 + Redis 7
- **Deployment**: Docker Compose with Caddy reverse proxy
- **Hardware Target**: Optimized for i5-2400 (4 cores, 16GB RAM)

### Current Subsystems
1. **Core Loop** - Workflow orchestration engine
2. **Income Engine** - Automated revenue pipelines  
3. **Codex/Memory** - Persistent knowledge store
4. **Protocol Libraries** - Reusable workflow templates
5. **Multi-Agent Orchestration** - Pipeline coordination across local AI models
6. **Governance/Doctrine** - Rules engine and audit trails
7. **Output Engineering** - Artifact generation and delivery

### Infrastructure Components
- **Database**: PostgreSQL 16 with persistent volumes
- **Cache/Queue**: Redis 7 with persistence
- **Proxy**: Caddy 2 with SSL termination
- **Background Processing**: Arq task queues
- **AI Integration**: Ollama (qwen2.5-coder:3b)

## 🔄 Migration Strategy

### Phase 1: Server Discovery & Planning (Week 1-2)
- [ ] Assess Nexus main server specifications and capacity
- [ ] Map current BaseLayer resource requirements to server capabilities
- [ ] Create inventory of server ports, storage, and network configuration
- [ ] Establish migration timeline and maintenance windows
- [ ] Document server access procedures and security protocols

### Phase 2: Server Preparation (Week 2-3)
- [ ] Update server OS and install required dependencies
- [ ] Configure Docker and Docker Compose on Nexus server
- [ ] Set up server firewall and security groups
- [ ] Create dedicated directories for BaseLayer deployment
- [ ] Configure server monitoring and logging infrastructure
- [ ] Establish backup procedures specific to server environment

### Phase 3: Data Migration to Server (Week 3-4)
- [ ] Transfer PostgreSQL data to server database
- [ ] Migrate Redis cache and queue data to server instance
- [ ] Transfer application files and uploads to server storage
- [ ] Import configuration files and environment variables
- [ ] Validate data integrity on server after transfer

### Phase 4: Server Application Deployment (Week 4-5)
- [ ] Deploy BaseLayer containers to Nexus server
- [ ] Configure server-specific environment variables
- [ ] Set up server networking and port mappings
- [ ] Configure background workers and agent services on server
- [ ] Implement server health checks and monitoring
- [ ] Optimize resource allocation for server hardware

### Phase 5: Server Integration Testing (Week 5-6)
- [ ] Test all BaseLayer workflows on server environment
- [ ] Validate server performance under load
- [ ] Test server security configurations and access controls
- [ ] Verify server backup and recovery procedures
- [ ] Conduct user acceptance testing on server deployment

### Phase 6: Server Cutover & Optimization (Week 6-7)
- [ ] Update DNS to point to Nexus main server
- [ ] Monitor server performance and resource utilization
- [ ] Optimize BaseLayer configuration for server hardware
- [ ] Implement server-specific performance tuning
- [ ] Decommission old infrastructure after validation period

## 📊 Migration Checklist

### Pre-Migration Requirements
- [ ] Nexus main server access credentials and permissions
- [ ] Server hardware specifications verification (CPU, RAM, Storage)
- [ ] Network connectivity and bandwidth testing
- [ ] Server storage capacity planning
- [ ] Server OS and Docker compatibility verification
- [ ] Performance baseline documentation from current system

### Migration Components
- [ ] Backend API services (FastAPI) - Server deployment
- [ ] Frontend application (React) - Server deployment
- [ ] PostgreSQL database - Server instance
- [ ] Redis cache/queue - Server instance
- [ ] Background task processors - Server containers
- [ ] Agent orchestration services - Server containers
- [ ] Caddy reverse proxy - Server configuration
- [ ] SSL certificates and security - Server setup
- [ ] Monitoring and logging - Server infrastructure
- [ ] File uploads and assets - Server storage
- [ ] Environment configurations - Server variables
- [ ] Backup systems - Server procedures

### Post-Migration Validation
- [ ] All BaseLayer services healthy on server
- [ ] Database connectivity and data integrity verified
- [ ] API endpoints responding correctly on server
- [ ] User workflows functional on server deployment
- [ ] Server performance metrics within acceptable ranges
- [ ] Server security controls validated
- [ ] Server backup systems operational
- [ ] Server monitoring and alerting functional

## 🔧 Technical Specifications

### Nexus Main Server Requirements
- **Operating System**: Ubuntu 22.04 LTS or RHEL 8+
- **CPU**: Minimum 4 cores (recommended 8+ cores)
- **Memory**: Minimum 16GB RAM (recommended 32GB+)
- **Storage**: Minimum 500GB SSD (recommended 1TB+ NVMe)
- **Network**: 1Gbps+ connectivity with static IP
- **Docker**: Latest Docker Engine and Docker Compose
- **Security**: Firewall configuration, SSL certificates
- **Monitoring**: System monitoring and log aggregation
- **Backup**: Automated backup procedures and storage

### Server Migration Tools
- **Database**: pg_dump/pg_restore for PostgreSQL migration
- **Files**: rsync or scp for file transfer to server
- **Containers**: Docker image transfer to server registry
- **Configuration**: Ansible or manual server configuration
- **Monitoring**: Prometheus/Grafana server setup
- **Backup**: Server-native backup solutions

## 🚨 Risk Mitigation

### Server-Specific Risks
1. **Hardware Compatibility**: Verify server meets BaseLayer requirements
2. **Network Configuration**: Ensure proper port access and firewall rules
3. **Resource Contention**: Monitor server resource utilization during migration
4. **Security Access**: Manage server credentials and access controls
5. **Service Dependencies**: Ensure all server services start in correct order
6. **Data Transfer Speed**: Plan for large database/file transfer times
7. **Server Downtime**: Minimize service interruption during cutover

### Server Rollback Plan
- [ ] Documented server rollback procedures
- [ ] Preserve current infrastructure during migration period
- [ ] Server data restoration capabilities verified
- [ ] Communication protocols for server downtime
- [ ] DNS fallback to original system if needed
- [ ] Server state snapshots before major changes

## 📈 Success Metrics

### Server Migration Technical Metrics
- 99.9% uptime during server migration
- <5 second API response times on server
- Zero data loss or corruption during transfer
- All BaseLayer workflows functional on server
- Server resource utilization <80% under normal load
- Server backup and recovery procedures tested
- Server security controls validated and operational

### Business Metrics
- No user-facing disruptions during server migration
- All BaseLayer integrations maintained on server
- Compliance requirements met in server environment
- Performance improvements achieved on server hardware
- Reduced operational costs through server consolidation
- Enhanced security through centralized server management

---

## 🎯 Server Migration Commands

### Pre-Migration Server Assessment
```bash
# Check server specifications
nproc  # CPU cores
free -h  # Memory
df -h  # Storage
lsb_release -a  # OS version

# Check Docker installation
docker --version
docker-compose --version

# Check network configuration
ip addr show
netstat -tulpn
```

### Server Preparation Commands
```bash
# Update server packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create BaseLayer directories
sudo mkdir -p /opt/baselayer/{data,logs,uploads,backups}
sudo chown -R $USER:$USER /opt/baselayer
```

### Database Migration Commands
```bash
# Export from current system
pg_dump -h localhost -U baselayer baselayer_prod > baselayer_backup.sql

# Transfer to server
scp baselayer_backup.sql user@nexus-server:/tmp/

# Import on server
psql -h localhost -U baselayer baselayer_prod < /tmp/baselayer_backup.sql
```

### Application Deployment Commands
```bash
# Transfer BaseLayer code to server
rsync -avz /path/to/baselayer/ user@nexus-server:/opt/baselayer/

# Deploy on server
cd /opt/baselayer
docker-compose -f infra/docker-compose.prod.yml up -d

# Check service status
docker-compose ps
docker-compose logs -f
```

### Server Monitoring Commands
```bash
# Monitor server resources
htop
iotop
docker stats

# Check service health
curl -f http://localhost:8000/health/health
docker-compose exec backend curl -f http://localhost:8000/health/health
```

---

## 📋 Server Migration Final Steps

### Immediate Actions Required
1. **Verify Server Specifications**
   - Confirm server meets minimum requirements (4 cores, 16GB RAM, 500GB SSD)
   - Validate OS compatibility (Ubuntu 22.04 LTS or RHEL 8+)
   - Check network bandwidth and static IP availability

2. **Schedule Migration Window**
   - Plan maintenance window for minimal user impact
   - Communicate migration timeline to stakeholders
   - Prepare rollback communication plan

3. **Prepare Server Access**
   - Obtain server credentials and SSH access
   - Configure SSH keys for secure access
   - Set up multi-factor authentication if required

4. **Backup Current System**
   - Create full database backup
   - Backup all configuration files
   - Document current system state

### Migration Execution Order
1. **Server Setup** → Install dependencies, configure Docker
2. **Data Transfer** → Migrate database and files
3. **Application Deployment** → Deploy BaseLayer containers
4. **Testing** → Validate all functionality
5. **DNS Cutover** → Update to point to server
6. **Optimization** → Tune performance for server hardware
7. **Decommission** → Remove old infrastructure after validation

### Post-Migration Monitoring
- Monitor server resource utilization for 72 hours
- Validate all automated workflows are functioning
- Check backup procedures are working correctly
- Verify security controls are operational
- Document lessons learned and improvements

This integration plan provides a complete roadmap for migrating your BaseLayer multi-agent system to the Nexus main server with minimal downtime and maximum reliability.
