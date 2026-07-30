"""
CODEX Knowledge Snapshot Models

SQLAlchemy models for daily knowledge base snapshots
and tracking knowledge growth over time.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import (
    Column, String, Integer, DateTime, Text,
    JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarativeBase()


class KnowledgeSnapshot(Base):
    """
    Daily snapshot of knowledge base state.
    
    Tracks knowledge growth, distribution, and health
    metrics for analytics and monitoring.
    """
    __tablename__ = "codex_knowledge_snapshots"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Snapshot metadata
    snapshot_date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    total_entries = Column(Integer, nullable=False)
    
    # Distribution data
    entries_by_type = Column(JSON, nullable=False)  # Count by entry_type
    entries_by_engine = Column(JSON, nullable=False)  # Count by source_engine
    entries_by_confidence = Column(JSON, nullable=False)  # Count by confidence ranges
    
    # Health metrics
    avg_confidence = Column(Float, nullable=False)
    avg_access_frequency = Column(Float, nullable=False)
    archived_count = Column(Integer, nullable=False, default=0)
    expired_count = Column(Integer, nullable=False, default=0)
    
    # Growth metrics
    new_entries_today = Column(Integer, nullable=False, default=0)
    entries_with_embeddings = Column(Integer, nullable=False, default=0)
    total_links = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    avg_embedding_time_ms = Column(Float, nullable=True)
    avg_search_time_ms = Column(Float, nullable=True)
    cache_hit_rate = Column(Float, nullable=True)
    
    # Additional data
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_snapshot_date', 'snapshot_date'),
        Index('idx_snapshot_created_at', 'created_at'),
        Index('idx_snapshot_total_entries', 'total_entries'),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeSnapshot(id={self.id}, date={self.snapshot_date}, entries={self.total_entries})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "snapshot_date": self.snapshot_date.isoformat() if self.snapshot_date else None,
            "total_entries": self.total_entries,
            "entries_by_type": self.entries_by_type,
            "entries_by_engine": self.entries_by_engine,
            "entries_by_confidence": self.entries_by_confidence,
            "avg_confidence": self.avg_confidence,
            "avg_access_frequency": self.avg_access_frequency,
            "archived_count": self.archived_count,
            "expired_count": self.expired_count,
            "new_entries_today": self.new_entries_today,
            "entries_with_embeddings": self.entries_with_embeddings,
            "total_links": self.total_links,
            "avg_embedding_time_ms": self.avg_embedding_time_ms,
            "avg_search_time_ms": self.avg_search_time_ms,
            "cache_hit_rate": self.cache_hit_rate,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def get_entry_count_by_type(self, entry_type: str) -> int:
        """Get count of entries by specific type."""
        if not self.entries_by_type:
            return 0
        return self.entries_by_type.get(entry_type, 0)
    
    def get_entry_count_by_engine(self, engine: str) -> int:
        """Get count of entries by specific engine."""
        if not self.entries_by_engine:
            return 0
        return self.entries_by_engine.get(engine, 0)
    
    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get confidence distribution ranges."""
        if not self.entries_by_confidence:
            return {}
        return self.entries_by_confidence
    
    def get_high_confidence_count(self, threshold: float = 0.8) -> int:
        """Get count of high confidence entries."""
        if not self.entries_by_confidence:
            return 0
        
        high_confidence_ranges = [
            "0.8-0.9",
            "0.9-1.0"
        ]
        
        count = 0
        for range_key in high_confidence_ranges:
            count += self.entries_by_confidence.get(range_key, 0)
        
        return count
    
    def get_low_confidence_count(self, threshold: float = 0.3) -> int:
        """Get count of low confidence entries."""
        if not self.entries_by_confidence:
            return 0
        
        low_confidence_ranges = [
            "0.0-0.1",
            "0.1-0.2",
            "0.2-0.3"
        ]
        
        count = 0
        for range_key in low_confidence_ranges:
            count += self.entries_by_confidence.get(range_key, 0)
        
        return count
    
    def get_active_percentage(self) -> float:
        """Get percentage of active (non-archived) entries."""
        if self.total_entries == 0:
            return 0.0
        
        active_count = self.total_entries - self.archived_count
        return (active_count / self.total_entries) * 100
    
    def get_embedding_coverage(self) -> float:
        """Get percentage of entries with embeddings."""
        if self.total_entries == 0:
            return 0.0
        
        return (self.entries_with_embeddings / self.total_entries) * 100
    
    def get_growth_rate(self, previous_snapshot: 'KnowledgeSnapshot') -> float:
        """Calculate growth rate compared to previous snapshot."""
        if not previous_snapshot or previous_snapshot.total_entries == 0:
            return 0.0
        
        growth = self.total_entries - previous_snapshot.total_entries
        return (growth / previous_snapshot.total_entries) * 100
    
    def get_confidence_trend(self, previous_snapshot: 'KnowledgeSnapshot') -> float:
        """Calculate confidence trend compared to previous snapshot."""
        if not previous_snapshot:
            return 0.0
        
        confidence_change = self.avg_confidence - previous_snapshot.avg_confidence
        return confidence_change * 100  # Convert to percentage points
    
    def get_engine_distribution(self) -> Dict[str, float]:
        """Get percentage distribution by engine."""
        if not self.entries_by_engine or self.total_entries == 0:
            return {}
        
        distribution = {}
        for engine, count in self.entries_by_engine.items():
            distribution[engine] = (count / self.total_entries) * 100
        
        return distribution
    
    def get_type_distribution(self) -> Dict[str, float]:
        """Get percentage distribution by entry type."""
        if not self.entries_by_type or self.total_entries == 0:
            return {}
        
        distribution = {}
        for entry_type, count in self.entries_by_type.items():
            distribution[entry_type] = (count / self.total_entries) * 100
        
        return distribution
    
    def get_health_score(self) -> float:
        """Calculate overall knowledge base health score."""
        scores = []
        
        # Active entries score (40% weight)
        active_score = self.get_active_percentage()
        scores.append(active_score * 0.4)
        
        # Confidence score (30% weight)
        confidence_score = self.avg_confidence * 100
        scores.append(confidence_score * 0.3)
        
        # Embedding coverage score (20% weight)
        embedding_score = self.get_embedding_coverage()
        scores.append(embedding_score * 0.2)
        
        # Access frequency score (10% weight)
        access_score = min(100, self.avg_access_frequency * 100)  # Cap at 100
        scores.append(access_score * 0.1)
        
        return sum(scores)
    
    def get_performance_rating(self) -> str:
        """Get performance rating based on metrics."""
        health_score = self.get_health_score()
        
        if health_score >= 90:
            return "excellent"
        elif health_score >= 80:
            return "good"
        elif health_score >= 70:
            return "fair"
        elif health_score >= 60:
            return "poor"
        else:
            return "critical"
    
    def identify_issues(self) -> list:
        """Identify potential issues in the knowledge base."""
        issues = []
        
        # Low active percentage
        if self.get_active_percentage() < 80:
            issues.append({
                "type": "low_active_percentage",
                "severity": "high",
                "message": f"Only {self.get_active_percentage():.1f}% entries are active",
                "recommendation": "Review and prune archived entries"
            })
        
        # Low average confidence
        if self.avg_confidence < 0.6:
            issues.append({
                "type": "low_confidence",
                "severity": "medium",
                "message": f"Average confidence is {self.avg_confidence:.2f}",
                "recommendation": "Review and improve low-confidence entries"
            })
        
        # Low embedding coverage
        if self.get_embedding_coverage() < 80:
            issues.append({
                "type": "low_embedding_coverage",
                "severity": "medium",
                "message": f"Only {self.get_embedding_coverage():.1f}% entries have embeddings",
                "recommendation": "Generate embeddings for remaining entries"
            })
        
        # High archived count
        if self.archived_count > self.total_entries * 0.3:
            issues.append({
                "type": "high_archived_count",
                "severity": "medium",
                "message": f"{self.archived_count} entries are archived ({(self.archived_count/self.total_entries)*100:.1f}%)",
                "recommendation": "Consider pruning old archived entries"
            })
        
        # Performance issues
        if self.avg_search_time_ms and self.avg_search_time_ms > 100:
            issues.append({
                "type": "slow_search",
                "severity": "medium",
                "message": f"Average search time is {self.avg_search_time_ms:.1f}ms",
                "recommendation": "Optimize vector search indexes"
            })
        
        if self.avg_embedding_time_ms and self.avg_embedding_time_ms > 500:
            issues.append({
                "type": "slow_embedding",
                "severity": "low",
                "message": f"Average embedding time is {self.avg_embedding_time_ms:.1f}ms",
                "recommendation": "Consider embedding cache optimization"
            })
        
        return issues
    
    def get_summary(self) -> dict:
        """Get snapshot summary for dashboard."""
        return {
            "id": str(self.id),
            "snapshot_date": self.snapshot_date.isoformat() if self.snapshot_date else None,
            "total_entries": self.total_entries,
            "new_entries_today": self.new_entries_today,
            "avg_confidence": self.avg_confidence,
            "health_score": self.get_health_score(),
            "performance_rating": self.get_performance_rating(),
            "active_percentage": self.get_active_percentage(),
            "embedding_coverage": self.get_embedding_coverage(),
            "issues_count": len(self.identify_issues()),
            "engine_distribution": self.get_engine_distribution(),
            "type_distribution": self.get_type_distribution()
        }
