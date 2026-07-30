"""
BaseLayer Prompt Engine

Jinja2-based prompt template system with versioning,
validation, and built-in patterns.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, Template, TemplateError
from pydantic import BaseModel

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class PromptTemplate(BaseModel):
    """Prompt template metadata."""
    name: str
    version: str
    description: str
    category: str
    variables: List[str]
    built_in_patterns: List[str]
    created_at: str
    updated_at: str


class PromptEngine:
    """
    Jinja2-based prompt template system.
    
    Manages template versioning, variable validation,
    and provides built-in prompt patterns.
    """
    
    def __init__(
        self,
        templates_dir: str = "agents/prompts",
        cache_size: int = 100
    ) -> None:
        """Initialize prompt engine."""
        self.templates_dir: Path = Path(templates_dir)
        self.cache_size: int = cache_size
        
        # Jinja2 environment
        self.env: Environment = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        # Template registry
        self.templates: Dict[str, PromptTemplate] = {}
        self.template_cache: Dict[str, Template] = {}
        
        # Built-in patterns
        self.patterns: Dict[str, str] = {
            "system_message": "You are {persona}. {role_description}",
            "few_shot": "Here are some examples:\n{examples}\n\nNow, {task}:",
            "chain_of_thought": "Think step by step to solve this problem.\n\n{problem}\n\nStep-by-step reasoning:",
            "json_output": "Respond with a valid JSON object only. No explanations.\n\n{prompt}\n\nJSON response:",
            "error_correction": "The previous response was invalid. Error: {error}\n\nPlease fix the response.\n\nOriginal request: {original_request}\n\nCorrected response:"
        }
        
        # Load templates
        self._load_templates()
        
        logger.info(
            "Prompt engine initialized",
            templates_dir=str(self.templates_dir),
            templates_loaded=len(self.templates)
        )
    
    def render(
        self,
        template_name: str,
        variables: Dict[str, Any],
        redact_sensitive: bool = True
    ) -> str:
        """
        Render a template with variables.
        
        Args:
            template_name: Name of template (with optional version)
            variables: Variables to inject
            redact_sensitive: Whether to redact sensitive variables in logs
            
        Returns:
            Rendered prompt string
        """
        # Parse template name and version
        name_parts = template_name.split("_v")
        name = name_parts[0]
        version = name_parts[1] if len(name_parts) > 1 else None
        
        # Get template
        template_key = f"{name}_v{version}" if version else name
        template = self._get_cached_template(template_key)
        
        if template is None:
            raise BaseLayerError(f"Template not found: {template_name}")
        
        # Validate variables
        self._validate_variables(template_key, variables)
        
        try:
            # Render template
            rendered = template.render(**variables)
            
            # Log with redaction
            log_variables = self._redact_variables(variables) if redact_sensitive else variables
            
            logger.debug(
                "Template rendered",
                template=template_key,
                variables=log_variables,
                length=len(rendered)
            )
            
            return rendered
            
        except TemplateError as e:
            logger.error(
                "Template rendering failed",
                template=template_key,
                error=str(e)
            )
            raise BaseLayerError(f"Template rendering failed: {str(e)}") from e
    
    def render_with_pattern(
        self,
        template_name: str,
        pattern_name: str,
        variables: Dict[str, Any],
        redact_sensitive: bool = True
    ) -> str:
        """
        Render template with built-in pattern.
        
        Args:
            template_name: Name of template
            pattern_name: Name of built-in pattern
            variables: Variables to inject
            
        Returns:
            Rendered prompt with pattern
        """
        if pattern_name not in self.patterns:
            raise BaseLayerError(f"Pattern not found: {pattern_name}")
        
        # Get pattern
        pattern = self.patterns[pattern_name]
        
        # Render template first
        template_content = self.render(template_name, variables, redact_sensitive)
        
        # Apply pattern
        pattern_variables = {
            "content": template_content,
            **variables
        }
        
        pattern_template = self.env.from_string(pattern)
        rendered = pattern_template.render(**pattern_variables)
        
        logger.debug(
            "Template rendered with pattern",
            template=template_name,
            pattern=pattern_name,
            length=len(rendered)
        )
        
        return rendered
    
    def list_templates(
        self,
        category: Optional[str] = None,
        version: Optional[str] = None
    ) -> List[PromptTemplate]:
        """
        List available templates.
        
        Args:
            category: Filter by category
            version: Filter by version
            
        Returns:
            List of template metadata
        """
        templates = list(self.templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if version:
            templates = [t for t in templates if t.version == version]
        
        return templates
    
    def get_template_info(self, template_name: str) -> Optional[PromptTemplate]:
        """
        Get template metadata.
        
        Args:
            template_name: Name of template
            
        Returns:
            Template metadata or None if not found
        """
        return self.templates.get(template_name)
    
    def validate_template(self, template_name: str) -> Dict[str, Any]:
        """
        Validate a template.
        
        Args:
            template_name: Name of template
            
        Returns:
            Validation result
        """
        template = self._get_cached_template(template_name)
        
        if template is None:
            return {
                "valid": False,
                "error": f"Template not found: {template_name}"
            }
        
        try:
            # Try to render with empty variables
            template.render()
            
            # Check for required variables
            template_info = self.get_template_info(template_name)
            
            return {
                "valid": True,
                "template": template_name,
                "required_variables": template_info.variables if template_info else [],
                "syntax_valid": True
            }
            
        except TemplateError as e:
            return {
                "valid": False,
                "template": template_name,
                "error": str(e),
                "syntax_valid": False
            }
    
    def create_system_message(
        self,
        persona: str,
        role_description: str,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Create a system message using built-in pattern.
        
        Args:
            persona: AI persona
            role_description: Role description
            additional_context: Additional context
            
        Returns:
            System message string
        """
        variables = {
            "persona": persona,
            "role_description": role_description
        }
        
        if additional_context:
            variables["additional_context"] = additional_context
        
        pattern = self.patterns["system_message"]
        template = self.env.from_string(pattern)
        
        return template.render(**variables)
    
    def create_few_shot(
        self,
        task: str,
        examples: List[Dict[str, str]],
        context: Optional[str] = None
    ) -> str:
        """
        Create few-shot prompt using built-in pattern.
        
        Args:
            task: Task description
            examples: List of examples with input/output
            context: Optional context
            
        Returns:
            Few-shot prompt string
        """
        # Format examples
        formatted_examples = []
        for i, example in enumerate(examples, 1):
            formatted_examples.append(
                f"Example {i}:\n"
                f"Input: {example.get('input', '')}\n"
                f"Output: {example.get('output', '')}"
            )
        
        examples_text = "\n\n".join(formatted_examples)
        
        variables = {
            "task": task,
            "examples": examples_text
        }
        
        if context:
            variables["context"] = context
        
        pattern = self.patterns["few_shot"]
        template = self.env.from_string(pattern)
        
        return template.render(**variables)
    
    def create_chain_of_thought(
        self,
        problem: str,
        context: Optional[str] = None
    ) -> str:
        """
        Create chain-of-thought prompt using built-in pattern.
        
        Args:
            problem: Problem to solve
            context: Optional context
            
        Returns:
            CoT prompt string
        """
        variables = {"problem": problem}
        
        if context:
            variables["context"] = context
        
        pattern = self.patterns["chain_of_thought"]
        template = self.env.from_string(pattern)
        
        return template.render(**variables)
    
    def create_json_output(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create JSON output prompt using built-in pattern.
        
        Args:
            prompt: Original prompt
            schema: Optional JSON schema
            
        Returns:
            JSON output prompt string
        """
        variables = {"prompt": prompt}
        
        if schema:
            variables["schema"] = json.dumps(schema, indent=2)
            # Use modified pattern with schema
            pattern = "Respond with a valid JSON object only. No explanations.\n\nSchema:\n{schema}\n\n{prompt}\n\nJSON response:"
        else:
            pattern = self.patterns["json_output"]
        
        template = self.env.from_string(pattern)
        
        return template.render(**variables)
    
    def create_error_correction(
        self,
        original_request: str,
        error: str,
        correction_hint: Optional[str] = None
    ) -> str:
        """
        Create error correction prompt using built-in pattern.
        
        Args:
            original_request: Original request
            error: Error message
            correction_hint: Optional correction hint
            
        Returns:
            Error correction prompt string
        """
        variables = {
            "original_request": original_request,
            "error": error
        }
        
        if correction_hint:
            variables["correction_hint"] = correction_hint
        
        pattern = self.patterns["error_correction"]
        template = self.env.from_string(pattern)
        
        return template.render(**variables)
    
    def _load_templates(self) -> None:
        """Load all templates from templates directory."""
        if not self.templates_dir.exists():
            logger.warning(
                "Templates directory not found",
                path=str(self.templates_dir)
            )
            return
        
        # Load template files
        for template_file in self.templates_dir.glob("*.j2"):
            try:
                self._load_template_file(template_file)
            except Exception as e:
                logger.error(
                    "Failed to load template file",
                    file=str(template_file),
                    error=str(e)
                )
    
    def _load_template_file(self, template_file: Path) -> None:
        """Load a single template file."""
        # Parse filename for name and version
        stem = template_file.stem
        
        if "_v" in stem:
            name_parts = stem.split("_v")
            name = name_parts[0]
            version = name_parts[1]
        else:
            name = stem
            version = "1"
        
        # Read template content
        content = template_file.read_text(encoding='utf-8')
        
        # Parse metadata from file header
        metadata = self._parse_template_metadata(content)
        
        # Extract variables from template
        template = self.env.from_string(content)
        variables = list(template.environment.parse(content).find_all(
            lambda node: hasattr(node, 'name')
        ))
        variable_names = [node.name for node in variables]
        
        # Create template metadata
        template_info = PromptTemplate(
            name=name,
            version=version,
            description=metadata.get("description", ""),
            category=metadata.get("category", "general"),
            variables=variable_names,
            built_in_patterns=metadata.get("built_in_patterns", []),
            created_at=metadata.get("created_at", ""),
            updated_at=metadata.get("updated_at", "")
        )
        
        # Store template
        template_key = f"{name}_v{version}"
        self.templates[template_key] = template_info
        
        logger.debug(
            "Template loaded",
            name=name,
            version=version,
            variables=len(variable_names)
        )
    
    def _parse_template_metadata(self, content: str) -> Dict[str, str]:
        """Parse metadata from template file header."""
        metadata = {}
        
        # Look for YAML frontmatter
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 2:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1])
                    metadata.update(frontmatter)
                except ImportError:
                    # yaml not available, skip parsing
                    pass
                except Exception as e:
                    logger.warning(
                        "Failed to parse template frontmatter",
                        error=str(e)
                    )
        
        return metadata
    
    def _get_cached_template(self, template_name: str) -> Optional[Template]:
        """Get template from cache or load from disk."""
        # Check cache
        if template_name in self.template_cache:
            return self.template_cache[template_name]
        
        # Load from disk
        try:
            template = self.env.get_template(f"{template_name}.j2")
            
            # Add to cache (with size limit)
            if len(self.template_cache) >= self.cache_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self.template_cache))
                del self.template_cache[oldest_key]
            
            self.template_cache[template_name] = template
            return template
            
        except Exception as e:
            logger.error(
                "Failed to load template",
                template=template_name,
                error=str(e)
            )
            return None
    
    def _validate_variables(
        self,
        template_name: str,
        variables: Dict[str, Any]
    ) -> None:
        """Validate that all required variables are provided."""
        template_info = self.get_template_info(template_name)
        
        if not template_info:
            return
        
        required_vars = set(template_info.variables)
        provided_vars = set(variables.keys())
        
        missing_vars = required_vars - provided_vars
        if missing_vars:
            raise BaseLayerError(
                f"Missing required variables for template {template_name}: {', '.join(missing_vars)}"
            )
    
    def _redact_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive variables for logging."""
        sensitive_keys = {
            'password', 'token', 'key', 'secret', 'api_key',
            'access_token', 'private_key', 'auth'
        }
        
        redacted = {}
        for key, value in variables.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        
        return redacted
    
    def clear_cache(self) -> None:
        """Clear template cache."""
        self.template_cache.clear()
        
        logger.info("Template cache cleared")
    
    def reload_templates(self) -> None:
        """Reload all templates from disk."""
        self.templates.clear()
        self.template_cache.clear()
        self._load_templates()
        
        logger.info("Templates reloaded")


# Global prompt engine instance
prompt_engine = PromptEngine()
