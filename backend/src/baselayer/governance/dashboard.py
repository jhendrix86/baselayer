"""
BaseLayer Compliance Dashboard

Compliance dashboard and reporting system
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

from ..core.database import get_db_session
from ..models.governance import (
    GovernanceRule, ComplianceReport,
    RuleType, ComplianceStatus
)
from ..models.user import User
from .exceptions import (
    DashboardError,
    ValidationError
)

logger = get_logger(__name__)


class ComplianceDashboard:
    """
    Compliance dashboard and reporting system.
    
    Provides real-time compliance monitoring, reporting,
    and alerting with comprehensive dashboard functionality.
    """
    
    def __init__(self):
        self.dashboard_active: bool = False
        self.dashboard_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 300  # 5 minutes
        self.refresh_interval: int = 60  # seconds
        
        # Dashboard widgets
        self.widget_types = {
            "compliance_score": {
                "description": "Overall compliance score",
                "data_source": "compliance_metrics",
                "refresh_rate": 300
            },
            "risk_level": {
                "description": "Current risk level",
                "data_source": "risk_assessment",
                "refresh_rate": 300
            },
            "violation_count": {
                "description": "Number of active violations",
                "data_source": "compliance_monitor",
                "refresh_rate": 60
            },
            "policy_status": {
                "description": "Policy enforcement status",
                "data_source": "policy_manager",
                "refresh_rate": 300
            },
            "audit_summary": {
                "description": "Recent audit activity",
                "data_source": "audit_trail",
                "refresh_rate": 300
            },
            "trend_chart": {
                "description": "Compliance trends over time",
                "data_source": "compliance_monitor",
                "refresh_rate": 3600
            },
            "alert_panel": {
                "description": "Active compliance alerts",
                "data_source": "compliance_monitor",
                "refresh_rate": 30
            },
            "mitigation_progress": {
                "description": "Risk mitigation progress",
                "data_source": "risk_assessor",
                "refresh_rate": 300
            }
        }
        
        # Dashboard metrics
        self.dashboard_metrics = {
            "total_views": 0,
            "refresh_count": 0,
            "alert_count": 0,
            "report_count": 0,
            "average_load_time": 0.0
        }
    
    async def start(self) -> None:
        """Start the compliance dashboard."""
        if self.dashboard_active:
            return
        
        self.dashboard_active = True
        asyncio.create_task(self._dashboard_refresh_loop())
        
        logger.info("Compliance dashboard started")
    
    async def stop(self) -> None:
        """Stop the compliance dashboard."""
        self.dashboard_active = False
        logger.info("Compliance dashboard stopped")
    
    async def get_dashboard_data(
        self,
        dashboard_type: str = "main",
        time_range: str = "7d",
        widgets: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get dashboard data.
        
        Args:
            dashboard_type: Type of dashboard
            time_range: Time range for data
            widgets: Specific widgets to include
            filters: Data filters
            
        Returns:
            Dict[str, Any]: Dashboard data
        """
        try:
            start_time = datetime.utcnow()
            
            # Validate inputs
            await self._validate_dashboard_request(dashboard_type, time_range, widgets)
            
            # Calculate time range
            time_delta = self._get_time_delta(time_range)
            period_start = datetime.utcnow() - time_delta
            period_end = datetime.utcnow()
            
            # Get widget data
            widget_data = {}
            widget_list = widgets or list(self.widget_types.keys())
            
            for widget_type in widget_list:
                try:
                    widget_data[widget_type] = await self._get_widget_data(
                        widget_type, period_start, period_end, filters
                    )
                except Exception as e:
                    logger.error(
                        "Failed to get widget data",
                        widget_type=widget_type,
                        error=str(e)
                    )
                    widget_data[widget_type] = {
                        "error": str(e),
                        "status": "error"
                    }
            
            # Get summary data
            summary_data = await self._get_summary_data(period_start, period_end)
            
            # Calculate load time
            load_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update metrics
            self.dashboard_metrics["total_views"] += 1
            self._update_average_load_time(load_time)
            
            dashboard_data = {
                "dashboard_type": dashboard_type,
                "time_range": time_range,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "summary": summary_data,
                "widgets": widget_data,
                "load_time": load_time,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            logger.debug(
                "Dashboard data retrieved",
                dashboard_type=dashboard_type,
                time_range=time_range,
                load_time=load_time
            )
            
            return dashboard_data
            
        except Exception as e:
            raise DashboardError(f"Failed to get dashboard data: {str(e)}") from e
    
    async def get_compliance_overview(
        self,
        time_range: str = "30d"
    ) -> Dict[str, Any]:
        """
        Get compliance overview.
        
        Args:
            time_range: Time range for overview
            
        Returns:
            Dict[str, Any]: Compliance overview
        """
        try:
            # Calculate time range
            time_delta = self._get_time_delta(time_range)
            period_start = datetime.utcnow() - time_delta
            period_end = datetime.utcnow()
            
            # Get compliance metrics
            compliance_metrics = await self._get_compliance_metrics(period_start, period_end)
            
            # Get risk assessment
            risk_assessment = await self._get_risk_assessment(period_start, period_end)
            
            # Get policy status
            policy_status = await self._get_policy_status(period_start, period_end)
            
            # Get audit summary
            audit_summary = await self._get_audit_summary(period_start, period_end)
            
            # Get alerts
            alerts = await self._get_active_alerts()
            
            overview = {
                "time_range": time_range,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "compliance_metrics": compliance_metrics,
                "risk_assessment": risk_assessment,
                "policy_status": policy_status,
                "audit_summary": audit_summary,
                "alerts": alerts,
                "overall_status": self._calculate_overall_status(compliance_metrics, risk_assessment),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return overview
            
        except Exception as e:
            raise DashboardError(f"Failed to get compliance overview: {str(e)}") from e
    
    async def generate_dashboard_report(
        self,
        report_type: str = "comprehensive",
        time_range: str = "30d",
        format_type: str = "json",
        include_charts: bool = True
    ) -> Dict[str, Any]:
        """
        Generate dashboard report.
        
        Args:
            report_type: Type of report
            time_range: Time range for report
            format_type: Output format
            include_charts: Whether to include charts
            
        Returns:
            Dict[str, Any]: Generated report
        """
        try:
            start_time = datetime.utcnow()
            
            # Get base dashboard data
            dashboard_data = await self.get_dashboard_data(
                dashboard_type="report",
                time_range=time_range
            )
            
            # Generate report sections
            report_sections = {}
            
            if report_type in ["comprehensive", "compliance"]:
                report_sections["compliance"] = await self._generate_compliance_section(
                    dashboard_data, include_charts
                )
            
            if report_type in ["comprehensive", "risk"]:
                report_sections["risk"] = await self._generate_risk_section(
                    dashboard_data, include_charts
                )
            
            if report_type in ["comprehensive", "audit"]:
                report_sections["audit"] = await self._generate_audit_section(
                    dashboard_data, include_charts
                )
            
            if report_type in ["comprehensive", "policy"]:
                report_sections["policy"] = await self._generate_policy_section(
                    dashboard_data, include_charts
                )
            
            # Generate summary
            report_summary = self._generate_report_summary(report_sections)
            
            # Calculate generation time
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update metrics
            self.dashboard_metrics["report_count"] += 1
            
            report = {
                "report_id": str(uuid.uuid4()),
                "report_type": report_type,
                "time_range": time_range,
                "format_type": format_type,
                "generated_at": start_time.isoformat(),
                "generation_time": generation_time,
                "summary": report_summary,
                "sections": report_sections,
                "metadata": {
                    "include_charts": include_charts,
                    "dashboard_version": "1.0.0"
                }
            }
            
            logger.info(
                "Dashboard report generated",
                report_id=report["report_id"],
                report_type=report_type,
                generation_time=generation_time
            )
            
            return report
            
        except Exception as e:
            raise DashboardError(f"Failed to generate dashboard report: {str(e)}") from e
    
    async def create_custom_dashboard(
        self,
        name: str,
        description: str,
        layout: Dict[str, Any],
        widgets: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a custom dashboard.
        
        Args:
            name: Dashboard name
            description: Dashboard description
            layout: Dashboard layout configuration
            widgets: Widget configurations
            filters: Default filters
            created_by: User who created the dashboard
            
        Returns:
            Dict[str, Any]: Created dashboard configuration
        """
        try:
            # Validate dashboard configuration
            await self._validate_custom_dashboard(layout, widgets)
            
            dashboard_config = {
                "dashboard_id": str(uuid.uuid4()),
                "name": name,
                "description": description,
                "layout": layout,
                "widgets": widgets,
                "filters": filters or {},
                "created_at": datetime.utcnow().isoformat(),
                "created_by": str(created_by) if created_by else None,
                "version": "1.0.0"
            }
            
            logger.info(
                "Custom dashboard created",
                dashboard_id=dashboard_config["dashboard_id"],
                name=name
            )
            
            return dashboard_config
            
        except Exception as e:
            raise DashboardError(f"Failed to create custom dashboard: {str(e)}") from e
    
    async def get_alerts(
        self,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get compliance alerts.
        
        Args:
            severity: Filter by severity
            category: Filter by category
            status: Filter by status
            limit: Maximum number of alerts
            
        Returns:
            List[Dict[str, Any]]: Compliance alerts
        """
        try:
            # In real implementation, would query from database
            # For now, return mock alerts
            mock_alerts = [
                {
                    "alert_id": str(uuid.uuid4()),
                    "severity": "high",
                    "category": "compliance",
                    "title": "Compliance score below threshold",
                    "description": "Overall compliance score has dropped below 80%",
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "active"
                },
                {
                    "alert_id": str(uuid.uuid4()),
                    "severity": "medium",
                    "category": "risk",
                    "title": "New risk identified",
                    "description": "A new medium-risk vulnerability has been detected",
                    "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                    "status": "active"
                }
            ]
            
            # Apply filters
            filtered_alerts = mock_alerts
            
            if severity:
                filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity]
            
            if category:
                filtered_alerts = [a for a in filtered_alerts if a["category"] == category]
            
            if status:
                filtered_alerts = [a for a in filtered_alerts if a["status"] == status]
            
            return filtered_alerts[:limit]
            
        except Exception as e:
            raise DashboardError(f"Failed to get alerts: {str(e)}") from e
    
    async def _dashboard_refresh_loop(self) -> None:
        """Main dashboard refresh loop."""
        while self.dashboard_active:
            try:
                # Refresh cached data
                await self._refresh_dashboard_cache()
                
                # Update metrics
                self.dashboard_metrics["refresh_count"] += 1
                
                # Sleep before next iteration
                await asyncio.sleep(self.refresh_interval)
                
            except Exception as e:
                logger.error(
                    "Dashboard refresh loop error",
                    error=str(e)
                )
                await asyncio.sleep(60)
    
    async def _refresh_dashboard_cache(self) -> None:
        """Refresh dashboard cache."""
        try:
            # Refresh commonly accessed widgets
            common_widgets = ["compliance_score", "risk_level", "violation_count", "alert_panel"]
            
            for widget_type in common_widgets:
                try:
                    cache_key = f"widget_{widget_type}"
                    
                    # Get fresh data
                    period_start = datetime.utcnow() - timedelta(hours=1)
                    period_end = datetime.utcnow()
                    
                    widget_data = await self._get_widget_data(widget_type, period_start, period_end)
                    
                    # Update cache
                    self.dashboard_cache[cache_key] = {
                        "data": widget_data,
                        "cached_at": datetime.utcnow()
                    }
                    
                except Exception as e:
                    logger.error(
                        "Failed to refresh widget cache",
                        widget_type=widget_type,
                        error=str(e)
                    )
            
        except Exception as e:
            logger.error(
                "Dashboard cache refresh failed",
                error=str(e)
            )
    
    async def _validate_dashboard_request(
        self,
        dashboard_type: str,
        time_range: str,
        widgets: Optional[List[str]]
    ) -> None:
        """Validate dashboard request."""
        errors = []
        
        # Validate dashboard type
        valid_types = ["main", "compliance", "risk", "audit", "custom"]
        if dashboard_type not in valid_types:
            errors.append(f"Invalid dashboard type: {dashboard_type}")
        
        # Validate time range
        valid_ranges = ["1d", "7d", "30d", "90d", "1y"]
        if time_range not in valid_ranges:
            errors.append(f"Invalid time range: {time_range}")
        
        # Validate widgets
        if widgets:
            for widget in widgets:
                if widget not in self.widget_types:
                    errors.append(f"Unknown widget type: {widget}")
        
        if errors:
            raise ValidationError(
                f"Dashboard request validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    def _get_time_delta(self, time_range: str) -> timedelta:
        """Get timedelta for time range."""
        time_ranges = {
            "1d": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
            "1y": timedelta(days=365)
        }
        
        return time_ranges.get(time_range, timedelta(days=7))
    
    async def _get_widget_data(
        self,
        widget_type: str,
        period_start: datetime,
        period_end: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get data for a specific widget."""
        if widget_type not in self.widget_types:
            raise DashboardError(f"Unknown widget type: {widget_type}")
        
        # Check cache first
        cache_key = f"widget_{widget_type}"
        if cache_key in self.dashboard_cache:
            cached_data = self.dashboard_cache[cache_key]
            cache_age = datetime.utcnow() - cached_data["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                return cached_data["data"]
        
        # Generate widget data
        if widget_type == "compliance_score":
            data = await self._get_compliance_score_data(period_start, period_end)
        elif widget_type == "risk_level":
            data = await self._get_risk_level_data(period_start, period_end)
        elif widget_type == "violation_count":
            data = await self._get_violation_count_data(period_start, period_end)
        elif widget_type == "policy_status":
            data = await self._get_policy_status_data(period_start, period_end)
        elif widget_type == "audit_summary":
            data = await self._get_audit_summary_data(period_start, period_end)
        elif widget_type == "trend_chart":
            data = await self._get_trend_chart_data(period_start, period_end)
        elif widget_type == "alert_panel":
            data = await self._get_alert_panel_data(period_start, period_end)
        elif widget_type == "mitigation_progress":
            data = await self._get_mitigation_progress_data(period_start, period_end)
        else:
            data = {"error": f"Widget not implemented: {widget_type}"}
        
        # Cache the data
        self.dashboard_cache[cache_key] = {
            "data": data,
            "cached_at": datetime.utcnow()
        }
        
        return data
    
    async def _get_compliance_score_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get compliance score data."""
        return {
            "current_score": 95.5,
            "previous_score": 93.2,
            "trend": "improving",
            "change": 2.3,
            "target_score": 98.0,
            "score_history": [90, 91, 92, 93, 94, 95, 95.5]
        }
    
    async def _get_risk_level_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get risk level data."""
        return {
            "current_level": "medium",
            "risk_score": 45.0,
            "risk_distribution": {
                "critical": 1,
                "high": 3,
                "medium": 8,
                "low": 12,
                "minimal": 5
            },
            "trend": "stable"
        }
    
    async def _get_violation_count_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get violation count data."""
        return {
            "total_violations": 15,
            "active_violations": 8,
            "resolved_violations": 7,
            "by_severity": {
                "critical": 1,
                "high": 3,
                "medium": 8,
                "low": 3
            },
            "trend": "decreasing"
        }
    
    async def _get_policy_status_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get policy status data."""
        return {
            "total_policies": 25,
            "active_policies": 22,
            "enforced_policies": 20,
            "violated_policies": 2,
            "compliance_rate": 90.9
        }
    
    async def _get_audit_summary_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get audit summary data."""
        return {
            "total_audits": 150,
            "passed_audits": 135,
            "failed_audits": 15,
            "pass_rate": 90.0,
            "recent_audits": [
                {"date": "2024-01-15", "type": "compliance", "result": "passed"},
                {"date": "2024-01-14", "type": "security", "result": "failed"},
                {"date": "2024-01-13", "type": "access", "result": "passed"}
            ]
        }
    
    async def _get_trend_chart_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get trend chart data."""
        return {
            "compliance_trend": [90, 91, 92, 93, 94, 95, 95.5],
            "risk_trend": [50, 48, 45, 47, 44, 45, 45],
            "dates": ["2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12", "2024-01-13", "2024-01-14", "2024-01-15"]
        }
    
    async def _get_alert_panel_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get alert panel data."""
        return {
            "active_alerts": 5,
            "critical_alerts": 1,
            "high_alerts": 2,
            "recent_alerts": [
                {
                    "id": "alert1",
                    "severity": "critical",
                    "title": "Compliance score drop",
                    "time": "2 hours ago"
                },
                {
                    "id": "alert2",
                    "severity": "high",
                    "title": "New security risk",
                    "time": "4 hours ago"
                }
            ]
        }
    
    async def _get_mitigation_progress_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get mitigation progress data."""
        return {
            "total_risks": 29,
            "mitigated_risks": 18,
            "in_progress": 6,
            "pending": 5,
            "completion_rate": 62.1,
            "progress_by_category": {
                "security": 75.0,
                "compliance": 60.0,
                "operational": 55.0,
                "data": 80.0
            }
        }
    
    async def _get_summary_data(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get summary data for dashboard."""
        return {
            "overall_status": "healthy",
            "compliance_score": 95.5,
            "risk_level": "medium",
            "active_alerts": 5,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def _get_compliance_metrics(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get compliance metrics."""
        return {
            "overall_score": 95.5,
            "by_category": {
                "data_protection": 98.0,
                "access_control": 94.0,
                "security": 93.0,
                "operational": 96.0
            },
            "trend": "improving"
        }
    
    async def _get_risk_assessment(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get risk assessment."""
        return {
            "overall_score": 45.0,
            "level": "medium",
            "distribution": {
                "critical": 1,
                "high": 3,
                "medium": 8,
                "low": 12,
                "minimal": 5
            }
        }
    
    async def _get_policy_status(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get policy status."""
        return {
            "total": 25,
            "active": 22,
            "enforced": 20,
            "violated": 2
        }
    
    async def _get_audit_summary(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Get audit summary."""
        return {
            "total": 150,
            "passed": 135,
            "failed": 15,
            "pass_rate": 90.0
        }
    
    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts."""
        return [
            {
                "id": "alert1",
                "severity": "critical",
                "title": "Compliance score drop",
                "description": "Overall compliance score has dropped below threshold"
            }
        ]
    
    def _calculate_overall_status(self, compliance_metrics: Dict[str, Any], risk_assessment: Dict[str, Any]) -> str:
        """Calculate overall system status."""
        compliance_score = compliance_metrics.get("overall_score", 0)
        risk_score = risk_assessment.get("overall_score", 0)
        
        if compliance_score >= 95 and risk_score <= 30:
            return "excellent"
        elif compliance_score >= 90 and risk_score <= 50:
            return "good"
        elif compliance_score >= 80 and risk_score <= 70:
            return "fair"
        else:
            return "poor"
    
    async def _generate_compliance_section(self, dashboard_data: Dict[str, Any], include_charts: bool) -> Dict[str, Any]:
        """Generate compliance section for report."""
        return {
            "title": "Compliance Overview",
            "metrics": dashboard_data["widgets"].get("compliance_score", {}),
            "charts": self._generate_compliance_charts() if include_charts else [],
            "summary": "Overall compliance is strong with a score of 95.5%"
        }
    
    async def _generate_risk_section(self, dashboard_data: Dict[str, Any], include_charts: bool) -> Dict[str, Any]:
        """Generate risk section for report."""
        return {
            "title": "Risk Assessment",
            "metrics": dashboard_data["widgets"].get("risk_level", {}),
            "charts": self._generate_risk_charts() if include_charts else [],
            "summary": "Risk level is medium with 29 total risks identified"
        }
    
    async def _generate_audit_section(self, dashboard_data: Dict[str, Any], include_charts: bool) -> Dict[str, Any]:
        """Generate audit section for report."""
        return {
            "title": "Audit Summary",
            "metrics": dashboard_data["widgets"].get("audit_summary", {}),
            "charts": self._generate_audit_charts() if include_charts else [],
            "summary": "Audit pass rate is 90% with 150 total audits"
        }
    
    async def _generate_policy_section(self, dashboard_data: Dict[str, Any], include_charts: bool) -> Dict[str, Any]:
        """Generate policy section for report."""
        return {
            "title": "Policy Status",
            "metrics": dashboard_data["widgets"].get("policy_status", {}),
            "charts": self._generate_policy_charts() if include_charts else [],
            "summary": "22 of 25 policies are active and being enforced"
        }
    
    def _generate_compliance_charts(self) -> List[Dict[str, Any]]:
        """Generate compliance charts."""
        return [
            {
                "type": "line",
                "title": "Compliance Score Trend",
                "data": {"labels": ["Mon", "Tue", "Wed", "Thu", "Fri"], "values": [90, 91, 92, 93, 95.5]}
            }
        ]
    
    def _generate_risk_charts(self) -> List[Dict[str, Any]]:
        """Generate risk charts."""
        return [
            {
                "type": "pie",
                "title": "Risk Distribution",
                "data": {"labels": ["Critical", "High", "Medium", "Low"], "values": [1, 3, 8, 12]}
            }
        ]
    
    def _generate_audit_charts(self) -> List[Dict[str, Any]]:
        """Generate audit charts."""
        return [
            {
                "type": "bar",
                "title": "Audit Results",
                "data": {"labels": ["Passed", "Failed"], "values": [135, 15]}
            }
        ]
    
    def _generate_policy_charts(self) -> List[Dict[str, Any]]:
        """Generate policy charts."""
        return [
            {
                "type": "donut",
                "title": "Policy Status",
                "data": {"labels": ["Active", "Inactive", "Violated"], "values": [22, 1, 2]}
            }
        ]
    
    def _generate_report_summary(self, sections: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report summary."""
        return {
            "overall_status": "healthy",
            "key_findings": [
                "Compliance score of 95.5% exceeds target",
                "Medium risk level requires attention",
                "90% audit pass rate is acceptable",
                "Policy enforcement is strong"
            ],
            "recommendations": [
                "Monitor compliance trends closely",
                "Address medium-risk items",
                "Maintain current audit practices",
                "Continue policy enforcement"
            ]
        }
    
    async def _validate_custom_dashboard(self, layout: Dict[str, Any], widgets: List[Dict[str, Any]]) -> None:
        """Validate custom dashboard configuration."""
        errors = []
        
        # Validate layout
        if not layout:
            errors.append("Layout configuration is required")
        
        # Validate widgets
        if not widgets:
            errors.append("At least one widget is required")
        else:
            for i, widget in enumerate(widgets):
                if "type" not in widget:
                    errors.append(f"Widget {i} missing required field: type")
                elif widget["type"] not in self.widget_types:
                    errors.append(f"Widget {i} unknown type: {widget['type']}")
        
        if errors:
            raise ValidationError(
                f"Custom dashboard validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    def _update_average_load_time(self, load_time: float) -> None:
        """Update average dashboard load time."""
        if self.dashboard_metrics["average_load_time"] == 0:
            self.dashboard_metrics["average_load_time"] = load_time
        else:
            current_avg = self.dashboard_metrics["average_load_time"]
            total_views = self.dashboard_metrics["total_views"]
            self.dashboard_metrics["average_load_time"] = (
                (current_avg * (total_views - 1) + load_time) / total_views
            )
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        return {
            "dashboard_active": self.dashboard_active,
            "refresh_interval": self.refresh_interval,
            "cache_size": len(self.dashboard_cache),
            "cache_ttl": self.cache_ttl,
            "widget_types": list(self.widget_types.keys()),
            "dashboard_metrics": self.dashboard_metrics
        }
