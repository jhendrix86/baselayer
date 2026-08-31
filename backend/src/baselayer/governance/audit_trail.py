"""
BaseLayer Audit Trail

Audit trail management and logging system
for the Governance/Doctrine subsystem.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import db_session_context
from ..models.governance import AuditLog
from ..models.user import User
from .exceptions import (
    AuditError,
    ValidationError
)

logger = get_logger(__name__)


class AuditTrail:
    """
    Audit trail management and logging system.
    
    Comprehensive audit logging with search, filtering,
    and retention management for compliance requirements.
    """
    
    def __init__(self):
        self.audit_active: bool = False
        self.audit_queue: asyncio.Queue = asyncio.Queue()
        self.batch_size: int = 100
        self.batch_timeout: int = 30  # seconds
        self.retention_days: int = 2555  # 7 years for compliance
        
        # Event types and categories
        self.event_categories = {
            "access": {
                "description": "Access control events",
                "events": ["login", "logout", "access_granted", "access_denied", "permission_change"],
                "retention_days": 2555
            },
            "data": {
                "description": "Data operations",
                "events": ["create", "read", "update", "delete", "export", "import"],
                "retention_days": 2555
            },
            "system": {
                "description": "System operations",
                "events": ["start", "stop", "restart", "configuration_change", "maintenance"],
                "retention_days": 1825  # 5 years
            },
            "security": {
                "description": "Security events",
                "events": ["violation", "breach", "attack", "intrusion", "malware"],
                "retention_days": 3650  # 10 years
            },
            "compliance": {
                "description": "Compliance events",
                "events": ["policy_violation", "audit_failure", "remediation", "report_generated"],
                "retention_days": 2555
            },
            "governance": {
                "description": "Governance events",
                "events": ["policy_created", "policy_updated", "policy_deleted", "rule_enforced"],
                "retention_days": 2555
            }
        }
        
        # Audit metrics
        self.audit_metrics = {
            "total_events": 0,
            "events_today": 0,
            "events_this_week": 0,
            "events_this_month": 0,
            "batch_size": 0,
            "average_processing_time": 0.0
        }
    
    async def start(self) -> None:
        """Start the audit trail system."""
        if self.audit_active:
            return
        
        self.audit_active = True
        asyncio.create_task(self._audit_processing_loop())
        
        logger.info("Audit trail system started")
    
    async def stop(self) -> None:
        """Stop the audit trail system."""
        self.audit_active = False
        logger.info("Audit trail system stopped")
    
    async def log_event(
        self,
        event_type: str,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> AuditLog:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            resource_id: ID of affected resource
            resource_type: Type of affected resource
            details: Event details
            user_id: User who performed the action
            ip_address: IP address of the request
            user_agent: User agent string
            severity: Event severity
            category: Event category
            tags: Event tags
            
        Returns:
            AuditLog: Created audit log entry
        """
        try:
            # Validate event
            await self._validate_event(event_type, category, severity)
            
            # Determine category if not provided
            if not category:
                category = self._determine_event_category(event_type)

            # Create audit log entry. AuditLog has no severity/tags/details
            # columns - fold them into metadata_ (JSONB) alongside the real
            # columns (event_id/action/timestamp are required, event_category
            # is the real name for "category").
            audit_log = AuditLog(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                event_category=category,
                action=event_type,
                resource_id=resource_id,
                resource_type=resource_type,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow(),
                metadata_={
                    **(details or {}),
                    "severity": severity,
                    "tags": tags or [],
                }
            )
            
            # Add to processing queue
            await self.audit_queue.put(audit_log)
            
            # Update metrics
            self.audit_metrics["total_events"] += 1
            self._update_periodic_metrics()
            
            logger.debug(
                "Audit event logged",
                event_type=event_type,
                resource_id=resource_id,
                user_id=str(user_id) if user_id else None
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(
                "Failed to log audit event",
                event_type=event_type,
                error=str(e)
            )
            raise AuditError(f"Failed to log audit event: {str(e)}") from e
    
    async def log_batch_events(
        self,
        events: List[Dict[str, Any]]
    ) -> List[AuditLog]:
        """
        Log multiple audit events in batch.
        
        Args:
            events: List of event data
            
        Returns:
            List[AuditLog]: Created audit log entries
        """
        audit_logs = []
        
        for event_data in events:
            try:
                audit_log = await self.log_event(**event_data)
                audit_logs.append(audit_log)
            except Exception as e:
                logger.error(
                    "Failed to log batch event",
                    event_data=event_data,
                    error=str(e)
                )
        
        return audit_logs
    
    async def search_audit_trail(
        self,
        query: Optional[str] = None,
        event_type: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Search the audit trail.
        
        Args:
            query: Search query string
            event_type: Filter by event type
            category: Filter by category
            user_id: Filter by user ID
            resource_id: Filter by resource ID
            resource_type: Filter by resource type
            severity: Filter by severity
            tags: Filter by tags
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List[AuditLog]: Audit log entries
        """
        try:
            async with db_session_context() as session:
                query_builder = select(AuditLog).where(AuditLog.deleted_at.is_(None))
                
                # Apply filters
                if event_type:
                    query_builder = query_builder.where(AuditLog.event_type == event_type)
                
                if category:
                    query_builder = query_builder.where(AuditLog.category == category)
                
                if user_id:
                    query_builder = query_builder.where(AuditLog.user_id == user_id)
                
                if resource_id:
                    query_builder = query_builder.where(AuditLog.resource_id == resource_id)
                
                if resource_type:
                    query_builder = query_builder.where(AuditLog.resource_type == resource_type)
                
                if severity:
                    query_builder = query_builder.where(AuditLog.severity == severity)
                
                if tags:
                    for tag in tags:
                        query_builder = query_builder.where(AuditLog.tags.contains([tag]))
                
                if start_date:
                    query_builder = query_builder.where(AuditLog.created_at >= start_date)
                
                if end_date:
                    query_builder = query_builder.where(AuditLog.created_at <= end_date)
                
                # Text search if query provided
                if query:
                    query_builder = query_builder.where(
                        AuditLog.details.ilike(f"%{query}%")
                    )
                
                # Order and paginate
                query_builder = query_builder.order_by(AuditLog.created_at.desc())
                query_builder = query_builder.limit(limit).offset(offset)
                
                result = await session.execute(query_builder)
                audit_logs = result.scalars().all()
                
                return list(audit_logs)
                
        except Exception as e:
            raise AuditError(f"Failed to search audit trail: {str(e)}") from e
    
    async def get_audit_statistics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit statistics for a period.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Audit statistics
        """
        try:
            # Set default period
            if not period_start:
                period_start = datetime.utcnow() - timedelta(days=30)
            if not period_end:
                period_end = datetime.utcnow()
            
            async with db_session_context() as session:
                # Total events
                result = await session.execute(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.created_at >= period_start,
                        AuditLog.created_at <= period_end,
                        AuditLog.deleted_at.is_(None)
                    )
                )
                total_events = result.scalar() or 0
                
                # Events by category
                result = await session.execute(
                    select(
                        AuditLog.category,
                        func.count(AuditLog.id)
                    ).where(
                        AuditLog.created_at >= period_start,
                        AuditLog.created_at <= period_end,
                        AuditLog.deleted_at.is_(None)
                    ).group_by(AuditLog.category)
                )
                category_counts = dict(result.all())
                
                # Events by severity
                result = await session.execute(
                    select(
                        AuditLog.severity,
                        func.count(AuditLog.id)
                    ).where(
                        AuditLog.created_at >= period_start,
                        AuditLog.created_at <= period_end,
                        AuditLog.deleted_at.is_(None)
                    ).group_by(AuditLog.severity)
                )
                severity_counts = dict(result.all())
                
                # Events by user
                result = await session.execute(
                    select(
                        AuditLog.user_id,
                        func.count(AuditLog.id)
                    ).where(
                        AuditLog.created_at >= period_start,
                        AuditLog.created_at <= period_end,
                        AuditLog.deleted_at.is_(None),
                        AuditLog.user_id.is_not(None)
                    ).group_by(AuditLog.user_id)
                    .order_by(func.count(AuditLog.id).desc())
                    .limit(10)
                )
                user_counts = dict(result.all())
                
                # Daily event counts
                result = await session.execute(
                    select(
                        func.date(AuditLog.created_at),
                        func.count(AuditLog.id)
                    ).where(
                        AuditLog.created_at >= period_start,
                        AuditLog.created_at <= period_end,
                        AuditLog.deleted_at.is_(None)
                    ).group_by(func.date(AuditLog.created_at))
                    .order_by(func.date(AuditLog.created_at))
                )
                daily_counts = dict(result.all())
                
                statistics = {
                    "period": {
                        "start": period_start.isoformat(),
                        "end": period_end.isoformat()
                    },
                    "total_events": total_events,
                    "by_category": category_counts,
                    "by_severity": severity_counts,
                    "top_users": {str(k): v for k, v in user_counts.items()},
                    "daily_counts": {str(k): v for k, v in daily_counts.items()},
                    "audit_metrics": self.audit_metrics
                }
                
                return statistics
                
        except Exception as e:
            raise AuditError(f"Failed to get audit statistics: {str(e)}") from e
    
    async def export_audit_trail(
        self,
        format_type: str = "json",
        filters: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> bytes:
        """
        Export audit trail data.
        
        Args:
            format_type: Export format (json, csv, xml)
            filters: Export filters
            start_date: Start date for export
            end_date: End date for export
            
        Returns:
            bytes: Exported data
        """
        try:
            # Get audit logs
            audit_logs = await self.search_audit_trail(
                start_date=start_date,
                end_date=end_date,
                limit=10000,  # Large limit for export
                **(filters or {})
            )
            
            # Convert to export format
            if format_type == "json":
                export_data = self._export_to_json(audit_logs)
            elif format_type == "csv":
                export_data = self._export_to_csv(audit_logs)
            elif format_type == "xml":
                export_data = self._export_to_xml(audit_logs)
            else:
                raise AuditError(f"Unsupported export format: {format_type}")
            
            return export_data
            
        except Exception as e:
            raise AuditError(f"Failed to export audit trail: {str(e)}") from e
    
    async def cleanup_old_audit_logs(self, max_age_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Clean up old audit logs based on retention policy.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Dict[str, Any]: Cleanup results
        """
        try:
            max_age_days = max_age_days or self.retention_days
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            async with db_session_context() as session:
                result = await session.execute(
                    select(AuditLog).where(
                        AuditLog.created_at < cutoff_date,
                        AuditLog.deleted_at.is_(None)
                    )
                )
                old_logs = result.scalars().all()
                
                cleaned_count = 0
                for log in old_logs:
                    log.soft_delete()
                    session.add(log)
                    cleaned_count += 1
                
                await session.commit()
                
                logger.info(
                    "Old audit logs cleaned up",
                    count=cleaned_count,
                    max_age_days=max_age_days
                )
                
                return {
                    "cleaned_count": cleaned_count,
                    "max_age_days": max_age_days,
                    "cutoff_date": cutoff_date.isoformat()
                }
                
        except Exception as e:
            raise AuditError(f"Failed to cleanup audit logs: {str(e)}") from e
    
    async def _audit_processing_loop(self) -> None:
        """Main audit processing loop."""
        while self.audit_active:
            try:
                # Process audit queue in batches
                batch = []
                
                # Collect batch
                while len(batch) < self.batch_size:
                    try:
                        audit_log = await asyncio.wait_for(
                            self.audit_queue.get(),
                            timeout=self.batch_timeout
                        )
                        batch.append(audit_log)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    await self._process_audit_batch(batch)
                
            except Exception as e:
                logger.error(
                    "Audit processing loop error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def _process_audit_batch(self, batch: List[AuditLog]) -> None:
        """Process a batch of audit logs."""
        try:
            start_time = datetime.utcnow()
            
            async with db_session_context() as session:
                for audit_log in batch:
                    session.add(audit_log)
                
                await session.commit()
            
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.audit_metrics["batch_size"] = len(batch)
            
            # Update average processing time
            if self.audit_metrics["average_processing_time"] == 0:
                self.audit_metrics["average_processing_time"] = processing_time
            else:
                current_avg = self.audit_metrics["average_processing_time"]
                self.audit_metrics["average_processing_time"] = (
                    (current_avg + processing_time) / 2
                )
            
            logger.debug(
                "Audit batch processed",
                batch_size=len(batch),
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(
                "Failed to process audit batch",
                batch_size=len(batch),
                error=str(e)
            )
    
    async def _validate_event(
        self,
        event_type: str,
        category: Optional[str],
        severity: str
    ) -> None:
        """Validate audit event data."""
        errors = []
        
        # Validate event type
        if not event_type or not isinstance(event_type, str):
            errors.append("Event type must be a non-empty string")
        
        # Validate category
        if category and category not in self.event_categories:
            errors.append(f"Unknown category: {category}")
        
        # Validate severity
        valid_severities = ["debug", "info", "warning", "error", "critical"]
        if severity not in valid_severities:
            errors.append(f"Invalid severity: {severity}")
        
        if errors:
            raise ValidationError(
                f"Audit event validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    def _determine_event_category(self, event_type: str) -> str:
        """Determine event category from event type."""
        for category, config in self.event_categories.items():
            if event_type in config["events"]:
                return category
        
        return "system"  # Default category
    
    def _update_periodic_metrics(self) -> None:
        """Update periodic metrics (today, week, month)."""
        now = datetime.utcnow()
        
        # Today
        if not hasattr(self, '_last_today_update') or now.date() > self._last_today_update:
            self.audit_metrics["events_today"] = 0
            self._last_today_update = now.date()
        
        self.audit_metrics["events_today"] += 1
        
        # Week
        week_start = now - timedelta(days=now.weekday())
        if not hasattr(self, '_last_week_update') or now < week_start:
            self.audit_metrics["events_this_week"] = 0
            self._last_week_update = week_start
        
        self.audit_metrics["events_this_week"] += 1
        
        # Month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not hasattr(self, '_last_month_update') or now < month_start:
            self.audit_metrics["events_this_month"] = 0
            self._last_month_update = month_start
        
        self.audit_metrics["events_this_month"] += 1
    
    def _export_to_json(self, audit_logs: List[AuditLog]) -> bytes:
        """Export audit logs to JSON format."""
        import json
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "total_logs": len(audit_logs),
            "logs": [log.to_dict() for log in audit_logs]
        }
        
        return json.dumps(export_data, indent=2, default=str).encode('utf-8')
    
    def _export_to_csv(self, audit_logs: List[AuditLog]) -> bytes:
        """Export audit logs to CSV format."""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "id", "event_type", "category", "severity", "resource_id",
            "resource_type", "user_id", "ip_address", "created_at",
            "details"
        ])
        
        # Write data
        for log in audit_logs:
            writer.writerow([
                str(log.id),
                log.event_type,
                log.category,
                log.severity,
                log.resource_id,
                log.resource_type,
                str(log.user_id) if log.user_id else "",
                log.ip_address,
                log.created_at.isoformat(),
                str(log.details)
            ])
        
        return output.getvalue().encode('utf-8')
    
    def _export_to_xml(self, audit_logs: List[AuditLog]) -> bytes:
        """Export audit logs to XML format."""
        import xml.etree.ElementTree as ET
        
        root = ET.Element("audit_export")
        root.set("timestamp", datetime.utcnow().isoformat())
        root.set("total_logs", str(len(audit_logs)))
        
        logs_element = ET.SubElement(root, "logs")
        
        for log in audit_logs:
            log_element = ET.SubElement(logs_element, "log")
            log_element.set("id", str(log.id))
            log_element.set("event_type", log.event_type)
            log_element.set("category", log.category)
            log_element.set("severity", log.severity)
            log_element.set("resource_id", log.resource_id or "")
            log_element.set("resource_type", log.resource_type or "")
            log_element.set("user_id", str(log.user_id) if log.user_id else "")
            log_element.set("ip_address", log.ip_address or "")
            log_element.set("created_at", log.created_at.isoformat())
            log_element.set("details", str(log.details))
        
        return ET.tostring(root, encoding='unicode').encode('utf-8')
    
    def get_audit_trail_stats(self) -> Dict[str, Any]:
        """Get audit trail statistics."""
        return {
            "audit_active": self.audit_active,
            "queue_size": self.audit_queue.qsize(),
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout,
            "retention_days": self.retention_days,
            "event_categories": list(self.event_categories.keys()),
            "audit_metrics": self.audit_metrics
        }
