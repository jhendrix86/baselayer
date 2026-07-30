"""
BaseLayer Knowledge Extractor

Knowledge extraction from documents, web pages, and other sources
for the Codex/Memory subsystem.
"""

import asyncio
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import aiofiles
import aiohttp
from structlog import get_logger

from ..core.database import get_db_session
from ..models.codex import (
    KnowledgeEntry, KnowledgeCategory, KnowledgeTag,
    KnowledgeType, EntryType, KnowledgeStatus
)
from ..models.user import User
from .exceptions import ExtractionError, ValidationError

logger = get_logger(__name__)


class KnowledgeExtractor:
    """
    Knowledge extraction engine for various sources.
    
    Extracts knowledge from documents, web pages, and other sources
    with AI-powered content analysis and categorization.
    """
    
    def __init__(self):
        self.extraction_queue: asyncio.Queue = asyncio.Queue()
        self.extraction_active: bool = False
        self.max_concurrent_extractions: int = 2  # Optimized for i5-2400
        self.supported_formats = [
            "html", "text", "markdown", "json", "xml", "csv"
        ]
        self.max_content_size: int = 10 * 1024 * 1024  # 10MB
        self.ai_enabled: bool = True
    
    async def start_extraction_worker(self) -> None:
        """Start the background extraction worker."""
        if self.extraction_active:
            return
        
        self.extraction_active = True
        asyncio.create_task(self._extraction_worker_loop())
        
        logger.info("Knowledge extraction worker started")
    
    async def stop_extraction_worker(self) -> None:
        """Stop the extraction worker."""
        self.extraction_active = False
        logger.info("Knowledge extraction worker stopped")
    
    async def _extraction_worker_loop(self) -> None:
        """Main extraction worker loop."""
        while self.extraction_active:
            try:
                # Get next extraction task
                extraction_task = await asyncio.wait_for(
                    self.extraction_queue.get(),
                    timeout=60.0
                )
                await self._process_extraction_task(extraction_task)
                
            except asyncio.TimeoutError:
                # No extraction tasks, continue
                continue
            except Exception as e:
                logger.error(
                    "Extraction worker error",
                    error=str(e)
                )
                await asyncio.sleep(10)
    
    async def extract_from_url(
        self,
        url: str,
        category_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> KnowledgeEntry:
        """
        Extract knowledge from a web page.
        
        Args:
            url: URL to extract from
            category_id: Category ID for the entry
            tags: Tags for the entry
            created_by: User who created the entry
            
        Returns:
            KnowledgeEntry: Created knowledge entry
            
        Raises:
            ExtractionError: If extraction fails
        """
        extraction_task = {
            "type": "extract_from_url",
            "source": url,
            "source_type": "web_page",
            "category_id": category_id,
            "tags": tags or [],
            "created_by": created_by
        }
        
        # For immediate results, process synchronously
        return await self._extract_from_url_task(extraction_task)
    
    async def extract_from_document(
        self,
        file_path: str,
        file_type: str,
        category_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> KnowledgeEntry:
        """
        Extract knowledge from a document.
        
        Args:
            file_path: Path to document file
            file_type: Type of document
            category_id: Category ID for the entry
            tags: Tags for the entry
            created_by: User who created the entry
            
        Returns:
            KnowledgeEntry: Created knowledge entry
            
        Raises:
            ExtractionError: If extraction fails
        """
        extraction_task = {
            "type": "extract_from_document",
            "source": file_path,
            "source_type": "document",
            "file_type": file_type,
            "category_id": category_id,
            "tags": tags or [],
            "created_by": created_by
        }
        
        # For immediate results, process synchronously
        return await self._extract_from_document_task(extraction_task)
    
    async def extract_from_text(
        self,
        content: str,
        title: str,
        source: str,
        category_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[uuid.UUID] = None
    ) -> KnowledgeEntry:
        """
        Extract knowledge from raw text.
        
        Args:
            content: Raw text content
            title: Title for the entry
            source: Source description
            category_id: Category ID for the entry
            tags: Tags for the entry
            created_by: User who created the entry
            
        Returns:
            KnowledgeEntry: Created knowledge entry
            
        Raises:
            ExtractionError: If extraction fails
        """
        extraction_task = {
            "type": "extract_from_text",
            "source": source,
            "source_type": "text",
            "content": content,
            "title": title,
            "category_id": category_id,
            "tags": tags or [],
            "created_by": created_by
        }
        
        # For immediate results, process synchronously
        return await self._extract_from_text_task(extraction_task)
    
    async def _process_extraction_task(self, task: Dict[str, Any]) -> None:
        """
        Process an extraction task.
        
        Args:
            task: Extraction task to process
        """
        try:
            task_type = task["type"]
            
            if task_type == "extract_from_url":
                await self._extract_from_url_task(task)
            elif task_type == "extract_from_document":
                await self._extract_from_document_task(task)
            elif task_type == "extract_from_text":
                await self._extract_from_text_task(task)
            else:
                logger.warning(
                    "Unknown extraction task type",
                    task_type=task_type
                )
                
        except Exception as e:
            logger.error(
                "Extraction task processing failed",
                task=task,
                error=str(e)
            )
    
    async def _extract_from_url_task(self, task: Dict[str, Any]) -> KnowledgeEntry:
        """Extract knowledge from a web page."""
        url = task["source"]
        category_id = task.get("category_id")
        tags = task.get("tags", [])
        created_by = task.get("created_by")
        
        try:
            # Fetch web page content
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "BaseLayer Knowledge Extractor 1.0"
                }
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise ExtractionError(f"Failed to fetch URL: {url} (status: {response.status})")
                    
                    content = await response.text()
                    
                    # Check content size
                    if len(content) > self.max_content_size:
                        raise ExtractionError(f"Content too large: {len(content)} bytes")
            
            # Extract structured data
            extracted_data = await self._extract_html_content(content, url)
            
            # Create knowledge entry
            async with get_db_session() as db_session:
                entry = KnowledgeEntry(
                    title=extracted_data["title"],
                    content=extracted_data["content"],
                    entry_type=EntryType.DOCUMENT,
                    knowledge_type=KnowledgeType.PROCEDURE,
                    category_id=uuid.UUID(category_id) if category_id else None,
                    language=extracted_data.get("language", "en"),
                    access_level="public",
                    status=KnowledgeStatus.DRAFT,
                    version="1.0.0",
                    metadata={
                        "source": url,
                        "source_type": "web_page",
                        "extraction_date": datetime.utcnow().isoformat(),
                        "author": extracted_data.get("author"),
                        "publish_date": extracted_data.get("publish_date"),
                        "word_count": len(extracted_data["content"].split()),
                        "original_url": url
                    },
                    author=extracted_data.get("author"),
                    created_by=created_by
                )
                
                db_session.add(entry)
                await db_session.commit()
                await db_session.refresh(entry)
                
                # Add tags
                if tags:
                    await self._add_tags_to_entry(db_session, entry.id, tags)
                
                # Add extracted tags
                if extracted_data.get("tags"):
                    await self._add_tags_to_entry(db_session, entry.id, extracted_data["tags"])
                
                logger.info(
                    "Knowledge extracted from URL",
                    entry_id=str(entry.id),
                    url=url,
                    title=extracted_data["title"]
                )
                
                return entry
                
        except Exception as e:
            raise ExtractionError(f"Failed to extract from URL {url}: {str(e)}") from e
    
    async def _extract_from_document_task(self, task: Dict[str, Any]) -> KnowledgeEntry:
        """Extract knowledge from a document."""
        file_path = task["source"]
        file_type = task["file_type"]
        category_id = task.get("category_id")
        tags = task.get("tags", [])
        created_by = task.get("created_by")
        
        try:
            # Read file content
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
            
            # Check content size
            if len(content) > self.max_content_size:
                raise ExtractionError(f"File too large: {len(content)} bytes")
            
            # Extract based on file type
            if file_type.lower() == "markdown":
                extracted_data = await self._extract_markdown_content(content, file_path)
            elif file_type.lower() == "text":
                extracted_data = await self._extract_plain_text_content(content, file_path)
            elif file_type.lower() == "json":
                extracted_data = await self._extract_json_content(content, file_path)
            elif file_type.lower() == "csv":
                extracted_data = await self._extract_csv_content(content, file_path)
            else:
                extracted_data = await self._extract_plain_text_content(content, file_path)
            
            # Create knowledge entry
            async with get_db_session() as db_session:
                entry = KnowledgeEntry(
                    title=extracted_data["title"],
                    content=extracted_data["content"],
                    entry_type=EntryType.DOCUMENT,
                    knowledge_type=KnowledgeType.PROCEDURE,
                    category_id=uuid.UUID(category_id) if category_id else None,
                    language=extracted_data.get("language", "en"),
                    access_level="public",
                    status=KnowledgeStatus.DRAFT,
                    version="1.0.0",
                    metadata={
                        "source": file_path,
                        "source_type": "document",
                        "file_type": file_type,
                        "extraction_date": datetime.utcnow().isoformat(),
                        "word_count": len(extracted_data["content"].split()),
                        "original_filename": file_path.split("/")[-1]
                    },
                    author=extracted_data.get("author"),
                    created_by=created_by
                )
                
                db_session.add(entry)
                await db_session.commit()
                await db_session.refresh(entry)
                
                # Add tags
                if tags:
                    await self._add_tags_to_entry(db_session, entry.id, tags)
                
                # Add extracted tags
                if extracted_data.get("tags"):
                    await self._add_tags_to_entry(db_session, entry.id, extracted_data["tags"])
                
                logger.info(
                    "Knowledge extracted from document",
                    entry_id=str(entry.id),
                    file_path=file_path,
                    file_type=file_type,
                    title=extracted_data["title"]
                )
                
                return entry
                
        except Exception as e:
            raise ExtractionError(f"Failed to extract from document {file_path}: {str(e)}") from e
    
    async def _extract_from_text_task(self, task: Dict[str, Any]) -> KnowledgeEntry:
        """Extract knowledge from raw text."""
        content = task["content"]
        title = task["title"]
        source = task["source"]
        category_id = task.get("category_id")
        tags = task.get("tags", [])
        created_by = task.get("created_by")
        
        try:
            # Check content size
            if len(content) > self.max_content_size:
                raise ExtractionError(f"Content too large: {len(content)} bytes")
            
            # Extract structured data from text
            extracted_data = await self._extract_text_content(content, title)
            
            # Create knowledge entry
            async with get_db_session() as db_session:
                entry = KnowledgeEntry(
                    title=title,
                    content=extracted_data["content"],
                    entry_type=EntryType.DOCUMENT,
                    knowledge_type=KnowledgeType.PROCEDURE,
                    category_id=uuid.UUID(category_id) if category_id else None,
                    language=extracted_data.get("language", "en"),
                    access_level="public",
                    status=KnowledgeStatus.DRAFT,
                    version="1.0.0",
                    metadata={
                        "source": source,
                        "source_type": "text",
                        "extraction_date": datetime.utcnow().isoformat(),
                        "word_count": len(content.split()),
                        "original_length": len(content)
                    },
                    author=extracted_data.get("author"),
                    created_by=created_by
                )
                
                db_session.add(entry)
                await db_session.commit()
                await db_session.refresh(entry)
                
                # Add tags
                if tags:
                    await self._add_tags_to_entry(db_session, entry.id, tags)
                
                # Add extracted tags
                if extracted_data.get("tags"):
                    await self._add_tags_to_entry(db_session, entry.id, extracted_data["tags"])
                
                logger.info(
                    "Knowledge extracted from text",
                    entry_id=str(entry.id),
                    title=title,
                    source=source
                )
                
                return entry
                
        except Exception as e:
            raise ExtractionError(f"Failed to extract from text: {str(e)}") from e
    
    async def _extract_html_content(self, html_content: str, url: str) -> Dict[str, Any]:
        """Extract structured content from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract title
            title = ""
            if soup.title:
                title = soup.title.get_text().strip()
            
            # Extract main content
            content = ""
            
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                content = main_content.get_text(separator=' ', strip=True)
            else:
                # Fallback to body content
                if soup.body:
                    content = soup.body.get_text(separator=' ', strip=True)
            
            # Clean content
            content = self._clean_extracted_content(content)
            
            # Extract metadata
            author = self._extract_meta_tag(soup, 'author')
            publish_date = self._extract_meta_tag(soup, 'date')
            description = self._extract_meta_tag(soup, 'description')
            
            # Detect language
            language = self._detect_language(content)
            
            # Extract tags from keywords
            keywords = self._extract_meta_tag(soup, 'keywords')
            tags = []
            if keywords:
                tags = [tag.strip() for tag in keywords.split(',')]
            
            return {
                "title": title or "Untitled",
                "content": content,
                "author": author,
                "publish_date": publish_date,
                "description": description,
                "language": language,
                "tags": tags,
                "word_count": len(content.split())
            }
            
        except Exception as e:
            raise ExtractionError(f"HTML extraction failed: {str(e)}") from e
    
    async def _extract_markdown_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract structured content from Markdown."""
        try:
            lines = content.split('\n')
            
            # Extract title (first heading)
            title = ""
            for line in lines:
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            
            # Clean content
            clean_content = self._clean_extracted_content(content)
            
            # Extract metadata from front matter if present
            metadata = self._extract_frontmatter(content)
            
            return {
                "title": title or file_path.split('/')[-1],
                "content": clean_content,
                "author": metadata.get("author"),
                "language": metadata.get("language", "en"),
                "tags": metadata.get("tags", []),
                "word_count": len(clean_content.split())
            }
            
        except Exception as e:
            raise ExtractionError(f"Markdown extraction failed: {str(e)}") from e
    
    async def _extract_plain_text_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract structured content from plain text."""
        try:
            lines = content.split('\n')
            
            # Extract title (first non-empty line or filename)
            title = ""
            for line in lines:
                if line.strip():
                    title = line.strip()
                    break
            
            if not title:
                title = file_path.split('/')[-1]
            
            # Clean content
            clean_content = self._clean_extracted_content(content)
            
            # Detect language
            language = self._detect_language(clean_content)
            
            return {
                "title": title,
                "content": clean_content,
                "language": language,
                "tags": [],
                "word_count": len(clean_content.split())
            }
            
        except Exception as e:
            raise ExtractionError(f"Plain text extraction failed: {str(e)}") from e
    
    async def _extract_json_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract structured content from JSON."""
        try:
            import json
            
            data = json.loads(content)
            
            # Try to find title and content in JSON
            title = data.get('title') or data.get('name') or file_path.split('/')[-1]
            
            # Convert JSON to text content
            json_text = json.dumps(data, indent=2)
            
            # Clean content
            clean_content = self._clean_extracted_content(json_text)
            
            return {
                "title": str(title),
                "content": clean_content,
                "language": "en",
                "tags": [],
                "word_count": len(clean_content.split())
            }
            
        except Exception as e:
            raise ExtractionError(f"JSON extraction failed: {str(e)}") from e
    
    async def _extract_csv_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract structured content from CSV."""
        try:
            import csv
            import io
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            rows = list(csv_reader)
            
            if not rows:
                raise ExtractionError("CSV file is empty")
            
            # Convert CSV to text content
            csv_text = "\n".join([", ".join(row.values()) for row in rows])
            
            # Use filename as title
            title = file_path.split('/')[-1]
            
            # Clean content
            clean_content = self._clean_extracted_content(csv_text)
            
            return {
                "title": title,
                "content": clean_content,
                "language": "en",
                "tags": ["csv", "data"],
                "word_count": len(clean_content.split())
            }
            
        except Exception as e:
            raise ExtractionError(f"CSV extraction failed: {str(e)}") from e
    
    async def _extract_text_content(self, content: str, title: str) -> Dict[str, Any]:
        """Extract structured content from raw text."""
        # Clean content
        clean_content = self._clean_extracted_content(content)
        
        # Detect language
        language = self._detect_language(clean_content)
        
        # Extract potential tags from content
        tags = self._extract_tags_from_text(clean_content)
        
        return {
            "title": title,
            "content": clean_content,
            "language": language,
            "tags": tags,
            "word_count": len(clean_content.split())
        }
    
    def _clean_extracted_content(self, content: str) -> str:
        """Clean extracted content."""
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove special characters but keep basic punctuation
        content = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\"\'\/\\]', ' ', content)
        
        # Trim whitespace
        content = content.strip()
        
        return content
    
    def _extract_meta_tag(self, soup: BeautifulSoup, name: str) -> Optional[str]:
        """Extract meta tag content."""
        meta_tag = soup.find('meta', attrs={'name': name})
        if meta_tag:
            return meta_tag.get('content')
        
        # Try property attribute
        meta_tag = soup.find('meta', attrs={'property': f'og:{name}'})
        if meta_tag:
            return meta_tag.get('content')
        
        return None
    
    def _detect_language(self, content: str) -> str:
        """Detect language of content."""
        # Simple language detection based on common words
        # In real implementation, this would use a proper language detection library
        
        common_english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = content.lower().split()
        
        english_word_count = sum(1 for word in words if word in common_english_words)
        
        if english_word_count / len(words) > 0.05:  # 5% threshold
            return "en"
        
        return "en"  # Default to English
    
    def _extract_tags_from_text(self, content: str) -> List[str]:
        """Extract potential tags from text content."""
        # Simple tag extraction based on common patterns
        tags = []
        
        # Look for capitalized words (potential proper nouns)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', content)
        
        # Count occurrences
        word_counts = {}
        for word in capitalized_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Add words that appear multiple times
        for word, count in word_counts.items():
            if count >= 2 and len(word) > 2:
                tags.append(word.lower())
        
        return tags[:10]  # Limit to 10 tags
    
    def _extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from Markdown."""
        lines = content.split('\n')
        
        if not lines or not lines[0].startswith('---'):
            return {}
        
        # Find end of frontmatter
        end_index = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_index = i
                break
        
        if end_index is None:
            return {}
        
        # Parse frontmatter
        frontmatter_lines = lines[1:end_index]
        metadata = {}
        
        for line in frontmatter_lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Handle different value types
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]  # Remove quotes
                elif value.startswith('[') and value.endswith(']'):
                    value = value[1:-1].split(',')  # List
                    value = [v.strip().strip('"') for v in value]
                
                metadata[key] = value
        
        return metadata
    
    async def _add_tags_to_entry(
        self,
        session: AsyncSession,
        entry_id: uuid.UUID,
        tags: List[str]
    ) -> None:
        """Add tags to a knowledge entry."""
        for tag_name in tags:
            # Get or create tag
            result = await session.execute(
                select(KnowledgeTag).where(
                    KnowledgeTag.name == tag_name,
                    KnowledgeTag.deleted_at.is_(None)
                )
            )
            tag = result.scalar_one_or_none()
            
            if not tag:
                tag = KnowledgeTag(
                    name=tag_name,
                    description=f"Tag: {tag_name}",
                    color=self._generate_tag_color(tag_name)
                )
                session.add(tag)
                await session.flush()
            
            # Create entry-tag relationship
            # In real implementation, this would be a separate association table
            pass
    
    def _generate_tag_color(self, tag_name: str) -> str:
        """Generate a color for a tag based on its name."""
        colors = [
            "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
            "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16"
        ]
        
        # Simple hash-based color selection
        hash_value = hash(tag_name) % len(colors)
        return colors[hash_value]
    
    async def get_extraction_statistics(self) -> Dict[str, Any]:
        """
        Get extraction statistics.
        
        Returns:
            Dict[str, Any]: Extraction statistics
        """
        return {
            "supported_formats": self.supported_formats,
            "max_content_size": self.max_content_size,
            "queue_size": self.extraction_queue.qsize(),
            "extraction_active": self.extraction_active,
            "max_concurrent_extractions": self.max_concurrent_extractions,
            "ai_enabled": self.ai_enabled
        }
