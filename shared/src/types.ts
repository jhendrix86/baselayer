/**
 * BaseLayer Shared Types
 * 
 * Common TypeScript interfaces and types used across frontend and backend.
 */

// Base types
export interface BaseEntity {
  id: string
  created_at: string
  updated_at: string
  deleted_at?: string
}

export interface PaginationParams {
  page?: number
  limit?: number
  offset?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
    details?: any
  }
  meta?: {
    request_id?: string
    timestamp: string
    version: string
  }
}

// User and Auth types
export interface User extends BaseEntity {
  username: string
  email: string
  role: UserRole
  is_active: boolean
  last_login?: string
}

export enum UserRole {
  ADMIN = 'admin',
  OPERATOR = 'operator',
  VIEWER = 'viewer',
  AGENT = 'agent'
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RefreshTokenRequest {
  refresh_token: string
}

// Core Loop types
export interface Workflow extends BaseEntity {
  name: string
  description: string
  status: WorkflowStatus
  priority: WorkflowPriority
  config: WorkflowConfig
  schedule?: WorkflowSchedule
  tags: string[]
  created_by: string
}

export enum WorkflowStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export enum WorkflowPriority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface WorkflowConfig {
  steps: WorkflowStep[]
  variables: Record<string, any>
  timeout?: number
  retry_policy?: RetryPolicy
}

export interface WorkflowStep {
  id: string
  name: string
  type: StepType
  config: Record<string, any>
  dependencies: string[]
  timeout?: number
  retry_policy?: RetryPolicy
}

export enum StepType {
  TASK = 'task',
  DECISION = 'decision',
  PARALLEL = 'parallel',
  DELAY = 'delay',
  WEBHOOK = 'webhook',
  AGENT = 'agent'
}

export interface WorkflowSchedule {
  type: ScheduleType
  expression: string
  timezone?: string
}

export enum ScheduleType {
  ONCE = 'once',
  RECURRING = 'recurring',
  CRON = 'cron'
}

export interface RetryPolicy {
  max_attempts: number
  backoff_type: BackoffType
  base_delay: number
  max_delay?: number
}

export enum BackoffType {
  FIXED = 'fixed',
  LINEAR = 'linear',
  EXPONENTIAL = 'exponential'
}

// Income Engine types
export interface RevenueStream extends BaseEntity {
  name: string
  description: string
  type: RevenueType
  status: RevenueStatus
  config: RevenueConfig
  metrics: RevenueMetrics
  created_by: string
}

export enum RevenueType {
  SUBSCRIPTION = 'subscription',
  ONE_TIME = 'one_time',
  USAGE_BASED = 'usage_based',
  COMMISSION = 'commission',
  LICENSING = 'licensing'
}

export enum RevenueStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  PENDING = 'pending',
  SUSPENDED = 'suspended'
}

export interface RevenueConfig {
  pricing_model: PricingModel
  amount?: number
  currency?: string
  billing_cycle?: BillingCycle
  usage_limits?: Record<string, number>
}

export enum PricingModel {
  FIXED = 'fixed',
  TIERED = 'tiered',
  USAGE_BASED = 'usage_based',
  DYNAMIC = 'dynamic'
}

export enum BillingCycle {
  MONTHLY = 'monthly',
  QUARTERLY = 'quarterly',
  YEARLY = 'yearly',
  CUSTOM = 'custom'
}

export interface RevenueMetrics {
  total_revenue: number
  monthly_revenue: number
  active_customers: number
  churn_rate: number
  average_revenue_per_user: number
}

// Codex/Memory types
export interface KnowledgeEntry extends BaseEntity {
  title: string
  content: string
  type: KnowledgeType
  category: string
  tags: string[]
  metadata: KnowledgeMetadata
  embedding?: number[]
  created_by: string
}

export enum KnowledgeType {
  DOCUMENT = 'document',
  NOTE = 'note',
  PROCEDURE = 'procedure',
  POLICY = 'policy',
  TEMPLATE = 'template',
  CODE = 'code'
}

export interface KnowledgeMetadata {
  source?: string
  author?: string
  version?: string
  language?: string
  confidence?: number
  last_reviewed?: string
}

// Protocol Libraries types
export interface Protocol extends BaseEntity {
  name: string
  description: string
  category: ProtocolCategory
  version: string
  template: ProtocolTemplate
  documentation: string
  examples: ProtocolExample[]
  tags: string[]
  created_by: string
}

export enum ProtocolCategory {
  WORKFLOW = 'workflow',
  AUTOMATION = 'automation',
  INTEGRATION = 'integration',
  SECURITY = 'security',
  COMPLIANCE = 'compliance',
  MONITORING = 'monitoring'
}

export interface ProtocolTemplate {
  definition: Record<string, any>
  variables: ProtocolVariable[]
  steps: ProtocolStep[]
}

export interface ProtocolVariable {
  name: string
  type: VariableType
  required: boolean
  default_value?: any
  description: string
  validation?: ValidationRule[]
}

export enum VariableType {
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  ARRAY = 'array',
  OBJECT = 'object',
  FILE = 'file'
}

export interface ValidationRule {
  type: ValidationType
  params: Record<string, any>
  message: string
}

export enum ValidationType {
  REQUIRED = 'required',
  MIN_LENGTH = 'min_length',
  MAX_LENGTH = 'max_length',
  MIN_VALUE = 'min_value',
  MAX_VALUE = 'max_value',
  PATTERN = 'pattern',
  CUSTOM = 'custom'
}

export interface ProtocolStep {
  id: string
  name: string
  type: StepType
  config: Record<string, any>
  description: string
}

export interface ProtocolExample {
  name: string
  description: string
  input: Record<string, any>
  expected_output: Record<string, any>
}

// Multi-Agent Orchestration types
export interface Agent extends BaseEntity {
  name: string
  type: AgentType
  status: AgentStatus
  config: AgentConfig
  capabilities: AgentCapability[]
  metrics: AgentMetrics
  created_by: string
}

export enum AgentType {
  WORKER = 'worker',
  COORDINATOR = 'coordinator',
  SUPERVISOR = 'supervisor',
  SPECIALIST = 'specialist',
  GATEWAY = 'gateway'
}

export enum AgentStatus {
  IDLE = 'idle',
  BUSY = 'busy',
  OFFLINE = 'offline',
  ERROR = 'error',
  MAINTENANCE = 'maintenance'
}

export interface AgentConfig {
  model: string
  max_concurrent_tasks: number
  timeout: number
  retry_policy: RetryPolicy
  resources: ResourceRequirements
}

export interface ResourceRequirements {
  cpu: number
  memory: number
  disk: number
  network?: number
}

export interface AgentCapability {
  name: string
  description: string
  input_types: VariableType[]
  output_types: VariableType[]
  parameters: ProtocolVariable[]
}

export interface AgentMetrics {
  tasks_completed: number
  tasks_failed: number
  average_task_duration: number
  success_rate: number
  resource_usage: ResourceUsage
}

export interface ResourceUsage {
  cpu_percent: number
  memory_mb: number
  disk_mb: number
  network_mb?: number
}

export interface AgentTask extends BaseEntity {
  agent_id: string
  type: string
  input: Record<string, any>
  output?: Record<string, any>
  status: TaskStatus
  priority: WorkflowPriority
  started_at?: string
  completed_at?: string
  error_message?: string
  created_by: string
}

export enum TaskStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

// Governance/Doctrine types
export interface GovernanceRule extends BaseEntity {
  name: string
  description: string
  category: GovernanceCategory
  type: RuleType
  conditions: RuleCondition[]
  actions: RuleAction[]
  priority: GovernancePriority
  status: GovernanceStatus
  created_by: string
}

export enum GovernanceCategory {
  SECURITY = 'security',
  COMPLIANCE = 'compliance',
  OPERATIONAL = 'operational',
  QUALITY = 'quality',
  PERFORMANCE = 'performance',
  ACCESS = 'access'
}

export enum RuleType {
  VALIDATION = 'validation',
  ENFORCEMENT = 'enforcement',
  MONITORING = 'monitoring',
  AUDIT = 'audit',
  ALERTING = 'alerting'
}

export interface RuleCondition {
  field: string
  operator: ConditionOperator
  value: any
  logical_operator?: LogicalOperator
}

export enum ConditionOperator {
  EQUALS = 'equals',
  NOT_EQUALS = 'not_equals',
  GREATER_THAN = 'greater_than',
  LESS_THAN = 'less_than',
  CONTAINS = 'contains',
  STARTS_WITH = 'starts_with',
  ENDS_WITH = 'ends_with',
  REGEX = 'regex',
  IN = 'in',
  NOT_IN = 'not_in'
}

export enum LogicalOperator {
  AND = 'and',
  OR = 'or',
  NOT = 'not'
}

export interface RuleAction {
  type: ActionType
  config: Record<string, any>
  order: number
}

export enum ActionType {
  BLOCK = 'block',
  WARN = 'warn',
  LOG = 'log',
  NOTIFY = 'notify',
  ESCALATE = 'escalate',
  TRANSFORM = 'transform'
}

export enum GovernancePriority {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export enum GovernanceStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  DRAFT = 'draft',
  DEPRECATED = 'deprecated'
}

export interface AuditLog extends BaseEntity {
  action: string
  entity_type: string
  entity_id: string
  user_id: string
  old_values?: Record<string, any>
  new_values?: Record<string, any>
  metadata: AuditMetadata
  ip_address?: string
  user_agent?: string
}

export interface AuditMetadata {
  source: string
  version: string
  request_id?: string
  session_id?: string
}

// Output Engineering types
export interface OutputTemplate extends BaseEntity {
  name: string
  description: string
  type: OutputType
  format: OutputFormat
  template: string
  variables: TemplateVariable[]
  config: OutputConfig
  created_by: string
}

export enum OutputType {
  REPORT = 'report',
  DOCUMENT = 'document',
  EMAIL = 'email',
  NOTIFICATION = 'notification',
  DASHBOARD = 'dashboard',
  EXPORT = 'export'
}

export enum OutputFormat {
  HTML = 'html',
  PDF = 'pdf',
  JSON = 'json',
  CSV = 'csv',
  XML = 'xml',
  MARKDOWN = 'markdown',
  PLAIN_TEXT = 'plain_text'
}

export interface TemplateVariable {
  name: string
  type: VariableType
  required: boolean
  default_value?: any
  description: string
  formatting?: VariableFormatting
}

export interface VariableFormatting {
  date_format?: string
  number_format?: string
  currency?: string
  locale?: string
}

export interface OutputConfig {
  styling?: OutputStyling
  delivery?: DeliveryConfig
  retention?: RetentionConfig
}

export interface OutputStyling {
  theme?: string
  logo_url?: string
  colors?: Record<string, string>
  fonts?: Record<string, string>
}

export interface DeliveryConfig {
  method: DeliveryMethod
  recipients: string[]
  schedule?: WorkflowSchedule
  retry_policy?: RetryPolicy
}

export enum DeliveryMethod {
  EMAIL = 'email',
  WEBHOOK = 'webhook',
  FILE = 'file',
  API = 'api',
  FTP = 'ftp',
  SMS = 'sms'
}

export interface RetentionConfig {
  period_days: number
  archive_location?: string
  compression?: boolean
}

export interface GeneratedOutput extends BaseEntity {
  template_id: string
  name: string
  format: OutputFormat
  content: string
  file_path?: string
  metadata: OutputMetadata
  delivery_status: DeliveryStatus
  created_by: string
}

export interface OutputMetadata {
  size_bytes: number
  generation_time_ms: number
  template_version: string
  variables_used: string[]
}

export enum DeliveryStatus {
  PENDING = 'pending',
  DELIVERED = 'delivered',
  FAILED = 'failed',
  RETRYING = 'retrying'
}

// System types
export interface SystemHealth {
  status: 'healthy' | 'unhealthy' | 'degraded'
  timestamp: string
  services: ServiceHealth[]
  system_metrics: SystemMetrics
}

export interface ServiceHealth {
  name: string
  status: 'healthy' | 'unhealthy'
  response_time_ms?: number
  error_message?: string
  last_check: string
}

export interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  uptime_seconds: number
  active_connections: number
}

// WebSocket types
export interface WebSocketMessage {
  type: string
  data: any
  timestamp: string
  id?: string
}

export interface AgentStatusUpdate extends WebSocketMessage {
  type: 'agent_status_update'
  data: {
    agent_id: string
    status: AgentStatus
    metrics?: Partial<AgentMetrics>
  }
}

export interface WorkflowProgressUpdate extends WebSocketMessage {
  type: 'workflow_progress_update'
  data: {
    workflow_id: string
    status: WorkflowStatus
    current_step?: string
    progress_percent: number
  }
}

export interface SystemAlert extends WebSocketMessage {
  type: 'system_alert'
  data: {
    level: 'info' | 'warning' | 'error' | 'critical'
    message: string
    source: string
    metadata?: Record<string, any>
  }
}
