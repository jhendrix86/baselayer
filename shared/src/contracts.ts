/**
 * BaseLayer API Contracts
 * 
 * Defines API endpoint contracts with request/response schemas
 * for frontend-backend type safety.
 */

// API endpoint definitions
export interface ApiContract {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  path: string
  version: string
  request?: any
  response?: any
  error?: any
}

// Health API contracts
export const HEALTH_CONTRACTS = {
  GET_HEALTH: {
    method: 'GET' as const,
    path: '/health/health',
    version: 'v1',
    response: {
      status: 'string',
      service: 'string',
      version: 'string',
      timestamp: 'string',
    },
  },
  GET_READY: {
    method: 'GET' as const,
    path: '/health/ready',
    version: 'v1',
    response: {
      status: 'string',
      timestamp: 'string',
      services: {
        database: { status: 'string', timestamp: 'string', details?: 'string' },
        redis: { status: 'string', timestamp: 'string', details?: 'string' },
        ollama: { status: 'string', timestamp: 'string', details?: 'string' },
      },
    },
  },
  GET_LIVE: {
    method: 'GET' as const,
    path: '/health/live',
    version: 'v1',
    response: {
      status: 'string',
      timestamp: 'string',
      uptime: 'string',
    },
  },
  GET_DETAILED_HEALTH: {
    method: 'GET' as const,
    path: '/health/detailed',
    version: 'v1',
    response: {
      status: 'string',
      timestamp: 'string',
      version: 'string',
      environment: 'string',
      services: 'object',
      system: 'object',
      governance: 'object',
    },
  },
} as const

// Metrics API contracts
export const METRICS_CONTRACTS = {
  GET_METRICS_INDEX: {
    method: 'GET' as const,
    path: '/metrics/',
    version: 'v1',
    response: {
      service: 'string',
      version: 'string',
      format: 'string',
      endpoints: 'object',
      metrics: 'object',
    },
  },
  GET_PROMETHEUS_METRICS: {
    method: 'GET' as const,
    path: '/metrics/prometheus',
    version: 'v1',
    response: 'string', // Prometheus format text
  },
  GET_METRICS_HEALTH: {
    method: 'GET' as const,
    path: '/metrics/health',
    version: 'v1',
    response: {
      status: 'string',
      service: 'string',
      timestamp: 'number',
    },
  },
} as const

// Auth API contracts
export const AUTH_CONTRACTS = {
  POST_LOGIN: {
    method: 'POST' as const,
    path: '/api/v1/auth/login',
    version: 'v1',
    request: {
      username: 'string',
      password: 'string',
    },
    response: {
      access_token: 'string',
      refresh_token: 'string',
      token_type: 'string',
      expires_in: 'number',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  POST_REFRESH: {
    method: 'POST' as const,
    path: '/api/v1/auth/refresh',
    version: 'v1',
    request: {
      refresh_token: 'string',
    },
    response: {
      access_token: 'string',
      token_type: 'string',
      expires_in: 'number',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  POST_LOGOUT: {
    method: 'POST' as const,
    path: '/api/v1/auth/logout',
    version: 'v1',
    request: {
      refresh_token: 'string',
    },
    response: {
      message: 'string',
    },
  },
  GET_ME: {
    method: 'GET' as const,
    path: '/api/v1/auth/me',
    version: 'v1',
    response: {
      id: 'string',
      username: 'string',
      email: 'string',
      role: 'string',
      is_active: 'boolean',
      created_at: 'string',
      updated_at: 'string',
      last_login: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
} as const

// Core Loop API contracts
export const CORE_LOOP_CONTRACTS = {
  GET_WORKFLOWS: {
    method: 'GET' as const,
    path: '/api/v1/core-loop/workflows',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      status: 'string',
      priority: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_WORKFLOW: {
    method: 'POST' as const,
    path: '/api/v1/core-loop/workflows',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      config: 'object',
      schedule: 'object',
      tags: 'array',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      status: 'string',
      priority: 'string',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_WORKFLOW: {
    method: 'GET' as const,
    path: '/api/v1/core-loop/workflows/{id}',
    version: 'v1',
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      status: 'string',
      priority: 'string',
      config: 'object',
      schedule: 'object',
      tags: 'array',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_WORKFLOW: {
    method: 'PUT' as const,
    path: '/api/v1/core-loop/workflows/{id}',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      config: 'object',
      schedule: 'object',
      tags: 'array',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      status: 'string',
      priority: 'string',
      config: 'object',
      schedule: 'object',
      tags: 'array',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_WORKFLOW: {
    method: 'DELETE' as const,
    path: '/api/v1/core-loop/workflows/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  POST_WORKFLOW_EXECUTE: {
    method: 'POST' as const,
    path: '/api/v1/core-loop/workflows/{id}/execute',
    version: 'v1',
    request: {
      variables: 'object',
    },
    response: {
      execution_id: 'string',
      workflow_id: 'string',
      status: 'string',
      started_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  GET_WORKFLOW_EXECUTIONS: {
    method: 'GET' as const,
    path: '/api/v1/core-loop/workflows/{id}/executions',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      status: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
} as const

// Income Engine API contracts
export const INCOME_ENGINE_CONTRACTS = {
  GET_REVENUE_STREAMS: {
    method: 'GET' as const,
    path: '/api/v1/income-engine/revenue-streams',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      type: 'string',
      status: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_REVENUE_STREAM: {
    method: 'POST' as const,
    path: '/api/v1/income-engine/revenue-streams',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      type: 'string',
      config: 'object',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      type: 'string',
      status: 'string',
      config: 'object',
      metrics: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_REVENUE_STREAM: {
    method: 'GET' as const,
    path: '/api/v1/income-engine/revenue-streams/{id}',
    version: 'v1',
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      type: 'string',
      status: 'string',
      config: 'object',
      metrics: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_REVENUE_STREAM: {
    method: 'PUT' as const,
    path: '/api/v1/income-engine/revenue-streams/{id}',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      config: 'object',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      type: 'string',
      status: 'string',
      config: 'object',
      metrics: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_REVENUE_STREAM: {
    method: 'DELETE' as const,
    path: '/api/v1/income-engine/revenue-streams/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  GET_REVENUE_METRICS: {
    method: 'GET' as const,
    path: '/api/v1/income-engine/metrics',
    version: 'v1',
    request: {
      period: 'string',
      stream_id: 'string',
    },
    response: {
      total_revenue: 'number',
      monthly_revenue: 'number',
      active_customers: 'number',
      churn_rate: 'number',
      average_revenue_per_user: 'number',
      period_start: 'string',
      period_end: 'string',
    },
  },
} as const

// Codex API contracts
export const CODEX_CONTRACTS = {
  GET_KNOWLEDGE_ENTRIES: {
    method: 'GET' as const,
    path: '/api/v1/codex/knowledge',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      type: 'string',
      category: 'string',
      tags: 'array',
      search: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_KNOWLEDGE_ENTRY: {
    method: 'POST' as const,
    path: '/api/v1/codex/knowledge',
    version: 'v1',
    request: {
      title: 'string',
      content: 'string',
      type: 'string',
      category: 'string',
      tags: 'array',
      metadata: 'object',
    },
    response: {
      id: 'string',
      title: 'string',
      content: 'string',
      type: 'string',
      category: 'string',
      tags: 'array',
      metadata: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_KNOWLEDGE_ENTRY: {
    method: 'GET' as const,
    path: '/api/v1/codex/knowledge/{id}',
    version: 'v1',
    response: {
      id: 'string',
      title: 'string',
      content: 'string',
      type: 'string',
      category: 'string',
      tags: 'array',
      metadata: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_KNOWLEDGE_ENTRY: {
    method: 'PUT' as const,
    path: '/api/v1/codex/knowledge/{id}',
    version: 'v1',
    request: {
      title: 'string',
      content: 'string',
      type: 'string',
      category: 'string',
      tags: 'array',
      metadata: 'object',
    },
    response: {
      id: 'string',
      title: 'string',
      content: 'string',
      type: 'string',
      category: 'string',
      tags: 'array',
      metadata: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_KNOWLEDGE_ENTRY: {
    method: 'DELETE' as const,
    path: '/api/v1/codex/knowledge/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  SEARCH_KNOWLEDGE: {
    method: 'POST' as const,
    path: '/api/v1/codex/knowledge/search',
    version: 'v1',
    request: {
      query: 'string',
      type: 'string',
      category: 'string',
      tags: 'array',
      limit: 'number',
    },
    response: {
      items: 'array',
      total: 'number',
      query: 'string',
      search_time_ms: 'number',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
} as const

// Protocol Libraries API contracts
export const PROTOCOLS_CONTRACTS = {
  GET_PROTOCOLS: {
    method: 'GET' as const,
    path: '/api/v1/protocols',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      category: 'string',
      tags: 'array',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_PROTOCOL: {
    method: 'POST' as const,
    path: '/api/v1/protocols',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      category: 'string',
      version: 'string',
      template: 'object',
      documentation: 'string',
      examples: 'array',
      tags: 'array',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      category: 'string',
      version: 'string',
      template: 'object',
      documentation: 'string',
      examples: 'array',
      tags: 'array',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_PROTOCOL: {
    method: 'GET' as const,
    path: '/api/v1/protocols/{id}',
    version: 'v1',
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      category: 'string',
      version: 'string',
      template: 'object',
      documentation: 'string',
      examples: 'array',
      tags: 'array',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_PROTOCOL: {
    method: 'PUT' as const,
    path: '/api/v1/protocols/{id}',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      template: 'object',
      documentation: 'string',
      examples: 'array',
      tags: 'array',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      category: 'string',
      version: 'string',
      template: 'object',
      documentation: 'string',
      examples: 'array',
      tags: 'array',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_PROTOCOL: {
    method: 'DELETE' as const,
    path: '/api/v1/protocols/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
} as const

// Agents API contracts
export const AGENTS_CONTRACTS = {
  GET_AGENTS: {
    method: 'GET' as const,
    path: '/api/v1/agents',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      type: 'string',
      status: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_AGENT: {
    method: 'POST' as const,
    path: '/api/v1/agents',
    version: 'v1',
    request: {
      name: 'string',
      type: 'string',
      config: 'object',
      capabilities: 'array',
    },
    response: {
      id: 'string',
      name: 'string',
      type: 'string',
      status: 'string',
      config: 'object',
      capabilities: 'array',
      metrics: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_AGENT: {
    method: 'GET' as const,
    path: '/api/v1/agents/{id}',
    version: 'v1',
    response: {
      id: 'string',
      name: 'string',
      type: 'string',
      status: 'string',
      config: 'object',
      capabilities: 'array',
      metrics: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_AGENT: {
    method: 'PUT' as const,
    path: '/api/v1/agents/{id}',
    version: 'v1',
    request: {
      name: 'string',
      config: 'object',
      capabilities: 'array',
    },
    response: {
      id: 'string',
      name: 'string',
      type: 'string',
      status: 'string',
      config: 'object',
      capabilities: 'array',
      metrics: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_AGENT: {
    method: 'DELETE' as const,
    path: '/api/v1/agents/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  POST_AGENT_TASK: {
    method: 'POST' as const,
    path: '/api/v1/agents/{id}/tasks',
    version: 'v1',
    request: {
      type: 'string',
      input: 'object',
      priority: 'string',
    },
    response: {
      id: 'string',
      agent_id: 'string',
      type: 'string',
      input: 'object',
      status: 'string',
      priority: 'string',
      created_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_AGENT_TASKS: {
    method: 'GET' as const,
    path: '/api/v1/agents/{id}/tasks',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      status: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
} as const

// Governance API contracts
export const GOVERNANCE_CONTRACTS = {
  GET_RULES: {
    method: 'GET' as const,
    path: '/api/v1/governance/rules',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      category: 'string',
      status: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_RULE: {
    method: 'POST' as const,
    path: '/api/v1/governance/rules',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      category: 'string',
      type: 'string',
      conditions: 'array',
      actions: 'array',
      priority: 'string',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      category: 'string',
      type: 'string',
      conditions: 'array',
      actions: 'array',
      priority: 'string',
      status: 'string',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_RULE: {
    method: 'GET' as const,
    path: '/api/v1/governance/rules/{id}',
    version: 'v1',
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      category: 'string',
      type: 'string',
      conditions: 'array',
      actions: 'array',
      priority: 'string',
      status: 'string',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_RULE: {
    method: 'PUT' as const,
    path: '/api/v1/governance/rules/{id}',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      conditions: 'array',
      actions: 'array',
      priority: 'string',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      category: 'string',
      type: 'string',
      conditions: 'array',
      actions: 'array',
      priority: 'string',
      status: 'string',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_RULE: {
    method: 'DELETE' as const,
    path: '/api/v1/governance/rules/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  GET_AUDIT_LOGS: {
    method: 'GET' as const,
    path: '/api/v1/governance/audit-logs',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      action: 'string',
      entity_type: 'string',
      user_id: 'string',
      start_date: 'string',
      end_date: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
} as const

// Output Engine API contracts
export const OUTPUT_ENGINE_CONTRACTS = {
  GET_TEMPLATES: {
    method: 'GET' as const,
    path: '/api/v1/output-engine/templates',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      type: 'string',
      format: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
  POST_TEMPLATE: {
    method: 'POST' as const,
    path: '/api/v1/output-engine/templates',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      type: 'string',
      format: 'string',
      template: 'string',
      variables: 'array',
      config: 'object',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      type: 'string',
      format: 'string',
      template: 'string',
      variables: 'array',
      config: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_TEMPLATE: {
    method: 'GET' as const,
    path: '/api/v1/output-engine/templates/{id}',
    version: 'v1',
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      type: 'string',
      format: 'string',
      template: 'string',
      variables: 'array',
      config: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  PUT_TEMPLATE: {
    method: 'PUT' as const,
    path: '/api/v1/output-engine/templates/{id}',
    version: 'v1',
    request: {
      name: 'string',
      description: 'string',
      template: 'string',
      variables: 'array',
      config: 'object',
    },
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      type: 'string',
      format: 'string',
      template: 'string',
      variables: 'array',
      config: 'object',
      created_at: 'string',
      updated_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  DELETE_TEMPLATE: {
    method: 'DELETE' as const,
    path: '/api/v1/output-engine/templates/{id}',
    version: 'v1',
    response: {
      message: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
    },
  },
  POST_GENERATE_OUTPUT: {
    method: 'POST' as const,
    path: '/api/v1/output-engine/generate',
    version: 'v1',
    request: {
      template_id: 'string',
      variables: 'object',
      config: 'object',
    },
    response: {
      id: 'string',
      template_id: 'string',
      name: 'string',
      format: 'string',
      content: 'string',
      metadata: 'object',
      delivery_status: 'string',
      created_at: 'string',
    },
    error: {
      code: 'string',
      message: 'string',
      details: 'object',
    },
  },
  GET_OUTPUTS: {
    method: 'GET' as const,
    path: '/api/v1/output-engine/outputs',
    version: 'v1',
    request: {
      page: 'number',
      limit: 'number',
      template_id: 'string',
      format: 'string',
      delivery_status: 'string',
    },
    response: {
      items: 'array',
      total: 'number',
      page: 'number',
      limit: 'number',
      total_pages: 'number',
    },
  },
} as const

// WebSocket contracts
export const WEBSOCKET_CONTRACTS = {
  AGENT_STATUS_UPDATE: {
    type: 'agent_status_update',
    data: {
      agent_id: 'string',
      status: 'string',
      metrics: 'object',
    },
  },
  WORKFLOW_PROGRESS_UPDATE: {
    type: 'workflow_progress_update',
    data: {
      workflow_id: 'string',
      status: 'string',
      current_step: 'string',
      progress_percent: 'number',
    },
  },
  SYSTEM_ALERT: {
    type: 'system_alert',
    data: {
      level: 'string',
      message: 'string',
      source: 'string',
      metadata: 'object',
    },
  },
} as const

// Error contracts
export const ERROR_CONTRACTS = {
  VALIDATION_ERROR: {
    code: 'VALIDATION_ERROR',
    message: 'Request validation failed',
    details: 'object',
  },
  AUTHENTICATION_ERROR: {
    code: 'AUTHENTICATION_ERROR',
    message: 'Authentication failed',
    details: 'object',
  },
  AUTHORIZATION_ERROR: {
    code: 'AUTHORIZATION_ERROR',
    message: 'Insufficient permissions',
    details: 'object',
  },
  NOT_FOUND_ERROR: {
    code: 'NOT_FOUND_ERROR',
    message: 'Resource not found',
    details: 'object',
  },
  CONFLICT_ERROR: {
    code: 'CONFLICT_ERROR',
    message: 'Resource conflict',
    details: 'object',
  },
  RATE_LIMIT_ERROR: {
    code: 'RATE_LIMIT_ERROR',
    message: 'Rate limit exceeded',
    details: 'object',
  },
  INTERNAL_ERROR: {
    code: 'INTERNAL_ERROR',
    message: 'Internal server error',
    details: 'object',
  },
  SERVICE_UNAVAILABLE_ERROR: {
    code: 'SERVICE_UNAVAILABLE_ERROR',
    message: 'Service temporarily unavailable',
    details: 'object',
  },
} as const
