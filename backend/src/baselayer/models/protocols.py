"""
BaseLayer Protocol Libraries Models

Protocol templates, variables, and validation rules
for the Protocol Libraries subsystem.
"""

from datetime import datetime

import uuid
from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, String, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import BaseModel, UUIDType


class ProtocolCategory(str, Enum):
    """Protocol categories."""
    WORKFLOW = "workflow"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    MONITORING = "monitoring"


class ProtocolStatus(str, Enum):
    """Protocol status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class VariableType(str, Enum):
    """Variable types."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE = "file"


class ValidationType(str, Enum):
    """Validation rule types."""
    REQUIRED = "required"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    PATTERN = "pattern"
    CUSTOM = "custom"


class Protocol(BaseModel):
    """
    Protocol model for Protocol Libraries subsystem.
    
    Defines reusable workflow templates with variables, validation,
    and documentation for operational consistency.
    """
    
    __tablename__ = "protocols"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Protocol name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Protocol description"
    )
    
    # Categorization
    category: Mapped[ProtocolCategory] = mapped_column(
        ENUM(ProtocolCategory, name="protocol_category"),
        nullable=False,
        index=True,
        comment="Protocol category"
    )
    
    status: Mapped[ProtocolStatus] = mapped_column(
        ENUM(ProtocolStatus, name="protocol_status"),
        nullable=False,
        default=ProtocolStatus.DRAFT,
        index=True,
        comment="Current protocol status"
    )
    
    # Version control
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Protocol version"
    )
    
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("protocols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent protocol for versioning"
    )
    
    # Template definition
    template_definition: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Complete protocol template definition"
    )
    
    # Variables and configuration
    variables: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Protocol variables with types and validation"
    )
    
    steps: Mapped[list[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Protocol steps with configuration"
    )
    
    # Documentation
    documentation: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed protocol documentation"
    )
    
    usage_instructions: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Instructions for using the protocol"
    )
    
    # Examples
    examples: Mapped[list[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Usage examples with input and output"
    )
    
    # Requirements and dependencies
    requirements: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="System requirements for the protocol"
    )
    
    dependencies: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Protocol dependencies"
    )
    
    # Governance and compliance
    governance_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether governance approval is required"
    )
    
    compliance_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="standard",
        comment="Compliance level requirement"
    )
    
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of user who approved the protocol"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when protocol was approved"
    )
    
    # Usage metrics
    usage_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the protocol has been used"
    )
    
    success_rate: Mapped[float] = mapped_column(
        String(10),
        nullable=True,
        comment="Success rate of protocol executions"
    )
    
    last_used_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Timestamp when protocol was last used"
    )
    
    # Metadata
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tags for categorization and search"
    )
    
    author: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Protocol author"
    )
    
    license: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        default="MIT",
        comment="Protocol license"
    )
    
    # Relationships
    created_by_user = relationship(
        "User",
        back_populates="protocols",
        foreign_keys="Protocol.created_by",
        lazy="select"
    )
    
    parent = relationship(
        "Protocol",
        remote_side="Protocol.id",
        back_populates="children",
        lazy="select"
    )
    
    children = relationship(
        "Protocol",
        back_populates="parent",
        lazy="select"
    )
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("name", "deleted_at", name="uq_protocol_name_deleted"),
        Index("idx_protocol_category_status", "category", "status"),
        Index("idx_protocol_version", "version"),
        Index("idx_protocol_tags", "tags", postgresql_using="gin"),
        Index("idx_protocol_usage", "usage_count"),
        {"comment": "Protocol templates for operational consistency"}
    )
    
    def __repr__(self) -> str:
        """String representation of the protocol."""
        return f"<Protocol(name='{self.name}', category='{self.category}', version='{self.version}')>"
    
    @property
    def is_published(self) -> bool:
        """Check if protocol is published."""
        return self.status == ProtocolStatus.PUBLISHED
    
    @property
    def has_dependencies(self) -> bool:
        """Check if protocol has dependencies."""
        return bool(self.dependencies)
    
    def publish(self, approved_by: uuid.UUID | None = None) -> None:
        """
        Publish the protocol.
        
        Args:
            approved_by: ID of user approving the publication
        """
        self.status = ProtocolStatus.PUBLISHED
        self.approved_by = approved_by
        self.approved_at = datetime.utcnow()
        self.increment_version()
    
    def deprecate(self) -> None:
        """Deprecate the protocol."""
        self.status = ProtocolStatus.DEPRECATED
        self.increment_version()
    
    def archive(self) -> None:
        """Archive the protocol."""
        self.status = ProtocolStatus.ARCHIVED
        self.increment_version()
    
    def add_variable(
        self,
        name: str,
        var_type: VariableType,
        required: bool = False,
        default_value: Any = None,
        description: str = "",
        validation_rules: list[Dict[str, Any]] | None = None
    ) -> None:
        """
        Add a variable to the protocol.
        
        Args:
            name: Variable name
            var_type: Variable type
            required: Whether variable is required
            default_value: Default value
            description: Variable description
            validation_rules: Validation rules
        """
        if not self.variables:
            self.variables = {}
        
        self.variables[name] = {
            "type": var_type.value,
            "required": required,
            "default_value": default_value,
            "description": description,
            "validation_rules": validation_rules or []
        }
        
        self.increment_version()
    
    def add_step(
        self,
        step_id: str,
        name: str,
        step_type: str,
        config: Dict[str, Any],
        description: str = "",
        dependencies: list[str] | None = None
    ) -> None:
        """
        Add a step to the protocol.
        
        Args:
            step_id: Unique step identifier
            name: Step name
            step_type: Type of step
            config: Step configuration
            description: Step description
            dependencies: Step dependencies
        """
        step = {
            "id": step_id,
            "name": name,
            "type": step_type,
            "config": config,
            "description": description,
            "dependencies": dependencies or []
        }
        
        if not self.steps:
            self.steps = []
        
        self.steps.append(step)
        self.increment_version()
    
    def add_example(
        self,
        name: str,
        description: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any]
    ) -> None:
        """
        Add an example to the protocol.
        
        Args:
            name: Example name
            description: Example description
            input_data: Input data for the example
            expected_output: Expected output data
        """
        example = {
            "name": name,
            "description": description,
            "input": input_data,
            "expected_output": expected_output
        }
        
        if not self.examples:
            self.examples = []
        
        self.examples.append(example)
        self.increment_version()
    
    def record_usage(self, success: bool = True) -> None:
        """
        Record protocol usage.
        
        Args:
            success: Whether the usage was successful
        """
        self.usage_count = str(int(self.usage_count) + 1)
        self.last_used_at = datetime.utcnow()
        
        # Update success rate
        if self.success_rate is not None:
            total_usage = int(self.usage_count)
            if total_usage > 1:
                current_successes = float(self.success_rate) * (total_usage - 1)
                new_successes = current_successes + (1 if success else 0)
                self.success_rate = str(new_successes / total_usage)
            else:
                self.success_rate = str(1.0 if success else 0.0)
        else:
            self.success_rate = str(1.0 if success else 0.0)
    
    def get_variable(self, name: str) -> Dict[str, Any] | None:
        """
        Get a variable definition.
        
        Args:
            name: Variable name
            
        Returns:
            Dict[str, Any] | None: Variable definition
        """
        if self.variables:
            return self.variables.get(name)
        return None
    
    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate input data against protocol variables.
        
        Args:
            input_data: Input data to validate
            
        Returns:
            tuple[bool, list[str]]: (is_valid, error_messages)
        """
        errors = []
        
        if not self.variables:
            return True, errors
        
        # Check required variables
        for var_name, var_def in self.variables.items():
            if var_def.get("required", False) and var_name not in input_data:
                errors.append(f"Required variable '{var_name}' is missing")
            
            if var_name in input_data:
                # Type validation
                var_type = var_def.get("type")
                value = input_data[var_name]
                
                if var_type == VariableType.STRING.value and not isinstance(value, str):
                    errors.append(f"Variable '{var_name}' must be a string")
                elif var_type == VariableType.NUMBER.value and not isinstance(value, (int, float)):
                    errors.append(f"Variable '{var_name}' must be a number")
                elif var_type == VariableType.BOOLEAN.value and not isinstance(value, bool):
                    errors.append(f"Variable '{var_name}' must be a boolean")
                elif var_type == VariableType.ARRAY.value and not isinstance(value, list):
                    errors.append(f"Variable '{var_name}' must be an array")
                elif var_type == VariableType.OBJECT.value and not isinstance(value, dict):
                    errors.append(f"Variable '{var_name}' must be an object")
                
                # Validation rules
                validation_rules = var_def.get("validation_rules", [])
                for rule in validation_rules:
                    rule_type = rule.get("type")
                    if rule_type == ValidationType.MIN_LENGTH.value and isinstance(value, str):
                        min_length = rule.get("params", {}).get("length")
                        if min_length and len(value) < min_length:
                            errors.append(f"Variable '{var_name}' must be at least {min_length} characters")
                    elif rule_type == ValidationType.MAX_LENGTH.value and isinstance(value, str):
                        max_length = rule.get("params", {}).get("length")
                        if max_length and len(value) > max_length:
                            errors.append(f"Variable '{var_name}' must be no more than {max_length} characters")
                    elif rule_type == ValidationType.MIN_VALUE.value and isinstance(value, (int, float)):
                        min_value = rule.get("params", {}).get("value")
                        if min_value is not None and value < min_value:
                            errors.append(f"Variable '{var_name}' must be at least {min_value}")
                    elif rule_type == ValidationType.MAX_VALUE.value and isinstance(value, (int, float)):
                        max_value = rule.get("params", {}).get("value")
                        if max_value is not None and value > max_value:
                            errors.append(f"Variable '{var_name}' must be no more than {max_value}")
                    elif rule_type == ValidationType.PATTERN.value and isinstance(value, str):
                        pattern = rule.get("params", {}).get("pattern")
                        if pattern:
                            import re
                            if not re.match(pattern, value):
                                errors.append(f"Variable '{var_name}' does not match required pattern")
        
        return len(errors) == 0, errors


class ProtocolTemplate(BaseModel):
    """
    Protocol template model.
    
    Stores reusable template components for protocols.
    """
    
    __tablename__ = "protocol_templates"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
        comment="Template name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Template description"
    )
    
    # Template content
    template_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template content with placeholders"
    )
    
    template_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Template type (step, workflow, notification, etc.)"
    )
    
    # Variables
    variables: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Template variables with types and defaults"
    )
    
    # Configuration
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Template configuration"
    )
    
    # Usage metrics
    usage_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the template has been used"
    )
    
    # Metadata
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tags for categorization"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the template is active"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_template_type", "template_type"),
        Index("idx_protocol_template_usage", "usage_count"),
        {"comment": "Reusable protocol templates"}
    )
    
    def __repr__(self) -> str:
        """String representation of the template."""
        return f"<ProtocolTemplate(name='{self.name}', type='{self.template_type}')>"
    
    def render(self, variables: Dict[str, Any]) -> str:
        """
        Render the template with provided variables.
        
        Args:
            variables: Variables to substitute in template
            
        Returns:
            str: Rendered template content
        """
        content = self.template_content
        
        # Simple variable substitution
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            content = content.replace(placeholder, str(var_value))
        
        return content
    
    def record_usage(self) -> None:
        """Record template usage."""
        self.usage_count = str(int(self.usage_count) + 1)


class ProtocolVariable(BaseModel):
    """
    Protocol variable model.
    
    Defines reusable variable definitions for protocols.
    """
    
    __tablename__ = "protocol_variables"
    
    # Basic information
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Variable name"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Variable description"
    )
    
    # Type and validation
    variable_type: Mapped[VariableType] = mapped_column(
        ENUM(VariableType, name="protocol_variable_type"),
        nullable=False,
        index=True,
        comment="Variable type"
    )
    
    default_value: Mapped[Any] = mapped_column(
        JSONB,
        nullable=True,
        comment="Default value for the variable"
    )
    
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the variable is required"
    )
    
    # Validation rules
    validation_rules: Mapped[list[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Validation rules for the variable"
    )
    
    # Usage metrics
    usage_count: Mapped[int] = mapped_column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of times the variable has been used"
    )
    
    # Metadata
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tags for categorization"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the variable is active"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index("idx_variable_type", "variable_type"),
        Index("idx_variable_usage", "usage_count"),
        {"comment": "Reusable protocol variable definitions"}
    )
    
    def __repr__(self) -> str:
        """String representation of the variable."""
        return f"<ProtocolVariable(name='{self.name}', type='{self.variable_type}')>"
    
    def validate_value(self, value: Any) -> tuple[bool, list[str]]:
        """
        Validate a value against the variable's rules.
        
        Args:
            value: Value to validate
            
        Returns:
            tuple[bool, list[str]]: (is_valid, error_messages)
        """
        errors = []
        
        # Type validation
        if self.variable_type == VariableType.STRING.value and not isinstance(value, str):
            errors.append(f"Value must be a string")
        elif self.variable_type == VariableType.NUMBER.value and not isinstance(value, (int, float)):
            errors.append(f"Value must be a number")
        elif self.variable_type == VariableType.BOOLEAN.value and not isinstance(value, bool):
            errors.append(f"Value must be a boolean")
        elif self.variable_type == VariableType.ARRAY.value and not isinstance(value, list):
            errors.append(f"Value must be an array")
        elif self.variable_type == VariableType.OBJECT.value and not isinstance(value, dict):
            errors.append(f"Value must be an object")
        
        # Validation rules
        for rule in self.validation_rules:
            rule_type = rule.get("type")
            if rule_type == ValidationType.MIN_LENGTH.value and isinstance(value, str):
                min_length = rule.get("params", {}).get("length")
                if min_length and len(value) < min_length:
                    errors.append(f"Value must be at least {min_length} characters")
            elif rule_type == ValidationType.MAX_LENGTH.value and isinstance(value, str):
                max_length = rule.get("params", {}).get("length")
                if max_length and len(value) > max_length:
                    errors.append(f"Value must be no more than {max_length} characters")
            elif rule_type == ValidationType.MIN_VALUE.value and isinstance(value, (int, float)):
                min_value = rule.get("params", {}).get("value")
                if min_value is not None and value < min_value:
                    errors.append(f"Value must be at least {min_value}")
            elif rule_type == ValidationType.MAX_VALUE.value and isinstance(value, (int, float)):
                max_value = rule.get("params", {}).get("value")
                if max_value is not None and value > max_value:
                    errors.append(f"Value must be no more than {max_value}")
            elif rule_type == ValidationType.PATTERN.value and isinstance(value, str):
                pattern = rule.get("params", {}).get("pattern")
                if pattern:
                    import re
                    if not re.match(pattern, value):
                        errors.append(f"Value does not match required pattern")
        
        return len(errors) == 0, errors
    
    def record_usage(self) -> None:
        """Record variable usage."""
        self.usage_count = str(int(self.usage_count) + 1)
