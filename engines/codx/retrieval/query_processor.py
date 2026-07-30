"""
CODX Query Processor

Query processing and understanding for CODX knowledge engine
with NLP and semantic analysis.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import asyncio
import re
from dataclasses import dataclass
from enum import Enum

from backend.shared.logger import get_logger
from backend.shared.errors import BaseLayerError

logger = get_logger(__name__)


class QueryType(str, Enum):
    """Query types."""
    FACTUAL = "factual"
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    RELATIONAL = "relational"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    EXPLORATORY = "exploratory"
    DEFINITIONAL = "definitional"
    CAUSAL = "causal"


class QueryIntent(str, Enum):
    """Query intents."""
    SEARCH = "search"
    COMPARE = "compare"
    EXPLAIN = "explain"
    DEFINE = "define"
    FIND_RELATIONSHIPS = "find_relationships"
    LIST = "list"
    FILTER = "filter"
    AGGREGATE = "aggregate"
    SUMMARIZE = "summarize"
    RECOMMEND = "recommend"
    NAVIGATE = "navigate"


@dataclass
class QueryEntity:
    """Query entity data class."""
    text: str
    type: str
    confidence: float
    start_pos: int
    end_pos: int
    normalized: Optional[str] = None
    synonyms: List[str] = None


@dataclass
class QueryRelationship:
    """Query relationship data class."""
    subject: str
    predicate: str
    object: str
    confidence: float
    relationship_type: str


@dataclass
class ProcessedQuery:
    """Processed query data class."""
    original_query: str
    normalized_query: str
    query_type: QueryType
    intent: QueryIntent
    entities: List[QueryEntity]
    relationships: List[QueryRelationship]
    keywords: List[str]
    concepts: List[str]
    filters: Dict[str, Any]
    constraints: Dict[str, Any]
    context: Dict[str, Any]
    confidence: float
    explanation: Optional[str] = None


class QueryProcessor:
    """
    Query processor for CODX knowledge engine.
    
    Provides advanced query processing with NLP,
    entity extraction, and semantic understanding.
    """
    
    def __init__(self, llm_client=None):
        """Initialize query processor."""
        self.llm_client = llm_client
        
        # Query processing configuration
        self.min_confidence = 0.5
        self.max_entities = 10
        self.max_relationships = 5
        
        # Performance metrics
        self.processing_stats = {
            "total_queries": 0,
            "successful_processings": 0,
            "failed_processings": 0,
            "average_processing_time_ms": 0,
            "average_entities_extracted": 0,
            "average_relationships_extracted": 0
        }
        
        # Query cache
        self.query_cache: Dict[str, ProcessedQuery] = {}
        self.cache_ttl = 1800  # 30 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        
        # NLP components
        self.stop_words = self._load_stop_words()
        self.entity_patterns = self._load_entity_patterns()
        self.relationship_patterns = self._load_relationship_patterns()
        
        logger.info(
            "Query processor initialized",
            llm_available=llm_client is not None,
            stop_words_count=len(self.stop_words)
        )
    
    async def process_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        use_llm: bool = False
    ) -> ProcessedQuery:
        """
        Process a knowledge query.
        
        Args:
            query: Query to process
            context: Query context
            use_cache: Whether to use cache
            use_llm: Whether to use LLM for processing
            
        Returns:
            Processed query object
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.processing_stats["total_queries"] += 1
            
            # Check cache first
            cache_key = self._generate_cache_key(query, context)
            if use_cache and self._is_cache_valid(cache_key):
                cached_query = self.query_cache[cache_key]
                
                logger.info(
                    "Query retrieved from cache",
                    query=query,
                    cache_key=cache_key
                )
                
                return cached_query
            
            # Normalize query
            normalized_query = self._normalize_query(query)
            
            # Determine query type and intent
            query_type = self._determine_query_type(normalized_query)
            intent = self._determine_query_intent(normalized_query)
            
            # Extract entities and relationships
            if use_llm and self.llm_client:
                entities, relationships = await self._extract_with_llm(normalized_query)
            else:
                entities = self._extract_entities(normalized_query)
                relationships = self._extract_relationships(normalized_query, entities)
            
            # Extract keywords and concepts
            keywords = self._extract_keywords(normalized_query)
            concepts = self._extract_concepts(normalized_query, entities)
            
            # Extract filters and constraints
            filters = self._extract_filters(normalized_query)
            constraints = self._extract_constraints(normalized_query)
            
            # Create processed query
            processed_query = ProcessedQuery(
                original_query=query,
                normalized_query=normalized_query,
                query_type=query_type,
                intent=intent,
                entities=entities,
                relationships=relationships,
                keywords=keywords,
                concepts=concepts,
                filters=filters,
                constraints=constraints,
                context=context or {},
                confidence=self._calculate_confidence(entities, relationships),
                explanation=self._generate_explanation(query, query_type, intent, entities, relationships)
            )
            
            # Update cache
            if use_cache:
                self._cache_query(cache_key, processed_query)
            
            # Update statistics
            processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            self.processing_stats["successful_processings"] += 1
            self.processing_stats["average_processing_time_ms"] = (
                (self.processing_stats["average_processing_time_ms"] * (self.processing_stats["successful_processings"] - 1) + processing_time) /
                self.processing_stats["successful_processings"]
            )
            self.processing_stats["average_entities_extracted"] = (
                (self.processing_stats["average_entities_extracted"] * (self.processing_stats["successful_processings"] - 1) + len(entities)) /
                self.processing_stats["successful_processings"]
            )
            self.processing_stats["average_relationships_extracted"] = (
                (self.processing_stats["average_relationships_extracted"] * (self.processing_stats["successful_processings"] - 1) + len(relationships)) /
                self.processing_stats["successful_processings"]
            )
            
            logger.info(
                "Query processed successfully",
                query=query,
                query_type=query_type,
                intent=intent,
                entities_count=len(entities),
                relationships_count=len(relationships),
                processing_time_ms=processing_time,
                confidence=processed_query.confidence
            )
            
            return processed_query
            
        except Exception as e:
            self.processing_stats["failed_processings"] += 1
            logger.error(
                "Query processing failed",
                error=str(e),
                query=query
            )
            raise BaseLayerError(f"Query processing failed: {str(e)}") from e
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query text."""
        # Convert to lowercase
        normalized = query.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove special characters (keep letters, numbers, spaces, basic punctuation)
        normalized = re.sub(r'[^\w\s\.\?\!\,\:\;\-\+]', ' ', normalized)
        
        # Normalize common abbreviations
        abbreviations = {
            'what is': 'what is',
            'how do': 'how do',
            'where can': 'where can',
            'why does': 'why does',
            'when did': 'when did',
            'who is': 'who is'
        }
        
        for abbr, full in abbreviations.items():
            normalized = normalized.replace(abbr, full)
        
        return normalized.strip()
    
    def _determine_query_type(self, query: str) -> QueryType:
        """Determine query type."""
        query_lower = query.lower()
        
        # Fact-based queries
        if any(word in query_lower for word in ['what', 'who', 'when', 'where', 'why', 'how']):
            return QueryType.FACTUAL
        
        # Concept-based queries
        if any(word in query_lower for word in ['concept', 'idea', 'theory', 'principle']):
            return QueryType.CONCEPTUAL
        
        # Procedural queries
        if any(word in query_lower for word in ['how to', 'step by step', 'process', 'procedure']):
            return QueryType.PROCEDURAL
        
        # Relational queries
        if any(word in query_lower for word in ['relationship', 'connection', 'relate', 'link']):
            return QueryType.RELATIONAL
        
        # Temporal queries
        if any(word in query_lower for word in ['when', 'time', 'date', 'period', 'duration']):
            return QueryType.TEMPORAL
        
        # Comparative queries
        if any(word in query_lower for word in ['compare', 'difference', 'versus', 'vs', 'better', 'worse']):
            return QueryType.COMPARATIVE
        
        # Exploratory queries
        if any(word in query_lower for word in ['explore', 'discover', 'find', 'search', 'look for']):
            return QueryType.EXPLORATORY
        
        # Definitional queries
        if any(word in query_lower for word in ['define', 'definition', 'meaning', 'what is']):
            return QueryType.DEFINITIONAL
        
        # Causal queries
        if any(word in query_lower for word in ['cause', 'effect', 'because', 'reason', 'lead to']):
            return QueryType.CAUSAL
        
        # Default to factual
        return QueryType.FACTUAL
    
    def _determine_query_intent(self, query: str) -> QueryIntent:
        """Determine query intent."""
        query_lower = query.lower()
        
        # Search intent
        if any(word in query_lower for word in ['find', 'search', 'look for', 'show me']):
            return QueryIntent.SEARCH
        
        # Compare intent
        if any(word in query_lower for word in ['compare', 'difference', 'versus', 'vs']):
            return QueryIntent.COMPARE
        
        # Explain intent
        if any(word in query_lower for word in ['explain', 'why', 'how does', 'what causes']):
            return QueryIntent.EXPLAIN
        
        # Define intent
        if any(word in query_lower for word in ['define', 'what is', 'meaning of']):
            return QueryIntent.DEFINE
        
        # Find relationships intent
        if any(word in query_lower for word in ['relationship', 'connected to', 'related to']):
            return QueryIntent.FIND_RELATIONSHIPS
        
        # List intent
        if any(word in query_lower for word in ['list', 'show all', 'enumerate']):
            return QueryIntent.LIST
        
        # Filter intent
        if any(word in query_lower for word in ['filter', 'only', 'with', 'that have']):
            return QueryIntent.FILTER
        
        # Aggregate intent
        if any(word in query_lower for word in ['count', 'sum', 'average', 'total', 'aggregate']):
            return QueryIntent.AGGREGATE
        
        # Summarize intent
        if any(word in query_lower for word in ['summarize', 'summary', 'overview', 'recap']):
            return QueryIntent.SUMMARIZE
        
        # Recommend intent
        if any(word in query_lower for word in ['recommend', 'suggest', 'best', 'top']):
            return QueryIntent.RECOMMEND
        
        # Navigate intent
        if any(word in query_lower for word in ['navigate', 'go to', 'path to', 'route']):
            return QueryIntent.NAVIGATE
        
        # Default to search
        return QueryIntent.SEARCH
    
    def _extract_entities(self, query: str) -> List[QueryEntity]:
        """Extract entities from query."""
        entities = []
        
        # Extract using patterns
        for pattern_name, pattern in self.entity_patterns.items():
            matches = re.finditer(pattern, query, re.IGNORECASE)
            
            for match in matches:
                entity_text = match.group(0)
                start_pos = match.start()
                end_pos = match.end()
                
                # Calculate confidence based on pattern strength
                confidence = self._calculate_entity_confidence(entity_text, pattern_name)
                
                if confidence >= self.min_confidence:
                    entity = QueryEntity(
                        text=entity_text,
                        type=pattern_name,
                        confidence=confidence,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        normalized=self._normalize_entity(entity_text),
                        synonyms=self._get_synonyms(entity_text)
                    )
                    entities.append(entity)
        
        # Remove duplicates and sort by confidence
        unique_entities = {}
        for entity in entities:
            key = (entity.text.lower(), entity.type)
            if key not in unique_entities or entity.confidence > unique_entities[key].confidence:
                unique_entities[key] = entity
        
        return sorted(unique_entities.values(), key=lambda x: x.confidence, reverse=True)[:self.max_entities]
    
    def _extract_relationships(self, query: str, entities: List[QueryEntity]) -> List[QueryRelationship]:
        """Extract relationships from query."""
        relationships = []
        
        # Extract using patterns
        for pattern_name, pattern in self.relationship_patterns.items():
            matches = re.finditer(pattern, query, re.IGNORECASE)
            
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    subject = groups[0].strip()
                    predicate = groups[1].strip() if len(groups) > 1 else ""
                    obj = groups[2].strip() if len(groups) > 2 else ""
                    
                    # Calculate confidence
                    confidence = self._calculate_relationship_confidence(subject, predicate, obj)
                    
                    if confidence >= self.min_confidence:
                        relationship = QueryRelationship(
                            subject=subject,
                            predicate=predicate,
                            object=obj,
                            confidence=confidence,
                            relationship_type=pattern_name
                        )
                        relationships.append(relationship)
        
        # Remove duplicates and sort by confidence
        unique_relationships = {}
        for rel in relationships:
            key = (rel.subject.lower(), rel.predicate.lower(), rel.object.lower())
            if key not in unique_relationships or rel.confidence > unique_relationships[key].confidence:
                unique_relationships[key] = rel
        
        return sorted(unique_relationships.values(), key=lambda x: x.confidence, reverse=True)[:self.max_relationships]
    
    async def _extract_with_llm(self, query: str) -> Tuple[List[QueryEntity], List[QueryRelationship]]:
        """Extract entities and relationships using LLM."""
        if not self.llm_client:
            return [], []
        
        try:
            # Create prompt for LLM
            prompt = f"""
            Extract entities and relationships from the following query:
            
            Query: "{query}"
            
            Please identify:
            1. Entities (nouns, proper nouns, concepts)
            2. Relationships between entities
            
            Format your response as JSON:
            {{
                "entities": [
                    {{"text": "entity text", "type": "entity type", "confidence": 0.9}}
                ],
                "relationships": [
                    {{"subject": "entity1", "predicate": "relationship", "object": "entity2", "confidence": 0.8}}
                ]
            }}
            """
            
            # Get LLM response
            response = await self.llm_client.generate_response(prompt)
            
            # Parse JSON response
            import json
            try:
                parsed = json.loads(response)
                
                entities = []
                for entity_data in parsed.get("entities", []):
                    entity = QueryEntity(
                        text=entity_data.get("text", ""),
                        type=entity_data.get("type", "unknown"),
                        confidence=entity_data.get("confidence", 0.5),
                        start_pos=0,
                        end_pos=len(entity_data.get("text", "")),
                        normalized=self._normalize_entity(entity_data.get("text", "")),
                        synonyms=[]
                    )
                    entities.append(entity)
                
                relationships = []
                for rel_data in parsed.get("relationships", []):
                    relationship = QueryRelationship(
                        subject=rel_data.get("subject", ""),
                        predicate=rel_data.get("predicate", ""),
                        object=rel_data.get("object", ""),
                        confidence=rel_data.get("confidence", 0.5),
                        relationship_type="extracted"
                    )
                    relationships.append(relationship)
                
                return entities, relationships
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON")
                return [], []
                
        except Exception as e:
            logger.error(
                "LLM extraction failed",
                error=str(e),
                query=query
            )
            return [], []
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query."""
        # Split into words
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Remove stop words
        keywords = [word for word in words if word not in self.stop_words and len(word) > 2]
        
        # Remove duplicates and return
        return list(set(keywords))
    
    def _extract_concepts(self, query: str, entities: List[QueryEntity]) -> List[str]:
        """Extract concepts from query."""
        concepts = []
        
        # Add entity types as concepts
        for entity in entities:
            if entity.type not in concepts:
                concepts.append(entity.type)
        
        # Extract noun phrases (simplified)
        noun_phrases = re.findall(r'\b(?:[a-z]+ ){0,2}[a-z]+\b', query.lower())
        
        for phrase in noun_phrases:
            if phrase not in concepts and len(phrase) > 3:
                concepts.append(phrase)
        
        return concepts[:10]  # Limit to top 10 concepts
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract filters from query."""
        filters = {}
        
        # Extract numeric filters
        numeric_matches = re.findall(r'(\w+)\s*(?:>|<|=|>=|<=)\s*(\d+(?:\.\d+)?)', query.lower())
        for match in numeric_matches:
            field, operator, value = match.groups()
            filters[field] = {
                "operator": operator,
                "value": float(value)
            }
        
        # Extract date filters
        date_matches = re.findall(r'(\w+)\s*(?:before|after|on|since)\s*(\d{4}-\d{2}-\d{2})', query.lower())
        for match in date_matches:
            field, relation, date = match.groups()
            filters[field] = {
                "date_relation": relation,
                "date": date
            }
        
        # Extract type filters
        type_matches = re.findall(r'(?:type|kind|category)\s+(?:of\s+)?(\w+)', query.lower())
        for match in type_matches:
            filters["type"] = match[1]
        
        return filters
    
    def _extract_constraints(self, query: str) -> Dict[str, Any]:
        """Extract constraints from query."""
        constraints = {}
        
        # Extract limit constraints
        limit_matches = re.findall(r'(?:top|first|limit)\s+(\d+)', query.lower())
        if limit_matches:
            constraints["limit"] = int(limit_matches[0])
        
        # Extract sort constraints
        sort_matches = re.findall(r'(?:sort|order)\s+(?:by\s+)?(\w+)', query.lower())
        if sort_matches:
            constraints["sort"] = sort_matches[0]
        
        # Extract time constraints
        time_matches = re.findall(r'(?:within|last|past)\s+(\d+)\s+(day|week|month|year)s?', query.lower())
        if time_matches:
            constraints["time_range"] = {
                "value": int(time_matches[0]),
                "unit": time_matches[1]
            }
        
        return constraints
    
    def _calculate_confidence(self, entities: List[QueryEntity], relationships: List[QueryRelationship]) -> float:
        """Calculate overall confidence score."""
        if not entities and not relationships:
            return 0.0
        
        entity_confidence = sum(e.confidence for e in entities) / len(entities) if entities else 0.0
        relationship_confidence = sum(r.confidence for r in relationships) / len(relationships) if relationships else 0.0
        
        # Weight entities more heavily
        overall_confidence = (entity_confidence * 0.7) + (relationship_confidence * 0.3)
        
        return min(overall_confidence, 1.0)
    
    def _calculate_entity_confidence(self, entity_text: str, pattern_type: str) -> float:
        """Calculate confidence score for entity."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence based on pattern type
        pattern_weights = {
            "proper_noun": 0.9,
            "noun_phrase": 0.8,
            "acronym": 0.7,
            "technical_term": 0.8,
            "person": 0.9,
            "organization": 0.8,
            "location": 0.8
        }
        
        confidence = pattern_weights.get(pattern_type, 0.5)
        
        # Boost based on entity characteristics
        if len(entity_text) > 5:
            confidence += 0.1
        
        if entity_text[0].isupper():
            confidence += 0.1
        
        if any(char.isdigit() for char in entity_text):
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _calculate_relationship_confidence(self, subject: str, predicate: str, obj: str) -> float:
        """Calculate confidence score for relationship."""
        confidence = 0.5  # Base confidence
        
        # Boost based on predicate strength
        strong_predicates = ['is', 'has', 'contains', 'includes', 'relates to', 'connects to']
        if predicate.lower() in strong_predicates:
            confidence += 0.2
        
        # Boost based on entity specificity
        if len(subject) > 3 and len(obj) > 3:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _normalize_entity(self, entity_text: str) -> str:
        """Normalize entity text."""
        # Convert to lowercase and strip
        normalized = entity_text.lower().strip()
        
        # Remove common prefixes/suffixes
        prefixes = ['the ', 'a ', 'an ', 'my ', 'our ', 'their ']
        suffixes = ['\'s', 's']
        
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        return normalized.strip()
    
    def _get_synonyms(self, entity_text: str) -> List[str]:
        """Get synonyms for entity."""
        # Simplified synonym mapping
        synonym_map = {
            'ai': ['artificial intelligence', 'machine learning', 'ml'],
            'database': ['db', 'data store', 'repository'],
            'api': ['application programming interface', 'interface'],
            'ui': ['user interface', 'interface', 'frontend'],
            'backend': ['server', 'server-side'],
            'frontend': ['client', 'client-side', 'ui'],
            'function': ['method', 'procedure', 'routine'],
            'class': ['type', 'object type'],
            'variable': ['var', 'parameter', 'argument'],
            'algorithm': ['algo', 'method', 'procedure']
        }
        
        normalized = entity_text.lower()
        return synonym_map.get(normalized, [])
    
    def _generate_explanation(
        self,
        query: str,
        query_type: QueryType,
        intent: QueryIntent,
        entities: List[QueryEntity],
        relationships: List[QueryRelationship]
    ) -> str:
        """Generate explanation for processed query."""
        explanation_parts = []
        
        explanation_parts.append(f"Query type: {query_type}")
        explanation_parts.append(f"Intent: {intent}")
        
        if entities:
            explanation_parts.append(f"Found {len(entities)} entities")
        
        if relationships:
            explanation_parts.append(f"Found {len(relationships)} relationships")
        
        return " | ".join(explanation_parts)
    
    def _generate_cache_key(self, query: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for query."""
        import hashlib
        key_data = {
            "query": query,
            "context": context or {}
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_json.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.query_cache:
            return False
        
        if cache_key not in self.cache_timestamps:
            return False
        
        age_seconds = (datetime.now(timezone.utc) - self.cache_timestamps[cache_key]).total_seconds()
        return age_seconds < self.cache_ttl
    
    def _cache_query(self, cache_key: str, processed_query: ProcessedQuery) -> None:
        """Cache processed query."""
        self.query_cache[cache_key] = processed_query
        self.cache_timestamps[cache_key] = datetime.now(timezone.utc)
        
        # Cleanup old cache entries
        self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Clean up old cache entries."""
        current_time = datetime.now(timezone.utc)
        keys_to_remove = []
        
        for cache_key, timestamp in self.cache_timestamps.items():
            age_seconds = (current_time - timestamp).total_seconds()
            if age_seconds > self.cache_ttl:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            if key in self.query_cache:
                del self.query_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
    
    def _load_stop_words(self) -> Set[str]:
        """Load stop words list."""
        return {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that',
            'the', 'to', 'was', 'will', 'with', 'the', 'this', 'but',
            'they', 'have', 'had', 'what', 'when', 'where', 'who',
            'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'nor', 'not',
            'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'can', 'will', 'just', 'should', 'now'
        }
    
    def _load_entity_patterns(self) -> Dict[str, str]:
        """Load entity extraction patterns."""
        return {
            "proper_noun": r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
            "noun_phrase": r'\b(?:[a-z]+ ){1,3}[a-z]+\b',
            "acronym": r'\b[A-Z]{2,}\b',
            "technical_term": r'\b[a-z]+(?:_[a-z]+)+\b',
            "person": r'\b[A-Z][a-z]+\s+(?:[A-Z][a-z]+\s+)*[A-Z][a-z]+\b',
            "organization": r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
            "location": r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        }
    
    def _load_relationship_patterns(self) -> Dict[str, str]:
        """Load relationship extraction patterns."""
        return {
            "is_a": r'(\w+)\s+is\s+(?:a\s+)?(\w+)',
            "has_a": r'(\w+)\s+has\s+(?:a\s+)?(\w+)',
            "relates_to": r'(\w+)\s+(?:relate[s]?|connect[s]?)\s+to\s+(\w+)',
            "part_of": r'(\w+)\s+(?:is\s+)?(?:a\s+)?part\s+of\s+(\w+)',
            "contains": r'(\w+)\s+contain[s]?\s+(\w+)',
            "similar_to": r'(\w+)\s+(?:is\s+)?similar\s+to\s+(\w+)'
        }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "total_queries": self.processing_stats["total_queries"],
            "successful_processings": self.processing_stats["successful_processings"],
            "failed_processings": self.processing_stats["failed_processings"],
            "success_rate": (
                self.processing_stats["successful_processings"] / self.processing_stats["total_queries"]
                if self.processing_stats["total_queries"] > 0 else 0.0
            ),
            "average_processing_time_ms": self.processing_stats["average_processing_time_ms"],
            "average_entities_extracted": self.processing_stats["average_entities_extracted"],
            "average_relationships_extracted": self.processing_stats["average_relationships_extracted"],
            "cache_size": len(self.query_cache)
        }
    
    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self.processing_stats = {
            "total_queries": 0,
            "successful_processings": 0,
            "failed_processings": 0,
            "average_processing_time_ms": 0,
            "average_entities_extracted": 0,
            "average_relationships_extracted": 0
        }
    
    def clear_cache(self) -> None:
        """Clear query cache."""
        self.query_cache.clear()
        self.cache_timestamps.clear()
        
        logger.info("Query processor cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on query processor."""
        try:
            # Test basic processing
            test_query = "What is artificial intelligence?"
            test_result = await self.process_query(
                query=test_query,
                use_cache=False,
                use_llm=False
            )
            
            health_status = {
                "status": "healthy",
                "processing_working": True,
                "test_query_processed": test_result.original_query == test_query,
                "test_entities_extracted": len(test_result.entities) > 0,
                "test_query_type_determined": test_result.query_type is not None,
                "test_intent_determined": test_result.intent is not None,
                "cache_size": len(self.query_cache),
                "stats": self.get_processing_stats(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                "Query processor health check completed",
                health_status=health_status
            )
            
            return health_status
            
        except Exception as e:
            logger.error(
                "Query processor health check failed",
                error=str(e)
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
