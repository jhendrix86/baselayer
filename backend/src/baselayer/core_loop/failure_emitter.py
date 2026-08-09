"""
Failure event emitter for WorkflowEngine

Emits failure.detected and failure.recovered events to autonomy-events
for DLQ handling and global state management.
"""

import uuid
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

try:
    from autonomy_events import EventPublisher, EventEnvelope
    AUTONOMY_EVENTS_AVAILABLE = True
except ImportError:
    AUTONOMY_EVENTS_AVAILABLE = False
    EventPublisher = None  # type: ignore

import structlog

logger = structlog.get_logger()


class FailureSeverity(str, Enum):
    """Failure severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureType(str, Enum):
    """Failure types"""
    PROCESSING = "processing"
    NETWORK = "network"
    VALIDATION = "validation"
    SYSTEM = "system"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"
    GOVERNANCE = "governance"


class FailureEventEmitter:
    """Emits workflow failures to autonomy-events for DLQ handling"""

    def __init__(self, rabbitmq_url: Optional[str] = None):
        self.rabbitmq_url = rabbitmq_url
        self.publisher: Optional[EventPublisher] = None
        self.connected = False

    async def connect(self):
        """Connect to event publisher"""
        if not AUTONOMY_EVENTS_AVAILABLE:
            logger.warning("autonomy_events not available, failure events disabled")
            return

        if not self.rabbitmq_url:
            logger.warning("rabbitmq_url not set, failure events disabled")
            return

        try:
            self.publisher = EventPublisher(self.rabbitmq_url)
            await self.publisher.connect()
            self.connected = True
            logger.info("failure_event_emitter_connected")
        except Exception as e:
            logger.error("failure_event_emitter_connection_failed", error=str(e))
            self.connected = False

    async def disconnect(self):
        """Disconnect from event publisher"""
        if self.publisher and self.connected:
            await self.publisher.disconnect()
            self.connected = False
            logger.info("failure_event_emitter_disconnected")

    async def emit_failure_detected(
        self,
        failure_id: str,
        failure_type: FailureType,
        severity: FailureSeverity,
        component: str,
        error_message: str,
        error_code: Optional[str] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        affected_operations: Optional[List[str]] = None,
        is_retriable: bool = True,
        requires_manual_intervention: bool = False,
    ) -> bool:
        """
        Emit a failure.detected event

        Args:
            failure_id: Unique failure identifier
            failure_type: Type of failure
            severity: Severity level
            component: Component where failure occurred
            error_message: Error message
            error_code: Optional error code
            stack_trace: Optional stack trace
            context: Optional failure context
            affected_operations: List of affected operations
            is_retriable: Whether failure is retriable
            requires_manual_intervention: Whether manual intervention is needed

        Returns:
            bool: True if event was published successfully
        """
        if not self.connected or not self.publisher:
            logger.warning(
                "failure_event_publisher_not_connected",
                failure_id=failure_id,
                failure_type=failure_type.value,
            )
            return False

        try:
            payload = {
                "failure_id": failure_id,
                "failure_type": failure_type.value,
                "severity": severity.value,
                "component": component,
                "error_message": error_message,
                "error_code": error_code,
                "detected_at": datetime.utcnow().isoformat(),
                "detected_by": "workflow-engine",
                "stack_trace": stack_trace,
                "context": context or {},
                "affected_operations": affected_operations or [],
                "is_retriable": is_retriable,
                "requires_manual_intervention": requires_manual_intervention,
            }

            result = await self.publisher.publish(
                event_type="failure.detected",
                payload=payload,
                routing_key="failure.detected",
            )

            logger.info(
                "failure_detected_event_published",
                failure_id=failure_id,
                event_id=result.event_id if result else None,
            )
            return result.success if result else False

        except Exception as e:
            logger.error(
                "failure_detected_event_emission_failed",
                failure_id=failure_id,
                error=str(e),
            )
            return False

    async def emit_failure_recovered(
        self,
        failure_id: str,
        recovery_type: str,
        recovery_actions: Optional[List[str]] = None,
        downtime_seconds: int = 0,
        data_loss: bool = False,
        root_cause: Optional[str] = None,
        preventive_measures: Optional[List[str]] = None,
    ) -> bool:
        """
        Emit a failure.recovered event

        Args:
            failure_id: Original failure identifier
            recovery_type: Type of recovery (retry, fallback, manual, fix)
            recovery_actions: List of actions taken
            downtime_seconds: Total downtime in seconds
            data_loss: Whether there was data loss
            root_cause: Root cause if identified
            preventive_measures: Preventive measures implemented

        Returns:
            bool: True if event was published successfully
        """
        if not self.connected or not self.publisher:
            logger.warning(
                "failure_event_publisher_not_connected",
                failure_id=failure_id,
            )
            return False

        try:
            payload = {
                "failure_id": failure_id,
                "recovery_type": recovery_type,
                "recovered_at": datetime.utcnow().isoformat(),
                "recovered_by": "workflow-engine",
                "recovery_actions": recovery_actions or [],
                "downtime_seconds": downtime_seconds,
                "data_loss": data_loss,
                "root_cause": root_cause,
                "preventive_measures": preventive_measures or [],
                "requires_monitoring": True,
            }

            result = await self.publisher.publish(
                event_type="failure.recovered",
                payload=payload,
                routing_key="failure.recovered",
            )

            logger.info(
                "failure_recovered_event_published",
                failure_id=failure_id,
                event_id=result.event_id if result else None,
            )
            return result.success if result else False

        except Exception as e:
            logger.error(
                "failure_recovered_event_emission_failed",
                failure_id=failure_id,
                error=str(e),
            )
            return False

    @staticmethod
    def classify_exception(exc: Exception) -> tuple[FailureType, FailureSeverity]:
        """
        Classify an exception to determine failure type and severity

        Args:
            exc: The exception to classify

        Returns:
            Tuple of (FailureType, FailureSeverity)
        """
        exc_name = exc.__class__.__name__
        exc_msg = str(exc).lower()

        # Timeout
        if "timeout" in exc_msg or "timeout" in exc_name.lower():
            return FailureType.TIMEOUT, FailureSeverity.HIGH

        # Network
        if any(
            keyword in exc_msg
            for keyword in ["connection", "network", "socket", "unreachable"]
        ):
            return FailureType.NETWORK, FailureSeverity.MEDIUM

        # Validation
        if "validation" in exc_msg or "invalid" in exc_msg:
            return FailureType.VALIDATION, FailureSeverity.LOW

        # Dependency
        if any(
            keyword in exc_msg
            for keyword in ["dependency", "import", "module", "not found"]
        ):
            return FailureType.DEPENDENCY, FailureSeverity.CRITICAL

        # Default: processing error with high severity
        return FailureType.PROCESSING, FailureSeverity.HIGH
