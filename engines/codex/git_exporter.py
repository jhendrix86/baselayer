"""
CODEX Git Exporter

Export knowledge entries to human-readable Markdown files
for Git tracking and version history.
"""

import os
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

from ..api.knowledge_manager import KnowledgeManager
from ..models.knowledge_entry import KnowledgeEntryType

logger = get_logger(__name__)


class GitExporter:
    """
    Export knowledge entries to Markdown files for Git tracking.
    
    Creates human-readable Markdown files with YAML frontmatter
    organized by entry type in ~/docs/codex/ directory.
    """
    
    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
        export_dir: Optional[str] = None
    ):
        """
        Initialize git exporter.
        
        Args:
            knowledge_manager: Knowledge manager instance
            export_dir: Directory for exports (defaults to ~/docs/codex/)
        """
        self.knowledge_manager = knowledge_manager
        
        # Set export directory
        if export_dir:
            self.export_dir = Path(export_dir)
        else:
            self.export_dir = Path.home() / "docs" / "codex"
        
        # Create export directory if it doesn't exist
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("GitExporter initialized", export_dir=str(self.export_dir))
    
    async def export_all_entries(self, include_archived: bool = False) -> Dict[str, Any]:
        """
        Export all knowledge entries to Markdown files.
        
        Args:
            include_archived: Whether to include archived entries
            
        Returns:
            Export results
        """
        try:
            logger.info("Starting full knowledge export")
            
            # Get all entries by type
            export_results = {}
            total_exported = 0
            
            for entry_type in KnowledgeEntryType:
                type_dir = self.export_dir / entry_type.value
                type_dir.mkdir(exist_ok=True)
                
                # Get entries of this type
                entries = await self._get_entries_by_type(entry_type, include_archived)
                
                # Export each entry
                exported_count = 0
                for entry in entries:
                    try:
                        await self._export_entry_to_markdown(entry, type_dir)
                        exported_count += 1
                    except Exception as e:
                        logger.error("Failed to export entry", 
                                   entry_id=str(entry.id),
                                   error=str(e))
                
                export_results[entry_type.value] = {
                    "entries_found": len(entries),
                    "entries_exported": exported_count,
                    "directory": str(type_dir)
                }
                total_exported += exported_count
            
            # Create index file
            await self._create_index_file(export_results)
            
            results = {
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_entries_exported": total_exported,
                "export_directory": str(self.export_dir),
                "results_by_type": export_results,
                "include_archived": include_archived
            }
            
            logger.info("Knowledge export completed", 
                       total_exported=total_exported,
                       export_dir=str(self.export_dir))
            
            return results
            
        except Exception as e:
            logger.error("Failed to export knowledge entries", error=str(e))
            raise BaseLayerError(f"Failed to export knowledge entries: {e}")
    
    async def export_by_type(
        self, 
        entry_type: KnowledgeEntryType, 
        include_archived: bool = False
    ) -> Dict[str, Any]:
        """
        Export entries of a specific type.
        
        Args:
            entry_type: Type of entries to export
            include_archived: Whether to include archived entries
            
        Returns:
            Export results
        """
        try:
            logger.info("Exporting entries by type", entry_type=entry_type.value)
            
            # Create type directory
            type_dir = self.export_dir / entry_type.value
            type_dir.mkdir(exist_ok=True)
            
            # Get entries
            entries = await self._get_entries_by_type(entry_type, include_archived)
            
            # Export entries
            exported_count = 0
            for entry in entries:
                try:
                    await self._export_entry_to_markdown(entry, type_dir)
                    exported_count += 1
                except Exception as e:
                    logger.error("Failed to export entry", 
                               entry_id=str(entry.id),
                               error=str(e))
            
            results = {
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "entry_type": entry_type.value,
                "entries_found": len(entries),
                "entries_exported": exported_count,
                "export_directory": str(type_dir)
            }
            
            logger.info("Type export completed", 
                       entry_type=entry_type.value,
                       exported=exported_count)
            
            return results
            
        except Exception as e:
            logger.error("Failed to export entries by type", 
                        entry_type=entry_type.value,
                        error=str(e))
            raise BaseLayerError(f"Failed to export entries by type: {e}")
    
    async def export_single_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Export a single knowledge entry.
        
        Args:
            entry_id: UUID of the entry to export
            
        Returns:
            Export result
        """
        try:
            logger.info("Exporting single entry", entry_id=entry_id)
            
            # Get entry
            entry = await self._get_entry_by_id(entry_id)
            if not entry:
                raise BaseLayerError(f"Entry not found: {entry_id}")
            
            # Create type directory
            type_dir = self.export_dir / entry.entry_type
            type_dir.mkdir(exist_ok=True)
            
            # Export entry
            await self._export_entry_to_markdown(entry, type_dir)
            
            result = {
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "entry_id": entry_id,
                "entry_key": entry.key,
                "entry_type": entry.entry_type,
                "export_file": str(type_dir / f"{entry.key}.md")
            }
            
            logger.info("Single entry export completed", 
                       entry_id=entry_id,
                       file=result["export_file"])
            
            return result
            
        except Exception as e:
            logger.error("Failed to export single entry", 
                        entry_id=entry_id,
                        error=str(e))
            raise BaseLayerError(f"Failed to export single entry: {e}")
    
    async def clean_exports(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up export directory.
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            Cleanup results
        """
        try:
            logger.info("Cleaning export directory", dry_run=dry_run)
            
            cleaned_files = []
            cleaned_dirs = []
            
            # Walk through export directory
            for item in self.export_dir.rglob("*"):
                if item.is_file():
                    # Check if file is a valid export
                    if item.suffix == ".md":
                        try:
                            # Try to parse frontmatter
                            with open(item, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if not content.startswith("---"):
                                    # Invalid export file
                                    if not dry_run:
                                        item.unlink()
                                    cleaned_files.append(str(item))
                        except Exception:
                            # Invalid file
                            if not dry_run:
                                item.unlink()
                            cleaned_files.append(str(item))
                    
                    # Remove non-Markdown files
                    elif item.suffix != ".md":
                        if not dry_run:
                            item.unlink()
                        cleaned_files.append(str(item))
                
                elif item.is_dir() and item != self.export_dir:
                    # Remove empty directories
                    try:
                        if not any(item.iterdir()):
                            if not dry_run:
                                item.rmdir()
                            cleaned_dirs.append(str(item))
                    except Exception:
                        pass
            
            results = {
                "cleanup_timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
                "files_cleaned": len(cleaned_files),
                "directories_cleaned": len(cleaned_dirs),
                "cleaned_files": cleaned_files,
                "cleaned_directories": cleaned_dirs
            }
            
            logger.info("Export directory cleanup completed", 
                       files_cleaned=len(cleaned_files),
                       dry_run=dry_run)
            
            return results
            
        except Exception as e:
            logger.error("Failed to clean export directory", error=str(e))
            raise BaseLayerError(f"Failed to clean export directory: {e}")
    
    async def get_export_stats(self) -> Dict[str, Any]:
        """
        Get statistics about exported files.
        
        Returns:
            Export statistics
        """
        try:
            logger.info("Getting export statistics")
            
            stats = {
                "export_directory": str(self.export_dir),
                "directory_exists": self.export_dir.exists(),
                "total_files": 0,
                "files_by_type": {},
                "total_size_bytes": 0,
                "last_export": None
            }
            
            if not self.export_dir.exists():
                return stats
            
            # Count files by type
            for entry_type in KnowledgeEntryType:
                type_dir = self.export_dir / entry_type.value
                if type_dir.exists():
                    md_files = list(type_dir.glob("*.md"))
                    stats["files_by_type"][entry_type.value] = len(md_files)
                    stats["total_files"] += len(md_files)
                    
                    # Calculate size
                    for file in md_files:
                        stats["total_size_bytes"] += file.stat().st_size
            
            # Find last export time
            index_file = self.export_dir / "index.md"
            if index_file.exists():
                stats["last_export"] = datetime.fromtimestamp(
                    index_file.stat().st_mtime, 
                    timezone.utc
                ).isoformat()
            
            logger.info("Export statistics retrieved", 
                       total_files=stats["total_files"],
                       total_size_mb=stats["total_size_bytes"] / (1024 * 1024))
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get export statistics", error=str(e))
            return {"error": str(e)}
    
    async def _get_entries_by_type(
        self, 
        entry_type: KnowledgeEntryType, 
        include_archived: bool = False
    ) -> List[Any]:
        """Get entries of a specific type."""
        try:
            # This would use the knowledge manager to get entries
            # For now, return empty list as placeholder
            logger.warning("Entry retrieval not implemented in git exporter")
            return []
            
        except Exception as e:
            logger.error("Failed to get entries by type", error=str(e))
            return []
    
    async def _get_entry_by_id(self, entry_id: str) -> Optional[Any]:
        """Get a specific entry by ID."""
        try:
            # This would use the knowledge manager to get entry
            # For now, return None as placeholder
            logger.warning("Entry retrieval not implemented in git exporter")
            return None
            
        except Exception as e:
            logger.error("Failed to get entry by ID", error=str(e))
            return None
    
    async def _export_entry_to_markdown(self, entry: Any, type_dir: Path) -> None:
        """Export a single entry to Markdown file."""
        try:
            # Create filename from key (sanitize)
            filename = self._sanitize_filename(entry.key) + ".md"
            file_path = type_dir / filename
            
            # Create frontmatter
            frontmatter = {
                "key": entry.key,
                "entry_type": entry.entry_type,
                "source_engine": entry.source_engine,
                "source_agent": entry.source_agent,
                "confidence": entry.confidence,
                "tags": entry.tags,
                "access_count": entry.access_count,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                "last_accessed_at": entry.last_accessed_at.isoformat() if entry.last_accessed_at else None,
                "is_archived": entry.is_archived,
                "exported_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Write Markdown file
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write frontmatter
                f.write("---\n")
                yaml.dump(frontmatter, f, default_flow_style=False, sort_keys=False)
                f.write("---\n\n")
                
                # Write content
                f.write(entry.value)
                f.write("\n")
            
            logger.debug("Entry exported to Markdown", 
                        entry_key=entry.key,
                        file_path=str(file_path))
            
        except Exception as e:
            logger.error("Failed to export entry to Markdown", 
                        entry_key=entry.key,
                        error=str(e))
            raise
    
    async def _create_index_file(self, export_results: Dict[str, Any]) -> None:
        """Create an index file with export summary."""
        try:
            index_path = self.export_dir / "index.md"
            
            # Build index content
            content = [
                "# CODEX Knowledge Export Index\n",
                f"Export generated: {datetime.now(timezone.utc).isoformat()}\n",
                f"Total entries exported: {sum(r['entries_exported'] for r in export_results.values())}\n",
                f"Export directory: `{self.export_dir}`\n",
                "## Export Summary\n"
            ]
            
            for entry_type, results in export_results.items():
                content.append(f"### {entry_type.title()}\n")
                content.append(f"- Entries found: {results['entries_found']}\n")
                content.append(f"- Entries exported: {results['entries_exported']}\n")
                content.append(f"- Directory: `{results['directory']}`\n\n")
            
            # Write index file
            with open(index_path, 'w', encoding='utf-8') as f:
                f.writelines(content)
            
            logger.debug("Index file created", index_path=str(index_path))
            
        except Exception as e:
            logger.error("Failed to create index file", error=str(e))
            raise
    
    def _sanitize_filename(self, key: str) -> str:
        """Sanitize key for use as filename."""
        # Replace problematic characters
        sanitized = key.replace("/", "_")
        sanitized = sanitized.replace("\\", "_")
        sanitized = sanitized.replace(":", "_")
        sanitized = sanitized.replace("*", "_")
        sanitized = sanitized.replace("?", "_")
        sanitized = sanitized.replace('"', "_")
        sanitized = sanitized.replace("<", "_")
        sanitized = sanitized.replace(">", "_")
        sanitized = sanitized.replace("|", "_")
        
        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        
        return sanitized
