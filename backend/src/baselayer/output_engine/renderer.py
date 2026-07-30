"""
BaseLayer Output Renderer

Template rendering engine with support for multiple template engines
for the Output Engine subsystem.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from structlog import get_logger

from ..models.output_engine import OutputTemplate
from .exceptions import RenderingError, TemplateNotFoundError

logger = get_logger(__name__)


class OutputRenderer:
    """
    Template rendering engine.
    
    Supports multiple template engines (Jinja2, etc.) with
    caching, validation, and error handling.
    """
    
    def __init__(self):
        self.rendering_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: int = 600  # 10 minutes
        self.supported_engines = ["jinja2", "string", "simple"]
        self.default_engine = "jinja2"
        self.max_render_time: int = 30  # seconds
        self.max_template_size: int = 1024 * 1024  # 1MB
        
        # Rendering metrics
        self.rendering_metrics = {
            "total_renders": 0,
            "successful_renders": 0,
            "failed_renders": 0,
            "average_render_time": 0.0
        }
    
    async def render_template(
        self,
        template: OutputTemplate,
        data: Dict[str, Any],
        engine: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a template with data.
        
        Args:
            template: Template to render
            data: Data for rendering
            engine: Template engine to use
            options: Rendering options
            
        Returns:
            str: Rendered content
            
        Raises:
            RenderingError: If rendering fails
        """
        engine = engine or template.engine or self.default_engine
        
        if engine not in self.supported_engines:
            raise RenderingError(f"Unsupported rendering engine: {engine}")
        
        try:
            # Validate inputs
            await self._validate_rendering_inputs(template, data, engine)
            
            # Check cache
            cache_key = self._generate_cache_key(template, data, engine)
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result:
                return cached_result
            
            # Render template
            start_time = datetime.utcnow()
            
            if engine == "jinja2":
                rendered_content = await self._render_jinja2(template, data, options or {})
            elif engine == "string":
                rendered_content = await self._render_string(template, data, options or {})
            elif engine == "simple":
                rendered_content = await self._render_simple(template, data, options or {})
            else:
                raise RenderingError(f"Rendering engine not implemented: {engine}")
            
            render_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update metrics
            self._update_rendering_metrics(True, render_time)
            
            # Cache result
            self._set_cache(cache_key, rendered_content)
            
            logger.debug(
                "Template rendered successfully",
                template_id=str(template.id),
                engine=engine,
                render_time=render_time
            )
            
            return rendered_content
            
        except Exception as e:
            self._update_rendering_metrics(False, 0)
            
            logger.error(
                "Template rendering failed",
                template_id=str(template.id),
                engine=engine,
                error=str(e)
            )
            
            raise RenderingError(f"Failed to render template: {str(e)}") from e
    
    async def render_string_template(
        self,
        template_string: str,
        data: Dict[str, Any],
        engine: str = "jinja2",
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a template string directly.
        
        Args:
            template_string: Template string
            data: Data for rendering
            engine: Template engine to use
            options: Rendering options
            
        Returns:
            str: Rendered content
            
        Raises:
            RenderingError: If rendering fails
        """
        try:
            # Create temporary template object
            temp_template = OutputTemplate(
                id=uuid.uuid4(),
                name="temp_template",
                content=template_string,
                template_type="custom",
                engine=engine,
                variables=[]
            )
            
            return await self.render_template(temp_template, data, engine, options)
            
        except Exception as e:
            raise RenderingError(f"Failed to render string template: {str(e)}") from e
    
    async def validate_template(
        self,
        template: OutputTemplate,
        engine: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a template.
        
        Args:
            template: Template to validate
            engine: Template engine to use
            
        Returns:
            Dict[str, Any]: Validation results
        """
        engine = engine or template.engine or self.default_engine
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "variables": [],
            "engine": engine
        }
        
        try:
            # Validate template syntax
            if engine == "jinja2":
                from jinja2 import Environment, TemplateSyntaxError
                env = Environment()
                try:
                    env.parse(template.content)
                except TemplateSyntaxError as e:
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Syntax error: {str(e)}")
            
            # Extract variables
            variables = await self._extract_template_variables(template, engine)
            validation_result["variables"] = variables
            
            # Check template size
            if len(template.content) > self.max_template_size:
                validation_result["warnings"].append(f"Template size ({len(template.content)} bytes) exceeds recommended limit")
            
            # Check for potential security issues
            if engine == "jinja2":
                security_issues = await self._check_jinja2_security(template.content)
                validation_result["warnings"].extend(security_issues)
            
            return validation_result
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(str(e))
            
            return validation_result
    
    async def get_rendering_stats(self) -> Dict[str, Any]:
        """
        Get rendering statistics.
        
        Returns:
            Dict[str, Any]: Rendering statistics
        """
        return {
            "cache_size": len(self.rendering_cache),
            "cache_ttl": self.cache_ttl,
            "supported_engines": self.supported_engines,
            "default_engine": self.default_engine,
            "max_render_time": self.max_render_time,
            "max_template_size": self.max_template_size,
            "rendering_metrics": self.rendering_metrics
        }
    
    async def _render_jinja2(
        self,
        template: OutputTemplate,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> str:
        """Render template using Jinja2."""
        from jinja2 import Environment, Template, select_autoescape, TemplateRuntimeError
        
        try:
            # Setup Jinja2 environment
            env_options = {
                "autoescape": select_autoescape(['html', 'xml']),
                "trim_blocks": options.get("trim_blocks", True),
                "lstrip_blocks": options.get("lstrip_blocks", True),
                "keep_trailing_newline": options.get("keep_trailing_newline", True)
            }
            
            env = Environment(**env_options)
            
            # Create template
            jinja_template = env.from_string(template.content)
            
            # Add custom filters if provided
            if "filters" in options:
                for filter_name, filter_func in options["filters"].items():
                    env.filters[filter_name] = filter_func
            
            # Add custom globals if provided
            if "globals" in options:
                for global_name, global_value in options["globals"].items():
                    env.globals[global_name] = global_value
            
            # Render template with timeout
            rendered_content = await asyncio.wait_for(
                asyncio.to_thread(jinja_template.render, **data),
                timeout=self.max_render_time
            )
            
            return rendered_content
            
        except TemplateRuntimeError as e:
            raise RenderingError(f"Jinja2 runtime error: {str(e)}", rendering_engine="jinja2") from e
        except Exception as e:
            raise RenderingError(f"Jinja2 rendering failed: {str(e)}", rendering_engine="jinja2") from e
    
    async def _render_string(
        self,
        template: OutputTemplate,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> str:
        """Render template using Python string formatting."""
        try:
            # Simple string formatting
            content = template.content
            
            # Replace variables using string.Template
            from string import Template
            
            # Convert data dict to string.Template format
            template_obj = Template(content)
            rendered_content = template_obj.safe_substitute(data)
            
            return rendered_content
            
        except Exception as e:
            raise RenderingError(f"String rendering failed: {str(e)}", rendering_engine="string") from e
    
    async def _render_simple(
        self,
        template: OutputTemplate,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> str:
        """Render template using simple placeholder replacement."""
        try:
            content = template.content
            
            # Simple placeholder replacement
            for key, value in data.items():
                placeholder = f"{{{key}}}"
                if placeholder in content:
                    content = content.replace(placeholder, str(value))
            
            return content
            
        except Exception as e:
            raise RenderingError(f"Simple rendering failed: {str(e)}", rendering_engine="simple") from e
    
    async def _validate_rendering_inputs(
        self,
        template: OutputTemplate,
        data: Dict[str, Any],
        engine: str
    ) -> None:
        """Validate rendering inputs."""
        # Check template content
        if not template.content or not template.content.strip():
            raise RenderingError("Template content is empty")
        
        # Check template size
        if len(template.content) > self.max_template_size:
            raise RenderingError(f"Template too large: {len(template.content)} bytes")
        
        # Check data
        if not isinstance(data, dict):
            raise RenderingError("Data must be a dictionary")
        
        # Check for required variables
        if template.variables:
            missing_vars = []
            for var in template.variables:
                if var not in data:
                    missing_vars.append(var)
            
            if missing_vars:
                raise RenderingError(f"Missing required variables: {missing_vars}")
    
    async def _extract_template_variables(
        self,
        template: OutputTemplate,
        engine: str
    ) -> List[str]:
        """Extract variables from template."""
        try:
            if engine == "jinja2":
                from jinja2 import Environment, meta
                env = Environment()
                ast = env.parse(template.content)
                variables = meta.find_undeclared_variables(ast)
                return list(variables)
            elif engine == "string":
                from string import Template
                template_obj = Template(template.content)
                return list(template_obj.get_template().pattern.findall(r'\{(\w+)\}'))
            elif engine == "simple":
                # Simple regex for {{variable}} pattern
                import re
                variables = re.findall(r'\{\{(\w+)\}\}', template.content)
                return list(set(variables))
            else:
                return []
                
        except Exception as e:
            logger.warning(
                "Failed to extract template variables",
                engine=engine,
                error=str(e)
            )
            return []
    
    async def _check_jinja2_security(self, content: str) -> List[str]:
        """Check for potential Jinja2 security issues."""
        warnings = []
        
        # Check for potentially dangerous constructs
        dangerous_patterns = [
            r'\{\{.*config\}',  # Access to config
            r'\{\{.*request\}',  # Access to request
            r'\{\{.*env\}',  # Access to environment
            r'\{\{.*import.*\}',  # Import statements
            r'\{\{.*eval.*\}',  # Eval statements
            r'\{\{.*exec.*\}',  # Exec statements
        ]
        
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(f"Potentially dangerous construct detected: {pattern}")
        
        return warnings
    
    def _generate_cache_key(
        self,
        template: OutputTemplate,
        data: Dict[str, Any],
        engine: str
    ) -> str:
        """Generate cache key for rendering result."""
        import hashlib
        
        # Create a hash of template content, data keys, and engine
        key_data = f"{template.id}:{engine}:{sorted(data.keys())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get rendering result from cache."""
        if key not in self.rendering_cache:
            return None
        
        timestamp, result = self.rendering_cache[key]
        if datetime.utcnow() - timestamp > timedelta(seconds=self.cache_ttl):
            del self.rendering_cache[key]
            return None
        
        return result
    
    def _set_cache(self, key: str, result: str) -> None:
        """Set rendering result in cache."""
        self.rendering_cache[key] = (datetime.utcnow(), result)
        
        # Limit cache size
        if len(self.rendering_cache) > 1000:
            # Remove oldest entries
            oldest_keys = sorted(
                self.rendering_cache.keys(),
                key=lambda k: self.rendering_cache[k][0]
            )[:100]
            
            for old_key in oldest_keys:
                del self.rendering_cache[old_key]
    
    def _update_rendering_metrics(self, success: bool, render_time: float) -> None:
        """Update rendering metrics."""
        self.rendering_metrics["total_renders"] += 1
        
        if success:
            self.rendering_metrics["successful_renders"] += 1
        else:
            self.rendering_metrics["failed_renders"] += 1
        
        # Update average render time
        successful = self.rendering_metrics["successful_renders"]
        if successful > 0:
            current_avg = self.rendering_metrics["average_render_time"]
            self.rendering_metrics["average_render_time"] = (
                (current_avg * (successful - 1) + render_time) / successful
            )
    
    def clear_cache(self) -> None:
        """Clear rendering cache."""
        self.rendering_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self.rendering_cache),
            "cache_ttl": self.cache_ttl,
            "oldest_cache": min(
                (timestamp for timestamp, _ in self.rendering_cache.values()),
                default=None
            ) if self.rendering_cache else None
        }
