"""
BaseLayer Risk Assessor

Risk assessment and mitigation system
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
    GovernanceRule, AuditLog,
    RuleType, ComplianceStatus
)
from ..models.user import User
from .exceptions import (
    RiskError,
    ValidationError
)

logger = get_logger(__name__)


class RiskAssessor:
    """
    Risk assessment and mitigation system.
    
    Identifies, assesses, and mitigates risks across all
    subsystems with comprehensive risk management.
    """
    
    def __init__(self):
        self.assessment_active: bool = False
        self.risk_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 3600  # 1 hour
        self.assessment_interval: int = 86400  # 24 hours
        
        # Risk categories and levels
        self.risk_categories = {
            "security": {
                "description": "Security risks",
                "factors": ["vulnerabilities", "threats", "breaches", "malware"],
                "mitigation_strategies": ["patch", "monitor", "isolate", "educate"]
            },
            "compliance": {
                "description": "Compliance risks",
                "factors": ["violations", "non_compliance", "audit_failures", "regulatory_changes"],
                "mitigation_strategies": ["remediate", "document", "train", "monitor"]
            },
            "operational": {
                "description": "Operational risks",
                "factors": ["downtime", "performance", "capacity", "process_failures"],
                "mitigation_strategies": ["redundancy", "monitor", "optimize", "automate"]
            },
            "data": {
                "description": "Data risks",
                "factors": ["loss", "corruption", "breach", "unauthorized_access"],
                "mitigation_strategies": ["encrypt", "backup", "access_control", "audit"]
            },
            "financial": {
                "description": "Financial risks",
                "factors": ["fraud", "loss", "theft", "mismanagement"],
                "mitigation_strategies": ["segregate", "audit", "monitor", "insure"]
            },
            "reputation": {
                "description": "Reputation risks",
                "factors": ["negative_publicity", "customer_dissatisfaction", "scandals"],
                "mitigation_strategies": ["monitor", "respond", "improve", "communicate"]
            }
        }
        
        # Risk levels
        self.risk_levels = {
            "critical": {
                "score_range": (80, 100),
                "color": "red",
                "response_time": 1,  # hours
                "escalation": "immediate"
            },
            "high": {
                "score_range": (60, 79),
                "color": "orange",
                "response_time": 4,  # hours
                "escalation": "24h"
            },
            "medium": {
                "score_range": (40, 59),
                "color": "yellow",
                "response_time": 24,  # hours
                "escalation": "72h"
            },
            "low": {
                "score_range": (20, 39),
                "color": "green",
                "response_time": 168,  # hours
                "escalation": "1w"
            },
            "minimal": {
                "score_range": (0, 19),
                "color": "blue",
                "response_time": 720,  # hours
                "escalation": "1m"
            }
        }
        
        # Risk metrics
        self.risk_metrics = {
            "total_assessments": 0,
            "risks_identified": 0,
            "risks_mitigated": 0,
            "average_risk_score": 0.0,
            "critical_risks": 0,
            "high_risks": 0
        }
    
    async def start(self) -> None:
        """Start the risk assessor."""
        if self.assessment_active:
            return
        
        self.assessment_active = True
        asyncio.create_task(self._assessment_loop())
        
        logger.info("Risk assessor started")
    
    async def stop(self) -> None:
        """Stop the risk assessor."""
        self.assessment_active = False
        logger.info("Risk assessor stopped")
    
    async def assess_risk(
        self,
        risk_category: str,
        risk_description: str,
        risk_factors: List[str],
        impact_score: int,
        probability_score: int,
        affected_assets: List[str],
        mitigation_plan: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Assess a specific risk.
        
        Args:
            risk_category: Category of risk
            risk_description: Description of risk
            risk_factors: Contributing factors
            impact_score: Impact score (0-100)
            probability_score: Probability score (0-100)
            affected_assets: Affected assets
            mitigation_plan: Mitigation plan
            created_by: User who created the assessment
            
        Returns:
            Dict[str, Any]: Risk assessment result
        """
        try:
            # Validate inputs
            await self._validate_risk_assessment(
                risk_category, impact_score, probability_score
            )
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(impact_score, probability_score)
            
            # Determine risk level
            risk_level = self._determine_risk_level(risk_score)
            
            # Generate risk ID
            risk_id = str(uuid.uuid4())
            
            # Create assessment result
            assessment_result = {
                "risk_id": risk_id,
                "risk_category": risk_category,
                "risk_description": risk_description,
                "risk_factors": risk_factors,
                "impact_score": impact_score,
                "probability_score": probability_score,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "affected_assets": affected_assets,
                "mitigation_plan": mitigation_plan or self._generate_mitigation_plan(risk_category, risk_level),
                "assessment_timestamp": datetime.utcnow().isoformat(),
                "assessed_by": str(created_by) if created_by else None,
                "status": "identified"
            }
            
            # Cache assessment
            self._cache_risk_assessment(risk_id, assessment_result)
            
            # Update metrics
            self.risk_metrics["total_assessments"] += 1
            self.risk_metrics["risks_identified"] += 1
            
            if risk_level == "critical":
                self.risk_metrics["critical_risks"] += 1
            elif risk_level == "high":
                self.risk_metrics["high_risks"] += 1
            
            # Update average risk score
            self._update_average_risk_score(risk_score)
            
            logger.info(
                "Risk assessed",
                risk_id=risk_id,
                category=risk_category,
                level=risk_level,
                score=risk_score
            )
            
            return assessment_result
            
        except Exception as e:
            raise RiskError(f"Failed to assess risk: {str(e)}") from e
    
    async def run_system_risk_assessment(self) -> Dict[str, Any]:
        """
        Run comprehensive system risk assessment.
        
        Returns:
            Dict[str, Any]: System risk assessment results
        """
        try:
            start_time = datetime.utcnow()
            
            # Assess risks across all categories
            category_assessments = {}
            total_risks = []
            
            for category, config in self.risk_categories.items():
                category_risks = await self._assess_category_risks(category)
                category_assessments[category] = category_risks
                total_risks.extend(category_risks)
            
            # Calculate overall risk metrics
            overall_metrics = self._calculate_overall_risk_metrics(total_risks)
            
            # Generate risk dashboard
            risk_dashboard = self._generate_risk_dashboard(total_risks, category_assessments)
            
            # Identify top risks
            top_risks = self._identify_top_risks(total_risks)
            
            # Generate recommendations
            recommendations = self._generate_risk_recommendations(total_risks, category_assessments)
            
            assessment_duration = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "assessment_id": str(uuid.uuid4()),
                "assessment_timestamp": start_time.isoformat(),
                "assessment_duration": assessment_duration,
                "category_assessments": category_assessments,
                "overall_metrics": overall_metrics,
                "risk_dashboard": risk_dashboard,
                "top_risks": top_risks,
                "recommendations": recommendations,
                "total_risks": len(total_risks)
            }
            
            logger.info(
                "System risk assessment completed",
                assessment_id=result["assessment_id"],
                total_risks=len(total_risks),
                overall_score=overall_metrics["average_score"]
            )
            
            return result
            
        except Exception as e:
            raise RiskError(f"Failed to run system risk assessment: {str(e)}") from e
    
    async def get_risk_assessment(
        self,
        risk_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific risk assessment.
        
        Args:
            risk_id: Risk assessment ID
            
        Returns:
            Dict[str, Any]: Risk assessment or None
        """
        # Check cache first
        cache_key = f"risk_{risk_id}"
        if cache_key in self.risk_cache:
            cached_assessment = self.risk_cache[cache_key]
            cache_age = datetime.utcnow() - cached_assessment["cached_at"]
            
            if cache_age.total_seconds() < self.cache_ttl:
                return cached_assessment["assessment"]
        
        # Risk assessment not found in cache
        return None
    
    async def update_risk_mitigation(
        self,
        risk_id: str,
        mitigation_actions: List[Dict[str, Any]],
        mitigation_status: str,
        updated_by: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Update risk mitigation actions.
        
        Args:
            risk_id: Risk assessment ID
            mitigation_actions: Mitigation actions taken
            mitigation_status: Current mitigation status
            updated_by: User who updated the mitigation
            
        Returns:
            bool: True if updated successfully
        """
        try:
            # Get risk assessment
            assessment = await self.get_risk_assessment(risk_id)
            if not assessment:
                return False
            
            # Update mitigation
            assessment["mitigation_actions"] = mitigation_actions
            assessment["mitigation_status"] = mitigation_status
            assessment["mitigation_updated_at"] = datetime.utcnow().isoformat()
            assessment["mitigation_updated_by"] = str(updated_by) if updated_by else None
            
            # Update cache
            self._cache_risk_assessment(risk_id, assessment)
            
            # Update metrics
            if mitigation_status == "mitigated":
                self.risk_metrics["risks_mitigated"] += 1
            
            logger.info(
                "Risk mitigation updated",
                risk_id=risk_id,
                status=mitigation_status
            )
            
            return True
            
        except Exception as e:
            raise RiskError(f"Failed to update risk mitigation: {str(e)}") from e
    
    async def get_risk_dashboard(self, time_range: str = "30d") -> Dict[str, Any]:
        """
        Get risk assessment dashboard.
        
        Args:
            time_range: Time range for data (7d, 30d, 90d)
            
        Returns:
            Dict[str, Any]: Risk dashboard data
        """
        try:
            # Calculate period based on time range
            time_ranges = {
                "7d": timedelta(days=7),
                "30d": timedelta(days=30),
                "90d": timedelta(days=90)
            }
            
            period_delta = time_ranges.get(time_range, timedelta(days=30))
            period_start = datetime.utcnow() - period_delta
            
            # Get risk trends
            risk_trends = await self._get_risk_trends(period_start)
            
            # Get risk distribution
            risk_distribution = await self._get_risk_distribution()
            
            # Get mitigation status
            mitigation_status = await self._get_mitigation_status()
            
            # Get emerging risks
            emerging_risks = await self._get_emerging_risks()
            
            dashboard_data = {
                "time_range": time_range,
                "period_start": period_start.isoformat(),
                "risk_trends": risk_trends,
                "risk_distribution": risk_distribution,
                "mitigation_status": mitigation_status,
                "emerging_risks": emerging_risks,
                "risk_metrics": self.risk_metrics,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return dashboard_data
            
        except Exception as e:
            raise RiskError(f"Failed to get risk dashboard: {str(e)}") from e
    
    async def _assessment_loop(self) -> None:
        """Main risk assessment loop."""
        while self.assessment_active:
            try:
                # Run scheduled system assessment
                await self.run_system_risk_assessment()
                
                # Update risk metrics
                await self._update_risk_metrics()
                
                # Clean up old cache entries
                await self._cleanup_cache()
                
                # Sleep before next iteration
                await asyncio.sleep(self.assessment_interval)
                
            except Exception as e:
                logger.error(
                    "Risk assessment loop error",
                    error=str(e)
                )
                await asyncio.sleep(3600)  # 1 hour on error
    
    async def _validate_risk_assessment(
        self,
        risk_category: str,
        impact_score: int,
        probability_score: int
    ) -> None:
        """Validate risk assessment inputs."""
        errors = []
        
        # Validate category
        if risk_category not in self.risk_categories:
            errors.append(f"Unknown risk category: {risk_category}")
        
        # Validate scores
        if not (0 <= impact_score <= 100):
            errors.append("Impact score must be between 0 and 100")
        
        if not (0 <= probability_score <= 100):
            errors.append("Probability score must be between 0 and 100")
        
        if errors:
            raise ValidationError(
                f"Risk assessment validation failed: {'; '.join(errors)}",
                validation_errors=errors
            )
    
    def _calculate_risk_score(self, impact_score: int, probability_score: int) -> int:
        """Calculate overall risk score."""
        # Weighted calculation: 60% impact, 40% probability
        return int((impact_score * 0.6) + (probability_score * 0.4))
    
    def _determine_risk_level(self, risk_score: int) -> str:
        """Determine risk level from score."""
        for level, config in self.risk_levels.items():
            min_score, max_score = config["score_range"]
            if min_score <= risk_score <= max_score:
                return level
        
        return "minimal"
    
    def _generate_mitigation_plan(self, risk_category: str, risk_level: str) -> Dict[str, Any]:
        """Generate default mitigation plan."""
        category_config = self.risk_categories.get(risk_category, {})
        strategies = category_config.get("mitigation_strategies", [])
        
        level_config = self.risk_levels.get(risk_level, {})
        response_time = level_config.get("response_time", 24)
        
        return {
            "strategies": strategies,
            "response_time_hours": response_time,
            "escalation_policy": level_config.get("escalation", "72h"),
            "monitoring_frequency": self._get_monitoring_frequency(risk_level),
            "auto_mitigation": risk_level in ["low", "minimal"]
        }
    
    def _get_monitoring_frequency(self, risk_level: str) -> str:
        """Get monitoring frequency based on risk level."""
        frequencies = {
            "critical": "continuous",
            "high": "hourly",
            "medium": "daily",
            "low": "weekly",
            "minimal": "monthly"
        }
        return frequencies.get(risk_level, "daily")
    
    async def _assess_category_risks(self, category: str) -> List[Dict[str, Any]]:
        """Assess risks for a specific category."""
        category_risks = []
        category_config = self.risk_categories.get(category, {})
        factors = category_config.get("factors", [])
        
        # Generate mock risks for demonstration
        for factor in factors:
            # In real implementation, would analyze actual system data
            impact_score = 50 + (hash(factor) % 40)  # 50-90
            probability_score = 30 + (hash(factor) % 50)  # 30-80
            
            risk = await self.assess_risk(
                risk_category=category,
                risk_description=f"Risk factor: {factor}",
                risk_factors=[factor],
                impact_score=impact_score,
                probability_score=probability_score,
                affected_assets=[f"asset_{factor}"],
                mitigation_plan=None
            )
            
            category_risks.append(risk)
        
        return category_risks
    
    def _calculate_overall_risk_metrics(self, risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall risk metrics."""
        if not risks:
            return {
                "average_score": 0,
                "risk_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0, "minimal": 0},
                "highest_risk": None,
                "risk_trend": "stable"
            }
        
        # Calculate average score
        total_score = sum(r["risk_score"] for r in risks)
        average_score = total_score / len(risks)
        
        # Calculate distribution
        distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0, "minimal": 0}
        for risk in risks:
            distribution[risk["risk_level"]] += 1
        
        # Find highest risk
        highest_risk = max(risks, key=lambda r: r["risk_score"])
        
        # Determine trend (mock data)
        risk_trend = "improving" if average_score < 50 else "degrading"
        
        return {
            "average_score": average_score,
            "risk_distribution": distribution,
            "highest_risk": {
                "id": highest_risk["risk_id"],
                "category": highest_risk["risk_category"],
                "score": highest_risk["risk_score"],
                "level": highest_risk["risk_level"]
            },
            "risk_trend": risk_trend
        }
    
    def _generate_risk_dashboard(self, total_risks: List[Dict[str, Any]], category_assessments: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Generate risk dashboard data."""
        return {
            "total_risks": len(total_risks),
            "risks_by_level": self._group_risks_by_level(total_risks),
            "risks_by_category": {
                category: len(risks) for category, risks in category_assessments.items()
            },
            "risk_heatmap": self._generate_risk_heatmap(total_risks),
            "mitigation_progress": self._calculate_mitigation_progress(total_risks)
        }
    
    def _group_risks_by_level(self, risks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group risks by level."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "minimal": 0}
        
        for risk in risks:
            level = risk["risk_level"]
            if level in counts:
                counts[level] += 1
        
        return counts
    
    def _generate_risk_heatmap(self, risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate risk heatmap data."""
        heatmap_data = []
        
        for risk in risks:
            heatmap_data.append({
                "category": risk["risk_category"],
                "level": risk["risk_level"],
                "score": risk["risk_score"],
                "description": risk["risk_description"]
            })
        
        return heatmap_data
    
    def _calculate_mitigation_progress(self, risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate mitigation progress."""
        total = len(risks)
        mitigated = len([r for r in risks if r.get("mitigation_status") == "mitigated"])
        in_progress = len([r for r in risks if r.get("mitigation_status") == "in_progress"])
        
        return {
            "total": total,
            "mitigated": mitigated,
            "in_progress": in_progress,
            "pending": total - mitigated - in_progress,
            "completion_rate": (mitigated / total * 100) if total > 0 else 0
        }
    
    def _identify_top_risks(self, risks: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        """Identify top risks by score."""
        sorted_risks = sorted(risks, key=lambda r: r["risk_score"], reverse=True)
        return sorted_risks[:limit]
    
    def _generate_risk_recommendations(self, total_risks: List[Dict[str, Any]], category_assessments: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Generate risk mitigation recommendations."""
        recommendations = []
        
        # High-level recommendations
        critical_count = len([r for r in total_risks if r["risk_level"] == "critical"])
        if critical_count > 0:
            recommendations.append({
                "priority": "critical",
                "category": "immediate",
                "description": f"Address {critical_count} critical risks immediately",
                "actions": ["Implement emergency mitigation", "Escalate to management", "Increase monitoring"]
            })
        
        # Category-specific recommendations
        for category, risks in category_assessments.items():
            high_risks = [r for r in risks if r["risk_level"] in ["critical", "high"]]
            if len(high_risks) > 2:
                recommendations.append({
                    "priority": "high",
                    "category": category,
                    "description": f"Multiple high risks in {category}",
                    "actions": self.risk_categories[category]["mitigation_strategies"]
                })
        
        return recommendations
    
    async def _get_risk_trends(self, period_start: datetime) -> Dict[str, Any]:
        """Get risk trends over time."""
        # In real implementation, would query historical data
        return {
            "trend": "improving",
            "daily_scores": [75, 73, 71, 69, 67, 65, 63, 61, 59, 57],
            "risk_count_trend": "decreasing"
        }
    
    async def _get_risk_distribution(self) -> Dict[str, Any]:
        """Get current risk distribution."""
        return {
            "by_level": self.risk_metrics,
            "by_category": {
                category: 5 for category in self.risk_categories.keys()
            }
        }
    
    async def _get_mitigation_status(self) -> Dict[str, Any]:
        """Get mitigation status."""
        return {
            "total_mitigated": self.risk_metrics["risks_mitigated"],
            "in_progress": 3,
            "pending": 7,
            "completion_rate": 40.0
        }
    
    async def _get_emerging_risks(self) -> List[Dict[str, Any]]:
        """Get emerging risks."""
        return [
            {
                "risk_id": "er1",
                "description": "New security vulnerability detected",
                "category": "security",
                "potential_impact": "high",
                "detected_at": datetime.utcnow().isoformat()
            }
        ]
    
    async def _update_risk_metrics(self) -> None:
        """Update risk metrics from database."""
        # In real implementation, would calculate from database
        pass
    
    async def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.utcnow()
        
        for key, (timestamp, _) in list(self.risk_cache.items()):
            if current_time - timestamp > timedelta(seconds=self.cache_ttl):
                del self.risk_cache[key]
    
    def _update_average_risk_score(self, new_score: int) -> None:
        """Update average risk score."""
        if self.risk_metrics["average_risk_score"] == 0:
            self.risk_metrics["average_risk_score"] = new_score
        else:
            current_avg = self.risk_metrics["average_risk_score"]
            total_assessments = self.risk_metrics["total_assessments"]
            self.risk_metrics["average_risk_score"] = (
                (current_avg * (total_assessments - 1) + new_score) / total_assessments
            )
    
    def _cache_risk_assessment(self, risk_id: str, assessment: Dict[str, Any]) -> None:
        """Cache a risk assessment."""
        cache_key = f"risk_{risk_id}"
        self.risk_cache[cache_key] = {
            "assessment": assessment,
            "cached_at": datetime.utcnow()
        }
    
    def get_risk_assessor_stats(self) -> Dict[str, Any]:
        """Get risk assessor statistics."""
        return {
            "assessment_active": self.assessment_active,
            "assessment_interval": self.assessment_interval,
            "cache_size": len(self.risk_cache),
            "cache_ttl": self.cache_ttl,
            "risk_categories": list(self.risk_categories.keys()),
            "risk_levels": list(self.risk_levels.keys()),
            "risk_metrics": self.risk_metrics
        }
