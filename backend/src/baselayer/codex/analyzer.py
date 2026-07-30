"""
BaseLayer Knowledge Analyzer

AI-powered knowledge analysis, categorization, and insights
for the Codex/Memory subsystem.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from structlog import get_logger

from ..core.database import get_db_session
from ..models.codex import (
    KnowledgeEntry, KnowledgeCategory, KnowledgeTag,
    KnowledgeType, EntryType, KnowledgeStatus
)
from .exceptions import AnalysisError, AIModelError

logger = get_logger(__name__)


class KnowledgeAnalyzer:
    """
    AI-powered knowledge analysis engine.
    
    Provides content analysis, categorization, sentiment analysis,
    and knowledge insights with AI integration.
    """
    
    def __init__(self):
        self.analysis_queue: asyncio.Queue = asyncio.Queue()
        self.analysis_active: bool = False
        self.max_concurrent_analysis: int = 2  # Optimized for i5-2400
        self.ai_model_timeout: int = 30  # seconds
        self.analysis_cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        self.cache_ttl: int = 3600  # 1 hour
        self.ai_enabled: bool = True
    
    async def start_analysis_worker(self) -> None:
        """Start the background analysis worker."""
        if self.analysis_active:
            return
        
        self.analysis_active = True
        asyncio.create_task(self._analysis_worker_loop())
        
        logger.info("Knowledge analysis worker started")
    
    async def stop_analysis_worker(self) -> None:
        """Stop the analysis worker."""
        self.analysis_active = False
        logger.info("Knowledge analysis worker stopped")
    
    async def _analysis_worker_loop(self) -> None:
        """Main analysis worker loop."""
        while self.analysis_active:
            try:
                # Get next analysis task
                analysis_task = await asyncio.wait_for(
                    self.analysis_queue.get(),
                    timeout=60.0
                )
                await self._process_analysis_task(analysis_task)
                
            except asyncio.TimeoutError:
                # No analysis tasks, continue
                continue
            except Exception as e:
                logger.error(
                    "Analysis worker error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def analyze_content(
        self,
        content: str,
        analysis_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze content using AI models.
        
        Args:
            content: Content to analyze
            analysis_types: Types of analysis to perform
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        if analysis_types is None:
            analysis_types = ["sentiment", "topics", "entities", "summary"]
        
        # Check cache
        cache_key = self._generate_analysis_cache_key(content, analysis_types)
        cached_result = self._get_from_cache(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            results = {}
            
            for analysis_type in analysis_types:
                if analysis_type == "sentiment":
                    results["sentiment"] = await self._analyze_sentiment(content)
                elif analysis_type == "topics":
                    results["topics"] = await self._analyze_topics(content)
                elif analysis_type == "entities":
                    results["entities"] = await self._analyze_entities(content)
                elif analysis_type == "summary":
                    results["summary"] = await self._generate_summary(content)
                elif analysis_type == "readability":
                    results["readability"] = await self._analyze_readability(content)
                elif analysis_type == "complexity":
                    results["complexity"] = await self._analyze_complexity(content)
                elif analysis_type == "keywords":
                    results["keywords"] = await self._extract_keywords(content)
                else:
                    logger.warning(
                        "Unknown analysis type",
                        analysis_type=analysis_type
                    )
            
            # Cache results
            self._set_cache(cache_key, results)
            
            return results
            
        except Exception as e:
            logger.error(
                "Content analysis failed",
                error=str(e)
            )
            raise AnalysisError(f"Analysis failed: {str(e)}") from e
    
    async def categorize_entry(
        self,
        entry: KnowledgeEntry
    ) -> Dict[str, Any]:
        """
        Auto-categorize a knowledge entry.
        
        Args:
            entry: Knowledge entry to categorize
            
        Returns:
            Dict[str, Any]: Categorization results
        """
        try:
            # Analyze content
            analysis = await self.analyze_content(
                entry.content,
                ["topics", "entities", "keywords"]
            )
            
            # Suggest categories based on analysis
            suggested_categories = await self._suggest_categories(
                entry.title,
                entry.content,
                analysis
            )
            
            # Suggest tags
            suggested_tags = await self._suggest_tags(
                entry.title,
                entry.content,
                analysis
            )
            
            # Determine knowledge type
            suggested_type = await self._suggest_knowledge_type(
                entry.title,
                entry.content,
                analysis
            )
            
            # Determine entry type
            suggested_entry_type = await self._suggest_entry_type(
                entry.title,
                entry.content,
                analysis
            )
            
            results = {
                "entry_id": str(entry.id),
                "suggested_categories": suggested_categories,
                "suggested_tags": suggested_tags,
                "suggested_knowledge_type": suggested_type,
                "suggested_entry_type": suggested_entry_type,
                "confidence_scores": self._calculate_confidence_scores(analysis),
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
            return results
            
        except Exception as e:
            logger.error(
                "Entry categorization failed",
                entry_id=str(entry.id),
                error=str(e)
            )
            raise AnalysisError(f"Categorization failed: {str(e)}") from e
    
    async def get_knowledge_insights(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Get insights about the knowledge base.
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            Dict[str, Any]: Knowledge insights
        """
        try:
            async with get_db_session() as session:
                # Get entry statistics
                result = await session.execute(
                    select(
                        func.count(KnowledgeEntry.id),
                        func.count(func.distinct(KnowledgeEntry.author)),
                        func.avg(func.length(KnowledgeEntry.content))
                    ).where(
                        KnowledgeEntry.deleted_at.is_(None),
                        KnowledgeEntry.created_at >= period_start,
                        KnowledgeEntry.created_at <= period_end
                    )
                )
                stats = result.first()
                
                total_entries = stats[0] or 0
                unique_authors = stats[1] or 0
                avg_content_length = stats[2] or 0
                
                # Get distribution by type
                result = await session.execute(
                    select(
                        KnowledgeEntry.knowledge_type,
                        func.count(KnowledgeEntry.id)
                    ).where(
                        KnowledgeEntry.deleted_at.is_(None),
                        KnowledgeEntry.created_at >= period_start,
                        KnowledgeEntry.created_at <= period_end
                    ).group_by(KnowledgeEntry.knowledge_type)
                )
                type_distribution = dict(result.all())
                
                # Get popular tags
                result = await session.execute(
                    select(
                        KnowledgeTag.name,
                        func.count(KnowledgeTag.id)
                    ).join(
                        # In real implementation, this would join through association table
                        KnowledgeEntry.tags
                    ).where(
                        KnowledgeTag.deleted_at.is_(None)
                    ).group_by(KnowledgeTag.name).order_by(
                        func.count(KnowledgeTag.id).desc()
                    ).limit(10)
                )
                popular_tags = dict(result.all())
                
                # Generate insights
                insights = {
                    "period": {
                        "start": period_start.isoformat(),
                        "end": period_end.isoformat()
                    },
                    "overview": {
                        "total_entries": total_entries,
                        "unique_authors": unique_authors,
                        "average_content_length": avg_content_length,
                        "entries_per_author": total_entries / unique_authors if unique_authors > 0 else 0
                    },
                    "distribution": {
                        "by_knowledge_type": type_distribution
                    },
                    "popular_tags": popular_tags,
                    "trends": await self._analyze_trends(period_start, period_end),
                    "quality_metrics": await self._analyze_quality_metrics(period_start, period_end)
                }
                
                return insights
                
        except Exception as e:
            logger.error(
                "Knowledge insights generation failed",
                error=str(e)
            )
            raise AnalysisError(f"Insights generation failed: {str(e)}") from e
    
    async def _analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """Analyze sentiment of content."""
        try:
            # In real implementation, this would use an AI sentiment analysis model
            # For now, perform simple rule-based analysis
            
            positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic", "perfect", "best", "love", "enjoy"]
            negative_words = ["bad", "terrible", "awful", "horrible", "worst", "hate", "dislike", "poor", "fail", "problem"]
            
            words = content.lower().split()
            positive_count = sum(1 for word in words if word in positive_words)
            negative_count = sum(1 for word in words if word in negative_words)
            
            total_sentiment_words = positive_count + negative_count
            
            if total_sentiment_words == 0:
                sentiment = "neutral"
                confidence = 0.5
            else:
                sentiment_ratio = positive_count / total_sentiment_words
                
                if sentiment_ratio > 0.6:
                    sentiment = "positive"
                    confidence = min(0.9, 0.5 + sentiment_ratio)
                elif sentiment_ratio < 0.4:
                    sentiment = "negative"
                    confidence = min(0.9, 0.5 + (1 - sentiment_ratio))
                else:
                    sentiment = "neutral"
                    confidence = 0.6
            
            return {
                "sentiment": sentiment,
                "confidence": confidence,
                "positive_words": positive_count,
                "negative_words": negative_count,
                "total_words": len(words)
            }
            
        except Exception as e:
            logger.error(
                "Sentiment analysis failed",
                error=str(e)
            )
            return {"sentiment": "neutral", "confidence": 0.0, "error": str(e)}
    
    async def _analyze_topics(self, content: str) -> List[Dict[str, Any]]:
        """Analyze topics in content."""
        try:
            # In real implementation, this would use topic modeling
            # For now, extract keywords as topics
            
            # Simple keyword extraction
            import re
            
            # Extract technical terms (capitalized words, acronyms)
            technical_terms = re.findall(r'\b[A-Z]{2,}\b|\b[A-Z][a-z]+[A-Z][a-z]*\b', content)
            
            # Extract common nouns (simplified)
            common_words = ["the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "must"]
            words = content.lower().split()
            nouns = [word for word in words if word not in common_words and len(word) > 3]
            
            # Count word frequencies
            word_freq = {}
            for word in nouns:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top topics
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            
            topics = []
            for word, freq in top_words:
                relevance = min(1.0, freq / len(nouns))
                topics.append({
                    "topic": word,
                    "relevance": relevance,
                    "frequency": freq
                })
            
            return topics
            
        except Exception as e:
            logger.error(
                "Topic analysis failed",
                error=str(e)
            )
            return []
    
    async def _analyze_entities(self, content: str) -> List[Dict[str, Any]]:
        """Analyze entities in content."""
        try:
            # In real implementation, this would use NER (Named Entity Recognition)
            # For now, perform simple pattern matching
            
            import re
            
            entities = []
            
            # Extract email addresses
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
            for email in emails:
                entities.append({
                    "text": email,
                    "type": "email",
                    "confidence": 0.9
                })
            
            # Extract URLs
            urls = re.findall(r'https?://[^\s<>"{}|\\^`[\]]+', content)
            for url in urls:
                entities.append({
                    "text": url,
                    "type": "url",
                    "confidence": 0.9
                })
            
            # Extract dates (simple pattern)
            dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', content)
            for date in dates:
                entities.append({
                    "text": date,
                    "type": "date",
                    "confidence": 0.7
                })
            
            # Extract numbers with units
            numbers = re.findall(r'\b\d+(?:\.\d+)?\s*(?:KB|MB|GB|TB|ms|s|min|h|days|weeks|months|years|USD|EUR|GBP|%\b)', content)
            for number in numbers:
                entities.append({
                    "text": number,
                    "type": "measurement",
                    "confidence": 0.8
                })
            
            return entities
            
        except Exception as e:
            logger.error(
                "Entity analysis failed",
                error=str(e)
            )
            return []
    
    async def _generate_summary(self, content: str) -> str:
        """Generate summary of content."""
        try:
            # In real implementation, this would use an AI summarization model
            # For now, perform extractive summarization
            
            sentences = content.split('.')
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) <= 3:
                return content[:200] + "..." if len(content) > 200 else content
            
            # Simple extractive summarization - pick first and last sentences
            summary = sentences[0] + ". " + sentences[-1]
            
            # Limit summary length
            if len(summary) > 300:
                summary = summary[:300] + "..."
            
            return summary
            
        except Exception as e:
            logger.error(
                "Summary generation failed",
                error=str(e)
            )
            return content[:100] + "..." if len(content) > 100 else content
    
    async def _analyze_readability(self, content: str) -> Dict[str, Any]:
        """Analyze readability of content."""
        try:
            sentences = content.split('.')
            sentences = [s.strip() for s in sentences if s.strip()]
            words = content.split()
            
            # Calculate basic metrics
            avg_sentence_length = len(words) / len(sentences) if sentences else 0
            avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
            
            # Simple readability score (simplified Flesch-Kincaid)
            if avg_sentence_length > 0 and avg_word_length > 0:
                readability_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * (avg_word_length / 4.7))
            else:
                readability_score = 0
            
            # Determine readability level
            if readability_score >= 90:
                level = "Very Easy"
            elif readability_score >= 80:
                level = "Easy"
            elif readability_score >= 70:
                level = "Fairly Easy"
            elif readability_score >= 60:
                level = "Standard"
            elif readability_score >= 50:
                level = "Fairly Difficult"
            elif readability_score >= 30:
                level = "Difficult"
            else:
                level = "Very Difficult"
            
            return {
                "readability_score": readability_score,
                "readability_level": level,
                "avg_sentence_length": avg_sentence_length,
                "avg_word_length": avg_word_length,
                "total_sentences": len(sentences),
                "total_words": len(words)
            }
            
        except Exception as e:
            logger.error(
                "Readability analysis failed",
                error=str(e)
            )
            return {"readability_score": 0, "readability_level": "Unknown", "error": str(e)}
    
    async def _analyze_complexity(self, content: str) -> Dict[str, Any]:
        """Analyze complexity of content."""
        try:
            # Count complex indicators
            words = content.split()
            
            # Technical terms (simplified)
            technical_patterns = ["API", "database", "algorithm", "system", "architecture", "framework", "library", "protocol", "interface", "implementation"]
            technical_count = sum(1 for word in words if word.lower() in [t.lower() for t in technical_patterns])
            
            # Long sentences
            sentences = content.split('.')
            long_sentences = sum(1 for s in sentences if len(s.split()) > 20)
            
            # Nested structures (parentheses, brackets)
            nested_count = content.count('(') + content.count('[') + content.count('{')
            
            # Calculate complexity score
            total_indicators = technical_count + long_sentences + nested_count
            complexity_score = min(1.0, total_indicators / len(words) * 100) if words else 0
            
            # Determine complexity level
            if complexity_score < 0.1:
                level = "Simple"
            elif complexity_score < 0.3:
                level = "Moderate"
            elif complexity_score < 0.6:
                level = "Complex"
            else:
                level = "Very Complex"
            
            return {
                "complexity_score": complexity_score,
                "complexity_level": level,
                "technical_terms": technical_count,
                "long_sentences": long_sentences,
                "nested_structures": nested_count
            }
            
        except Exception as e:
            logger.error(
                "Complexity analysis failed",
                error=str(e)
            )
            return {"complexity_score": 0, "complexity_level": "Unknown", "error": str(e)}
    
    async def _extract_keywords(self, content: str) -> List[Dict[str, Any]]:
        """Extract keywords from content."""
        try:
            # Simple keyword extraction
            import re
            
            # Remove common words
            common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "must", "this", "that", "these", "those", "a", "an"}
            
            # Extract words and count frequencies
            words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
            word_freq = {}
            
            for word in words:
                if word not in common_words:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top keywords
            top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
            
            keywords = []
            for word, freq in top_keywords:
                relevance = min(1.0, freq / len(words))
                keywords.append({
                    "keyword": word,
                    "frequency": freq,
                    "relevance": relevance
                })
            
            return keywords
            
        except Exception as e:
            logger.error(
                "Keyword extraction failed",
                error=str(e)
            )
            return []
    
    async def _suggest_categories(
        self,
        title: str,
        content: str,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Suggest categories based on analysis."""
        try:
            # In real implementation, this would use AI to suggest categories
            # For now, use rule-based suggestions
            
            suggestions = []
            
            # Get available categories
            async with get_db_session() as session:
                result = await session.execute(
                    select(KnowledgeCategory).where(
                        KnowledgeCategory.deleted_at.is_(None)
                    )
                )
                categories = result.scalars().all()
                
                for category in categories:
                    score = self._calculate_category_match(title, content, category, analysis)
                    if score > 0.3:  # Minimum threshold
                        suggestions.append({
                            "category_id": str(category.id),
                            "category_name": category.name,
                            "confidence": score
                        })
            
            # Sort by confidence
            suggestions.sort(key=lambda x: x["confidence"], reverse=True)
            
            return suggestions[:5]  # Return top 5
            
        except Exception as e:
            logger.error(
                "Category suggestion failed",
                error=str(e)
            )
            return []
    
    async def _suggest_tags(
        self,
        title: str,
        content: str,
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Suggest tags based on analysis."""
        try:
            tags = []
            
            # Extract from topics
            if "topics" in analysis:
                for topic in analysis["topics"][:5]:  # Top 5 topics
                    if topic["relevance"] > 0.5:
                        tags.append(topic["topic"])
            
            # Extract from keywords
            if "keywords" in analysis:
                for keyword in analysis["keywords"][:5]:  # Top 5 keywords
                    if keyword["relevance"] > 0.6:
                        tags.append(keyword["keyword"])
            
            # Remove duplicates and limit
            unique_tags = list(set(tags))
            
            return unique_tags[:10]  # Limit to 10 tags
            
        except Exception as e:
            logger.error(
                "Tag suggestion failed",
                error=str(e)
            )
            return []
    
    async def _suggest_knowledge_type(
        self,
        title: str,
        content: str,
        analysis: Dict[str, Any]
    ) -> str:
        """Suggest knowledge type based on analysis."""
        try:
            # Rule-based type suggestion
            title_lower = title.lower()
            content_lower = content.lower()
            
            # Check for procedure
            if any(word in title_lower for word in ["how to", "step", "guide", "tutorial", "process", "procedure"]):
                return KnowledgeType.PROCEDURE.value
            
            # Check for concept
            if any(word in title_lower for word in ["what is", "definition", "concept", "theory", "principle"]):
                return KnowledgeType.CONCEPT.value
            
            # Check for reference
            if any(word in title_lower for word in ["reference", "documentation", "manual", "specification"]):
                return KnowledgeType.REFERENCE.value
            
            # Check for fact
            if any(word in title_lower for word in ["fact", "data", "statistic", "measurement"]):
                return KnowledgeType.FACT.value
            
            # Default to procedure
            return KnowledgeType.PROCEDURE.value
            
        except Exception as e:
            logger.error(
                "Knowledge type suggestion failed",
                error=str(e)
            )
            return KnowledgeType.PROCEDURE.value
    
    async def _suggest_entry_type(
        self,
        title: str,
        content: str,
        analysis: Dict[str, Any]
    ) -> str:
        """Suggest entry type based on analysis."""
        try:
            # Rule-based type suggestion
            content_length = len(content)
            
            # Check for code
            if "```" in content or "def " in content or "function" in content:
                return EntryType.CODE.value
            
            # Check for FAQ
            if "faq" in title.lower() or "frequently asked" in content.lower():
                return EntryType.FAQ.value
            
            # Check for tutorial
            if "tutorial" in title.lower() or "step" in content.lower():
                return EntryType.TUTORIAL.value
            
            # Check for article
            if content_length > 1000:
                return EntryType.ARTICLE.value
            
            # Default to document
            return EntryType.DOCUMENT.value
            
        except Exception as e:
            logger.error(
                "Entry type suggestion failed",
                error=str(e)
            )
            return EntryType.DOCUMENT.value
    
    def _calculate_category_match(
        self,
        title: str,
        content: str,
        category: KnowledgeCategory,
        analysis: Dict[str, Any]
    ) -> float:
        """Calculate category match score."""
        score = 0.0
        
        # Title matching
        if category.name.lower() in title.lower():
            score += 0.4
        
        # Description matching
        if category.description and category.description.lower() in content.lower():
            score += 0.3
        
        # Topic matching
        if "topics" in analysis:
            for topic in analysis["topics"]:
                if topic["topic"].lower() == category.name.lower():
                    score += topic["relevance"] * 0.3
        
        return min(1.0, score)
    
    def _calculate_confidence_scores(self, analysis: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence scores for different analysis types."""
        scores = {}
        
        for analysis_type, result in analysis.items():
            if isinstance(result, dict) and "confidence" in result:
                scores[analysis_type] = result["confidence"]
            else:
                scores[analysis_type] = 0.8  # Default confidence
        
        return scores
    
    async def _analyze_trends(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Analyze trends in knowledge creation."""
        try:
            async with get_db_session() as session:
                # Get daily creation counts
                result = await session.execute(
                    select(
                        func.date(KnowledgeEntry.created_at).label('date'),
                        func.count(KnowledgeEntry.id).label('count')
                    ).where(
                        KnowledgeEntry.deleted_at.is_(None),
                        KnowledgeEntry.created_at >= period_start,
                        KnowledgeEntry.created_at <= period_end
                    ).group_by(
                        func.date(KnowledgeEntry.created_at)
                    ).order_by('date')
                )
                
                daily_counts = [(row[0].isoformat(), row[1]) for row in result.all()]
                
                # Calculate trend
                if len(daily_counts) >= 2:
                    first_week_avg = sum(count for _, count in daily_counts[:7]) / min(7, len(daily_counts))
                    last_week_avg = sum(count for _, count in daily_counts[-7:]) / min(7, len(daily_counts))
                    
                    trend = "increasing" if last_week_avg > first_week_avg * 1.1 else "decreasing" if last_week_avg < first_week_avg * 0.9 else "stable"
                else:
                    trend = "insufficient_data"
                
                return {
                    "daily_counts": daily_counts,
                    "trend": trend
                }
                
        except Exception as e:
            logger.error(
                "Trend analysis failed",
                error=str(e)
            )
            return {"trend": "error", "error": str(e)}
    
    async def _analyze_quality_metrics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Analyze quality metrics for knowledge entries."""
        try:
            async with get_db_session() as session:
                # Get average content length
                result = await session.execute(
                    select(func.avg(func.length(KnowledgeEntry.content))).where(
                        KnowledgeEntry.deleted_at.is_(None),
                        KnowledgeEntry.created_at >= period_start,
                        KnowledgeEntry.created_at <= period_end
                    )
                )
                avg_content_length = result.scalar() or 0
                
                # Get completion rate (entries with content vs total)
                result = await session.execute(
                    select(
                        func.count(KnowledgeEntry.id),
                        func.count(func.nullif(KnowledgeEntry.content == '', True))
                    ).where(
                        KnowledgeEntry.deleted_at.is_(None),
                        KnowledgeEntry.created_at >= period_start,
                        KnowledgeEntry.created_at <= period_end
                    )
                )
                total, with_content = result.first()
                
                completion_rate = (with_content / total) if total > 0 else 0
                
                return {
                    "average_content_length": avg_content_length,
                    "completion_rate": completion_rate,
                    "total_entries": total or 0,
                    "entries_with_content": with_content or 0
                }
                
        except Exception as e:
            logger.error(
                "Quality metrics analysis failed",
                error=str(e)
            )
            return {"error": str(e)}
    
    def _generate_analysis_cache_key(
        self,
        content: str,
        analysis_types: List[str]
    ) -> str:
        """Generate cache key for analysis results."""
        import hashlib
        
        key_data = f"{content}:{':'.join(sorted(analysis_types))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get analysis results from cache."""
        if key not in self.analysis_cache:
            return None
        
        timestamp, results = self.analysis_cache[key]
        if datetime.utcnow() - timestamp > timedelta(seconds=self.cache_ttl):
            del self.analysis_cache[key]
            return None
        
        return results
    
    def _set_cache(self, key: str, results: Dict[str, Any]) -> None:
        """Set analysis results in cache."""
        self.analysis_cache[key] = (datetime.utcnow(), results)
        
        # Limit cache size
        if len(self.analysis_cache) > 500:
            # Remove oldest entries
            oldest_keys = sorted(
                self.analysis_cache.keys(),
                key=lambda k: self.analysis_cache[k][0]
            )[:100]
            
            for old_key in oldest_keys:
                del self.analysis_cache[old_key]
    
    async def _process_analysis_task(self, task: Dict[str, Any]) -> None:
        """Process an analysis task."""
        try:
            task_type = task["type"]
            
            if task_type == "analyze_content":
                await self.analyze_content(task["content"], task.get("analysis_types"))
            else:
                logger.warning(
                    "Unknown analysis task type",
                    task_type=task_type
                )
                
        except Exception as e:
            logger.error(
                "Analysis task processing failed",
                task=task,
                error=str(e)
            )
    
    def clear_cache(self) -> None:
        """Clear analysis cache."""
        self.analysis_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get analysis cache statistics."""
        return {
            "cache_size": len(self.analysis_cache),
            "cache_ttl": self.cache_ttl,
            "max_concurrent_analysis": self.max_concurrent_analysis,
            "ai_enabled": self.ai_enabled,
            "oldest_cache": min(
                (timestamp for timestamp, _ in self.analysis_cache.values()),
                default=None
            ) if self.analysis_cache else None
        }
