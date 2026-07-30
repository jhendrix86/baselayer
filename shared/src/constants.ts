/**
 * BaseLayer Shared Constants
 * 
 * Common constants used across frontend and backend.
 */

// Application constants
export const APP_NAME = 'BaseLayer'
export const APP_VERSION = '0.1.0'
export const APP_DESCRIPTION = 'A modular, governance-grade operational system'

// API constants
export const API_VERSION = 'v1'
export const API_BASE_URL = '/api/v1'
export const DEFAULT_PAGE_SIZE = 20
export const MAX_PAGE_SIZE = 100

// Pagination constants
export const PAGINATION_DEFAULTS = {
  page: 1,
  limit: 20,
  maxLimit: 100,
} as const

// Date/time constants
export const DATE_FORMATS = {
  ISO: 'YYYY-MM-DDTHH:mm:ss.sssZ',
  DATE_ONLY: 'YYYY-MM-DD',
  TIME_ONLY: 'HH:mm:ss',
  READABLE: 'MMM DD, YYYY HH:mm',
  SHORT: 'MMM DD, YYYY',
} as const

export const TIME_UNITS = {
  MILLISECOND: 1,
  SECOND: 1000,
  MINUTE: 60 * 1000,
  HOUR: 60 * 60 * 1000,
  DAY: 24 * 60 * 60 * 1000,
  WEEK: 7 * 24 * 60 * 60 * 1000,
  MONTH: 30 * 24 * 60 * 60 * 1000,
  YEAR: 365 * 24 * 60 * 60 * 1000,
} as const

// Validation constants
export const VALIDATION_RULES = {
  USERNAME_MIN_LENGTH: 3,
  USERNAME_MAX_LENGTH: 50,
  PASSWORD_MIN_LENGTH: 8,
  PASSWORD_MAX_LENGTH: 128,
  EMAIL_MAX_LENGTH: 255,
  NAME_MIN_LENGTH: 1,
  NAME_MAX_LENGTH: 100,
  DESCRIPTION_MAX_LENGTH: 1000,
  TITLE_MAX_LENGTH: 200,
  TAG_MAX_LENGTH: 50,
  MAX_TAGS: 10,
} as const

// File upload constants
export const FILE_UPLOAD = {
  MAX_FILE_SIZE: 5 * 1024 * 1024, // 5MB
  ALLOWED_MIME_TYPES: [
    'text/plain',
    'text/markdown',
    'application/json',
    'application/xml',
    'text/csv',
    'application/pdf',
  ],
  ALLOWED_EXTENSIONS: ['.txt', '.md', '.json', '.xml', '.csv', '.pdf'],
} as const

// Rate limiting constants
export const RATE_LIMITS = {
  DEFAULT_REQUESTS_PER_MINUTE: 60,
  AUTH_REQUESTS_PER_MINUTE: 10,
  UPLOAD_REQUESTS_PER_MINUTE: 5,
  SEARCH_REQUESTS_PER_MINUTE: 30,
} as const

// Cache constants
export const CACHE_KEYS = {
  USER_SESSION: 'user_session',
  WORKFLOW_CACHE: 'workflow_cache',
  KNOWLEDGE_CACHE: 'knowledge_cache',
  AGENT_STATUS: 'agent_status',
  SYSTEM_HEALTH: 'system_health',
} as const

export const CACHE_TTL = {
  SHORT: 5 * 60 * 1000, // 5 minutes
  MEDIUM: 30 * 60 * 1000, // 30 minutes
  LONG: 2 * 60 * 60 * 1000, // 2 hours
  VERY_LONG: 24 * 60 * 60 * 1000, // 24 hours
} as const

// WebSocket constants
export const WEBSOCKET_EVENTS = {
  AGENT_STATUS_UPDATE: 'agent_status_update',
  WORKFLOW_PROGRESS_UPDATE: 'workflow_progress_update',
  SYSTEM_ALERT: 'system_alert',
  GOVERNANCE_EVENT: 'governance_event',
  OUTPUT_GENERATED: 'output_generated',
  KNOWLEDGE_UPDATED: 'knowledge_updated',
} as const

export const WEBSOCKET_RECONNECT = {
  MAX_ATTEMPTS: 5,
  INITIAL_DELAY: 1000,
  MAX_DELAY: 30000,
  BACKOFF_FACTOR: 2,
} as const

// Governance constants
export const GOVERNANCE = {
  MODES: ['strict', 'moderate', 'lenient'] as const,
  CATEGORIES: ['security', 'compliance', 'operational', 'quality', 'performance', 'access'] as const,
  PRIORITIES: ['low', 'medium', 'high', 'critical'] as const,
  STATUSES: ['active', 'inactive', 'draft', 'deprecated'] as const,
  RULE_TYPES: ['validation', 'enforcement', 'monitoring', 'audit', 'alerting'] as const,
} as const

export const SYS_CRP_REQUIREMENTS = {
  'CRP-01': 'I/O Specification',
  'CRP-02': 'State Management',
  'CRP-03': 'Error Handling',
  'CRP-04': 'Logging/Observability',
  'CRP-05': 'Performance Thresholds',
  'CRP-06': 'Security Baseline',
  'CRP-07': 'Modularity Standard',
  'CRP-08': 'Interface Contracts',
  'CRP-09': 'Documentation Minimum',
  'CRP-10': 'Doctrine Compliance',
} as const

// System constants
export const SYSTEM = {
  SUBSYSTEMS: [
    'core-loop',
    'income-engine',
    'codex',
    'protocols',
    'agents',
    'governance',
    'output-engine',
  ] as const,
  HEALTH_CHECK_INTERVAL: 30 * 1000, // 30 seconds
  METRICS_COLLECTION_INTERVAL: 60 * 1000, // 1 minute
  AUDIT_RETENTION_DAYS: 365,
  LOG_RETENTION_DAYS: 30,
} as const

// Agent constants
export const AGENT = {
  TYPES: ['worker', 'coordinator', 'supervisor', 'specialist', 'gateway'] as const,
  STATUSES: ['idle', 'busy', 'offline', 'error', 'maintenance'] as const,
  TASK_STATUSES: ['pending', 'running', 'completed', 'failed', 'cancelled'] as const,
  DEFAULT_TIMEOUT: 5 * 60 * 1000, // 5 minutes
  MAX_CONCURRENT_TASKS: 10,
} as const

// Workflow constants
export const WORKFLOW = {
  STATUSES: ['draft', 'active', 'paused', 'completed', 'failed', 'cancelled'] as const,
  PRIORITIES: ['low', 'medium', 'high', 'critical'] as const,
  STEP_TYPES: ['task', 'decision', 'parallel', 'delay', 'webhook', 'agent'] as const,
  SCHEDULE_TYPES: ['once', 'recurring', 'cron'] as const,
  BACKOFF_TYPES: ['fixed', 'linear', 'exponential'] as const,
  DEFAULT_TIMEOUT: 60 * 60 * 1000, // 1 hour
  MAX_STEPS: 100,
} as const

// Knowledge constants
export const KNOWLEDGE = {
  TYPES: ['document', 'note', 'procedure', 'policy', 'template', 'code'] as const,
  MAX_CONTENT_SIZE: 10 * 1024 * 1024, // 10MB
  SEARCH_LIMIT: 50,
  EMBEDDING_DIMENSIONS: 1536, // OpenAI ada-002 dimensions
} as const

// Protocol constants
export const PROTOCOL = {
  CATEGORIES: ['workflow', 'automation', 'integration', 'security', 'compliance', 'monitoring'] as const,
  VARIABLE_TYPES: ['string', 'number', 'boolean', 'array', 'object', 'file'] as const,
  VALIDATION_TYPES: ['required', 'min_length', 'max_length', 'min_value', 'max_value', 'pattern', 'custom'] as const,
  MAX_VARIABLES: 50,
  MAX_STEPS: 100,
} as const

// Output constants
export const OUTPUT = {
  TYPES: ['report', 'document', 'email', 'notification', 'dashboard', 'export'] as const,
  FORMATS: ['html', 'pdf', 'json', 'csv', 'xml', 'markdown', 'plain_text'] as const,
  DELIVERY_METHODS: ['email', 'webhook', 'file', 'api', 'ftp', 'sms'] as const,
  DELIVERY_STATUSES: ['pending', 'delivered', 'failed', 'retrying'] as const,
  MAX_TEMPLATE_SIZE: 1 * 1024 * 1024, // 1MB
  MAX_OUTPUT_SIZE: 50 * 1024 * 1024, // 50MB
} as const

// Revenue constants
export const REVENUE = {
  TYPES: ['subscription', 'one_time', 'usage_based', 'commission', 'licensing'] as const,
  STATUSES: ['active', 'inactive', 'pending', 'suspended'] as const,
  PRICING_MODELS: ['fixed', 'tiered', 'usage_based', 'dynamic'] as const,
  BILLING_CYCLES: ['monthly', 'quarterly', 'yearly', 'custom'] as const,
  CURRENCIES: ['USD', 'EUR', 'GBP', 'JPY', 'CNY'] as const,
} as const

// Error codes
export const ERROR_CODES = {
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  AUTHENTICATION_ERROR: 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR: 'AUTHORIZATION_ERROR',
  NOT_FOUND_ERROR: 'NOT_FOUND_ERROR',
  CONFLICT_ERROR: 'CONFLICT_ERROR',
  RATE_LIMIT_ERROR: 'RATE_LIMIT_ERROR',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  SERVICE_UNAVAILABLE_ERROR: 'SERVICE_UNAVAILABLE_ERROR',
  DATABASE_ERROR: 'DATABASE_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT_ERROR: 'TIMEOUT_ERROR',
  FILE_ERROR: 'FILE_ERROR',
  PERMISSION_ERROR: 'PERMISSION_ERROR',
  QUOTA_EXCEEDED_ERROR: 'QUOTA_EXCEEDED_ERROR',
  CONFIGURATION_ERROR: 'CONFIGURATION_ERROR',
  DEPENDENCY_ERROR: 'DEPENDENCY_ERROR',
} as const

// HTTP status codes
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  ACCEPTED: 202,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  METHOD_NOT_ALLOWED: 405,
  CONFLICT: 409,
  UNPROCESSABLE_ENTITY: 422,
  TOO_MANY_REQUESTS: 429,
  INTERNAL_SERVER_ERROR: 500,
  NOT_IMPLEMENTED: 501,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503,
  GATEWAY_TIMEOUT: 504,
} as const

// Environment constants
export const ENVIRONMENTS = ['development', 'testing', 'staging', 'production'] as const

// Log levels
export const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const

// Theme constants
export const THEME = {
  COLORS: {
    PRIMARY: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
      950: '#172554',
    },
    GOVERNANCE: {
      50: '#f0fdf4',
      100: '#dcfce7',
      200: '#bbf7d0',
      300: '#86efac',
      400: '#4ade80',
      500: '#22c55e',
      600: '#16a34a',
      700: '#15803d',
      800: '#166534',
      900: '#14532d',
      950: '#052e16',
    },
    DANGER: {
      50: '#fef2f2',
      100: '#fee2e2',
      200: '#fecaca',
      300: '#fca5a5',
      400: '#f87171',
      500: '#ef4444',
      600: '#dc2626',
      700: '#b91c1c',
      800: '#991b1b',
      900: '#7f1d1d',
      950: '#450a0a',
    },
  },
  BREAKPOINTS: {
    SM: '640px',
    MD: '768px',
    LG: '1024px',
    XL: '1280px',
    '2XL': '1536px',
  },
} as const

// Regular expressions
export const REGEX_PATTERNS = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  USERNAME: /^[a-zA-Z0-9_-]{3,50}$/,
  PASSWORD: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/,
  SLUG: /^[a-z0-9-]+$/,
  UUID: /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  SEMVER: /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/,
  HEX_COLOR: /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/,
  IPV4: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
  URL: /^https?:\/\/(?:[-\w.])+(?:\:[0-9]+)?(?:\/(?:[\w\/_])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$/,
} as const

// Feature flags
export const FEATURE_FLAGS = {
  ENABLE_AUDIT_LOGGING: true,
  ENABLE_METRICS: true,
  ENABLE_WEBSOCKETS: true,
  ENABLE_FILE_UPLOADS: true,
  ENABLE_EMAIL_NOTIFICATIONS: false,
  ENABLE_SMS_NOTIFICATIONS: false,
  ENABLE_ADVANCED_SEARCH: true,
  ENABLE_REAL_TIME_UPDATES: true,
  ENABLE_BACKUP_AUTOMATION: true,
  ENABLE_PERFORMANCE_MONITORING: true,
} as const

// Default configurations
export const DEFAULT_CONFIGS = {
  WORKFLOW: {
    timeout: 60 * 60 * 1000, // 1 hour
    max_retries: 3,
    retry_delay: 5000, // 5 seconds
  },
  AGENT: {
    max_concurrent_tasks: 5,
    timeout: 5 * 60 * 1000, // 5 minutes
    health_check_interval: 30 * 1000, // 30 seconds
  },
  CACHE: {
    default_ttl: 30 * 60 * 1000, // 30 minutes
    max_size: 1000, // Maximum number of cached items
  },
  RATE_LIMIT: {
    window_ms: 60 * 1000, // 1 minute
    max_requests: 60,
  },
} as const
