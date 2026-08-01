"""
BaseLayer Governance/Doctrine Models

Governance rules, audit logging, and compliance tracking
for the Governance/Doctrine subsystem.
"""

from datetime import datetime

import uuid
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import BaseModel, UUIDType


class GovernanceCategory(str, Enum):
    """Governance rule categories."""
    SECURITY = "security"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    QUALITY = "quality"
    PERFORMANCE = "performance"
    ACCESS = "access"


class GovernancePriority(str, Enum):
    """Governance rule priorities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GovernanceStatus(str, Enum):
    """Governance rule status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


class RuleType(str, Enum):
    """Governance rule types."""
    VALIDATION = "validation"
    ENFORCEMENT = "enforcement"
    MONITORING = "monitoring"
    AUDIT = "audit"
    ALERTING = "alerting"


class AuditLevel(str, Enum):
    """Audit logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComplianceStatus(str, Enum):
    """Compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING = "pending"
    EXEMPT = "exempt"


class GovernanceRule(BaseModel):
    """
    Governance rule model for Governance/Doctrine subsystem.
    
    Defines governance rules with validation, enforcement, and monitoring capabilities.
    """
    
    __tablename__ = "governance_rules"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Governance rule name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Rule description"
    )
    
    # Categorization
    category: Mapped[GovernanceCategory] = mapped_column(
        ENUM(GovernanceCategory, name="governance_category"),
        nullable=False,
        index=True,
        comment="Rule category"
    )
    
    priority: Mapped[GovernancePriority] = mapped_column(
        ENUM(GovernancePriority, name="governance_priority"),
        nullable=False,
        default=GovernancePriority.MEDIUM,
        index=True,
        comment="Rule priority"
    )
    
    status: Mapped[GovernanceStatus] = mapped_column(
        ENUM(GovernanceStatus, name="governance_status"),
        nullable=False,
        default=GovernanceStatus.DRAFT,
        index=True,
        comment="Current rule status"
    )
    
    # Rule definition
    rule_type: Mapped[RuleType] = mapped_column(
        ENUM(RuleType, name="rule_type"),
        nullable=False,
        index=True,
        comment="Type of governance rule"
    )
    
    rule_definition: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Complete rule definition"
    )
    
    # Conditions and triggers
    conditions: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Conditions for rule application"
    )
    
    triggers: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Events that trigger the rule"
    )
    
    # Actions and enforcement
    actions: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Actions to take when rule is triggered"
    )
    
    enforcement_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="advisory",
        comment="Enforcement level (advisory, warning, blocking)"
    )
    
    # Compliance requirements
    sys_crp_mapping: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Mapping to SYS-CRP requirements"
    )
    
    maturity_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1",
        comment="Maturity level (1-5)"
    )
    
    # Monitoring and alerting
    monitoring_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether monitoring is enabled"
    )
    
    alert_threshold: Mapped[float] = mapped_column(
        String(5),
        nullable=True,
        comment="Threshold for alerting"
    )
    
    alert_recipients: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Alert recipients"
    )
    
    # Version control
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Rule version"
    )
    
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("governance_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent rule for versioning"
    )
    
    # Review and maintenance
    review_frequency_days: Mapped[int] = mapped_column(
        String(5),
        nullable=True,
        comment="Frequency of review in days"
    )
    
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when rule was last reviewed"
    )
    
    next_review_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when next review is due"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="governance_rules",
        foreign_keys="GovernanceRule.created_by",
        lazy="select"
    )
    
    parent = relationship(
        "GovernanceRule",
        remote_side="GovernanceRule.id",
        back_populates="children",
        lazy="select"
    )
    
    children = relationship(
        "GovernanceRule",
        back_populates="parent",
        lazy="select"
    )
    
    audit_logs = relationship(
        "AuditLog",
        back_populates="governance_rule",
        lazy="select"
    )
    
    compliance_reports = relationship(
        "ComplianceReport",
        back_populates="governance_rule",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("name", "deleted_at", name="uq_governance_rule_name_deleted"),
        Index("idx_governance_category_status", "category", "status"),
        Index("idx_governance_priority", "priority"),
        Index("idx_governance_type", "rule_type"),
        Index("idx_governance_maturity", "maturity_level"),
        {"comment": "Governance rules for compliance and enforcement"}
    )
    
    def __repr__(self) -> str:
        """String representation of the governance rule."""
        return f"<GovernanceRule(name='{self.name}', category='{self.category}', status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if rule is active."""
        return self.status == GovernanceStatus.ACTIVE
    
    @property
    def is_critical(self) -> bool:
        """Check if rule is critical priority."""
        return self.priority == GovernancePriority.CRITICAL
    
    @property
    def requires_enforcement(self) -> bool:
        """Check if rule requires enforcement."""
        return self.rule_type in {RuleType.ENFORCEMENT, RuleType.VALIDATION}
    
    def activate(self) -> None:
        """Activate the governance rule."""
        self.status = GovernanceStatus.ACTIVE
        self.increment_version()
    
    def deactivate(self) -> None:
        """Deactivate the governance rule."""
        self.status = GovernanceStatus.INACTIVE
        self.increment_version()
    
    def deprecate(self) -> None:
        """Deprecate the governance rule."""
        self.status = GovernanceStatus.DEPRECATED
        self.increment_version()
    
    def schedule_review(self, frequency_days: int) -> None:
        """
        Schedule the next review.
        
        Args:
            frequency_days: Review frequency in days
        """
        self.review_frequency_days = str(frequency_days)
        self.last_reviewed_at = datetime.utcnow()
        self.next_review_at = datetime.utcnow() + datetime.timedelta(days=frequency_days)
    
    def evaluate_condition(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate rule conditions against context.
        
        Args:
            context: Context data for evaluation
            
        Returns:
            bool: True if conditions are met
        """
        # TODO: Implement condition evaluation logic
        return True
    
    def execute_actions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute rule actions.
        
        Args:
            context: Context data for execution
            
        Returns:
            Dict[str, Any]: Action results
        """
        # TODO: Implement action execution logic
        return {"executed": True, "actions": []}
    
    def update_sys_crp_mapping(self, crp_requirements: Dict[str, Any]) -> None:
        """
        Update SYS-CRP requirement mapping.
        
        Args:
            crp_requirements: SYS-CRP requirements mapping
        """
        self.sys_crp_mapping = crp_requirements
        self.increment_version()


class AuditLog(BaseModel):
    """
    Audit log model.
    
    Tracks all system events and actions for compliance and security auditing.
    """
    
    __tablename__ = "audit_logs"
    
    # Event details
    event_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique event identifier"
    )
    
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of event"
    )
    
    event_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Event category"
    )
    
    # User and session information
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of user who performed the action"
    )
    
    username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Username of the user"
    )
    
    session_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Session identifier"
    )
    
    # Resource information
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of resource affected"
    )
    
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of resource affected"
    )
    
    resource_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Name of resource affected"
    )
    
    # Action details
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Action performed"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the action"
    )
    
    # Timing information
    timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Event timestamp"
    )
    
    duration_ms: Mapped[int] = mapped_column(
        String(10),
        nullable=True,
        comment="Action duration in milliseconds"
    )
    
    # Request information
    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Request identifier"
    )
    
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of the request"
    )
    
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent string"
    )
    
    # Outcome
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="Action outcome (success, failure, error)"
    )
    
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Error code if action failed"
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if action failed"
    )
    
    # Data changes
    old_values: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous values before change"
    )
    
    new_values: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="New values after change"
    )
    
    # Governance
    governance_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("governance_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Related governance rule"
    )
    
    compliance_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        comment="Compliance level of the action"
    )
    
    # Metadata
    metadata_: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional event metadata"
    )
    
    # Relationships
    governance_rule = relationship(
        "GovernanceRule",
        back_populates="audit_logs",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_outcome", "outcome"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        {"comment": "Audit logs for compliance and security"}
    )
    
    def __repr__(self) -> str:
        """String representation of the audit log."""
        return f"<AuditLog(event_id='{self.event_id}', type='{self.event_type}', outcome='{self.outcome}')>"
    
    @property
    def is_success(self) -> bool:
        """Check if action was successful."""
        return self.outcome == "success"
    
    @property
    def is_failure(self) -> bool:
        """Check if action failed."""
        return self.outcome in {"failure", "error"}
    
    @property
    def has_data_changes(self) -> bool:
        """Check if log contains data changes."""
        return self.old_values is not None or self.new_values is not None
    
    @classmethod
    def create_event(
        cls,
        event_type: str,
        action: str,
        user_id: uuid.UUID | None = None,
        username: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        resource_name: str | None = None,
        description: str | None = None,
        outcome: str = "success",
        old_values: Dict[str, Any] | None = None,
        new_values: Dict[str, Any] | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        metadata_: Dict[str, Any] | None = None
    ) -> "AuditLog":
        """
        Create a new audit log entry.
        
        Args:
            event_type: Type of event
            action: Action performed
            user_id: ID of user
            username: Username
            resource_type: Type of resource
            resource_id: ID of resource
            resource_name: Name of resource
            description: Description
            outcome: Action outcome
            old_values: Previous values
            new_values: New values
            ip_address: IP address
            request_id: Request ID
            metadata_: Additional metadata
            
        Returns:
            AuditLog: New audit log entry
        """
        import uuid
        
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            event_category=event_type.split(".")[0],
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            action=action,
            description=description,
            timestamp=datetime.utcnow(),
            outcome=outcome,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            request_id=request_id,
            metadata_=metadata_
        )


class ComplianceReport(BaseModel):
    """
    Compliance report model.
    
    Tracks compliance status and metrics for governance rules.
    """
    
    __tablename__ = "compliance_reports"
    
    # References
    governance_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("governance_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the governance rule"
    )
    
    # Report period
    report_period_start: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Start of report period"
    )
    
    report_period_end: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="End of report period"
    )
    
    # Compliance status
    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        ENUM(ComplianceStatus, name="compliance_status"),
        nullable=False,
        default=ComplianceStatus.PENDING,
        index=True,
        comment="Current compliance status"
    )
    
    compliance_score: Mapped[float] = mapped_column(
        String(5),
        nullable=True,
        comment="Compliance score (0.0-1.0)"
    )
    
    # Metrics
    total_checks: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Total number of compliance checks"
    )
    
    passed_checks: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of passed checks"
    )
    
    failed_checks: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of failed checks"
    )
    
    warning_checks: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of warning checks"
    )
    
    # Violations
    violations: Mapped[list[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of compliance violations"
    )
    
    # Remediation
    remediation_actions: Mapped[list[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Remediation actions taken"
    )
    
    pending_actions: Mapped[int] = mapped_column(
        String(5),
        nullable=False,
        default="0",
        comment="Number of pending remediation actions"
    )
    
    completed_actions: Mapped[int] = mapped_column(
        String(5),
        nullable=False,
        default="0",
        comment="Number of completed remediation actions"
    )
    
    # Assessment
    assessor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of assessor"
    )
    
    assessment_date: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Date of assessment"
    )
    
    assessment_notes: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Assessment notes"
    )
    
    # Evidence
    evidence_files: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Evidence file references"
    )
    
    # Relationships
    governance_rule = relationship(
        "GovernanceRule",
        back_populates="compliance_reports",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("governance_rule_id", "report_period_start", "report_period_end", name="uq_compliance_report_period"),
        Index("idx_compliance_status", "compliance_status"),
        Index("idx_compliance_score", "compliance_score"),
        Index("idx_compliance_assessment", "assessment_date"),
        {"comment": "Compliance reports for governance rules"}
    )
    
    def __repr__(self) -> str:
        """String representation of the compliance report."""
        return f"<ComplianceReport(status='{self.compliance_status}', score={self.compliance_score})>"
    
    @property
    def is_compliant(self) -> bool:
        """Check if rule is compliant."""
        return self.compliance_status == ComplianceStatus.COMPLIANT
    
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        total = int(self.total_checks)
        if total == 0:
            return 0.0
        return int(self.passed_checks) / total
    
    @property
    def has_violations(self) -> bool:
        """Check if there are violations."""
        return len(self.violations) > 0
    
    def add_violation(
        self,
        severity: str,
        description: str,
        resource_id: str | None = None,
        evidence: Dict[str, Any] | None = None
    ) -> None:
        """
        Add a compliance violation.
        
        Args:
            severity: Violation severity
            description: Violation description
            resource_id: Related resource ID
            evidence: Evidence data
        """
        violation = {
            "id": str(uuid.uuid4()),
            "severity": severity,
            "description": description,
            "resource_id": resource_id,
            "evidence": evidence or {},
            "detected_at": datetime.utcnow().isoformat(),
            "status": "open"
        }
        
        self.violations.append(violation)
        self.failed_checks = str(int(self.failed_checks) + 1)
        self.total_checks = str(int(self.total_checks) + 1)
        
        # Update compliance status
        if self.compliance_status == ComplianceStatus.COMPLIANT:
            self.compliance_status = ComplianceStatus.NON_COMPLIANT
    
    def add_remediation_action(
        self,
        action_type: str,
        description: str,
        assignee_id: uuid.UUID | None = None,
        due_date: datetime | None = None
    ) -> None:
        """
        Add a remediation action.
        
        Args:
            action_type: Type of action
            description: Action description
            assignee_id: ID of assignee
            due_date: Due date for action
        """
        action = {
            "id": str(uuid.uuid4()),
            "type": action_type,
            "description": description,
            "assignee_id": str(assignee_id) if assignee_id else None,
            "due_date": due_date.isoformat() if due_date else None,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.remediation_actions.append(action)
        self.pending_actions = str(int(self.pending_actions) + 1)
    
    def calculate_compliance_score(self) -> None:
        """Calculate overall compliance score."""
        total = int(self.total_checks)
        if total == 0:
            self.compliance_score = None
            return
        
        passed = int(self.passed_checks)
        warnings = int(self.warning_checks)
        
        # Weighted score: passed = 1.0, warning = 0.5, failed = 0.0
        score = (passed * 1.0 + warnings * 0.5) / total
        self.compliance_score = str(score)
        
        # Update compliance status based on score
        if score >= 0.95:
            self.compliance_status = ComplianceStatus.COMPLIANT
        elif score >= 0.80:
            self.compliance_status = ComplianceStatus.PENDING
        else:
            self.compliance_status = ComplianceStatus.NON_COMPLIANT
