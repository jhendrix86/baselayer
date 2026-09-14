# BaseLayer

A modular, governance-grade operational system with 7 subsystems for self-hosted deployment.

## Architecture

- **Core Loop**: Workflow orchestration engine
- **Income Engine**: Automated revenue pipelines
- **Codex/Memory**: Persistent knowledge store
- **Protocol Libraries**: Reusable workflow templates
- **Multi-Agent Orchestration**: Pipeline coordination across local AI models
- **Governance/Doctrine**: Rules engine and audit trails
- **Output Engineering**: Artifact generation and delivery

## Tech Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0 + PostgreSQL 16
- **Frontend**: React 19 + Vite 6 + Tailwind CSS 4
- **Database**: PostgreSQL 16 + Redis 7
- **Auth**: Custom JWT (python-jose + Argon2)
- **Deployment**: Docker Compose + Caddy + systemd
- **AI**: Ollama integration (CPU-only, qwen2.5-coder:3b)
- **Monitoring**: Netdata integration

## Monorepo Structure

```
baselayer/
├── backend/          # FastAPI application
├── frontend/         # React dashboard
├── shared/           # Types and contracts
├── agents/           # Multi-agent orchestration
├── protocols/        # Reusable workflow templates
└── infra/            # Docker, Caddy, systemd
```

## Quick Start

```bash
# Development
docker-compose -f infra/docker-compose.dev.yml up

# Production
docker-compose -f infra/docker-compose.prod.yml up
```

## Hardware Requirements

- CPU: Intel i5-2400 quad-core 3.10GHz
- RAM: 16GB DDR3
- Storage: 2x1TB HDD
- OS: Ubuntu 22.04 LTS

## Governance

This project operates under the NODEDEMAND Governance Megasuite with SYS-CRP requirements compliance.

## Business Context

This repo is engineering-only. Business, brand, and venture context lives in
the **Empire OS** Notion workspace:

- [Command Center](https://app.notion.com/p/3a703d47c57e81d4aaf3d1136bc94b55) — master index
- [TALORA — Build Status & Capability Log](https://app.notion.com/p/3cf03d47c57e8192b87ef6f2003323c6) — tracks this repo's build state from the business side

Notion's log currently shows this repo's CI as failing (Backend job,
`test_auth.py`, run #9, 2026-09-07) and not yet deployed as the production
automation hub — confirm current state in this repo directly before trusting
that log, since it may be stale.
