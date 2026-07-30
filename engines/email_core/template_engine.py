"""
EMAIL_CORE Template Engine

Jinja2-based email template rendering with responsive design,
CAN-SPAM compliance, and multi-format support.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from markupsafe import Markup

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class EmailTemplateEngine:
    """
    Jinja2-based email template engine.
    
    Renders responsive HTML emails with CAN-SPAM compliance,
    plain text fallbacks, and preview support.
    """
    
    def __init__(
        self,
        template_dir: str = "engines/email_core/templates",
        base_url: str = "https://example.com",
        company_name: str = "Kade Digital",
        company_address: str = "123 Business St, Suite 100, City, State 12345",
        support_email: str = "support@example.com"
    ) -> None:
        """Initialize email template engine."""
        self.template_dir = Path(template_dir)
        self.base_url = base_url
        self.company_name = company_name
        self.company_address = company_address
        self.support_email = support_email
        
        # Setup Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self._add_custom_filters()
        
        # Load templates
        self._load_templates()
        
        logger.info("EmailTemplateEngine initialized", template_dir=str(self.template_dir))
    
    def _add_custom_filters(self) -> None:
        """Add custom Jinja2 filters for email rendering."""
        
        def format_currency(value: float, currency: str = "USD") -> str:
            """Format currency values."""
            if currency == "USD":
                return f"${value:,.2f}"
            return f"{value:,.2f} {currency}"
        
        def format_date(date: datetime, format_str: str = "%B %d, %Y") -> str:
            """Format dates."""
            if isinstance(date, str):
                date = datetime.fromisoformat(date.replace('Z', '+00:00'))
            return date.strftime(format_str)
        
        def format_datetime(datetime_obj: datetime, format_str: str = "%B %d, %Y at %I:%M %p") -> str:
            """Format datetime objects."""
            if isinstance(datetime_obj, str):
                datetime_obj = datetime.fromisoformat(datetime_obj.replace('Z', '+00:00'))
            return datetime_obj.strftime(format_str)
        
        def mask_email(email: str) -> str:
            """Mask email for privacy."""
            if '@' not in email:
                return email
            
            local, domain = email.split('@', 1)
            if len(local) <= 2:
                masked = local[0] + '*' * (len(local) - 1)
            else:
                masked = local[0] + '*' * (len(local) - 2) + local[-1]
            
            return f"{masked}@{domain}"
        
        def truncate_words(text: str, length: int = 50) -> str:
            """Truncate text to specified word count."""
            words = text.split()
            if len(words) <= length:
                return text
            return ' '.join(words[:length]) + '...'
        
        def nl2br(text: str) -> str:
            """Convert newlines to <br> tags."""
            return Markup(text.replace('\n', '<br>\n'))
        
        def url_encode(text: str) -> str:
            """URL encode text."""
            import urllib.parse
            return urllib.parse.quote(text)
        
        # Register filters
        self.env.filters['currency'] = format_currency
        self.env.filters['date'] = format_date
        self.env.filters['datetime'] = format_datetime
        self.env.filters['mask_email'] = mask_email
        self.env.filters['truncate_words'] = truncate_words
        self.env.filters['nl2br'] = nl2br
        self.env.filters['url_encode'] = url_encode
    
    def _load_templates(self) -> None:
        """Load and validate email templates."""
        self.templates = {}
        
        if not self.template_dir.exists():
            logger.warning("Template directory not found", template_dir=str(self.template_dir))
            return
        
        for template_file in self.template_dir.glob("*.html"):
            template_name = template_file.stem
            try:
                template = self.env.get_template(template_file.name)
                self.templates[template_name] = template
                logger.debug("Template loaded", template=template_name)
            except Exception as e:
                logger.error("Failed to load template", template=template_name, error=str(e))
                raise BaseLayerError(f"Failed to load template {template_name}: {e}")
        
        logger.info("Templates loaded", count=len(self.templates))
    
    def render_email(
        self,
        template_name: str,
        context: Dict[str, Any],
        subscriber: Optional[Any] = None,
        preview_text: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Render email template with context.
        
        Args:
            template_name: Name of the template to render
            context: Template variables
            subscriber: Subscriber object for personalization
            preview_text: Custom preview text
            
        Returns:
            Dict with 'html', 'text', and 'subject' keys
        """
        try:
            # Prepare template context
            full_context = self._prepare_context(context, subscriber)
            
            # Render HTML
            html_content = self._render_html(template_name, full_context)
            
            # Generate plain text fallback
            text_content = self._generate_text_fallback(html_content)
            
            # Extract or generate subject
            subject = self._extract_subject(html_content, full_context)
            
            # Add preview text
            if preview_text:
                html_content = self._add_preview_text(html_content, preview_text)
            
            # Validate CAN-SPAM compliance
            self._validate_can_spam(html_content, text_content)
            
            result = {
                'html': html_content,
                'text': text_content,
                'subject': subject,
                'preview_text': preview_text
            }
            
            logger.info("Email rendered successfully", 
                        template=template_name, 
                        subscriber_email=subscriber.email if subscriber else None)
            
            return result
            
        except Exception as e:
            logger.error("Failed to render email", 
                        template=template_name, 
                        error=str(e))
            raise BaseLayerError(f"Failed to render email template {template_name}: {e}")
    
    def _prepare_context(self, context: Dict[str, Any], subscriber: Optional[Any] = None) -> Dict[str, Any]:
        """Prepare template context with global variables."""
        full_context = context.copy()
        
        # Add global variables
        full_context.update({
            'base_url': self.base_url,
            'company_name': self.company_name,
            'company_address': self.company_address,
            'support_email': self.support_email,
            'current_year': datetime.now().year,
            'current_date': datetime.now(timezone.utc),
            'render_timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Add subscriber data if available
        if subscriber:
            full_context.update({
                'subscriber': {
                    'id': str(subscriber.id),
                    'email': subscriber.email,
                    'first_name': subscriber.first_name,
                    'last_name': subscriber.last_name,
                    'full_name': subscriber.full_name,
                    'masked_email': subscriber.mask_email(subscriber.email),
                    'tags': subscriber.tags or [],
                    'timezone': subscriber.timezone,
                    'language': subscriber.language
                }
            })
        
        return full_context
    
    def _render_html(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render HTML template."""
        if template_name not in self.templates:
            raise BaseLayerError(f"Template not found: {template_name}")
        
        template = self.templates[template_name]
        return template.render(**context)
    
    def _generate_text_fallback(self, html_content: str) -> str:
        """Generate plain text fallback from HTML."""
        try:
            # Simple HTML to text conversion
            # For production, consider using a library like html2text
            import re
            
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', html_content)
            
            # Handle common HTML entities
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&quot;', '"')
            text = text.replace('&#39;', "'")
            
            # Clean up whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.warning("Failed to generate text fallback", error=str(e))
            return "Plain text version not available. Please view this email in an HTML-capable email client."
    
    def _extract_subject(self, html_content: str, context: Dict[str, Any]) -> str:
        """Extract subject from HTML or use context."""
        # Try to extract from title tag
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            subject = title_match.group(1).strip()
            if subject:
                return subject
        
        # Try to extract from h1 tag
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
        if h1_match:
            subject = h1_match.group(1).strip()
            if subject:
                return subject
        
        # Use context subject
        return context.get('subject', f"Email from {self.company_name}")
    
    def _add_preview_text(self, html_content: str, preview_text: str) -> str:
        """Add preview text to HTML."""
        # Insert preview text after opening head tag
        preview_html = f'<style type="text/css">.preview-text {{ display:none; }}</style>\n<div class="preview-text">{preview_text}</div>'
        
        if '<head>' in html_content:
            return html_content.replace('<head>', f'<head>\n{preview_html}')
        elif '<html>' in html_content:
            return html_content.replace('<html>', f'<html>\n<head>\n{preview_html}\n</head>')
        else:
            return f'{preview_html}\n{html_content}'
    
    def _validate_can_spam(self, html_content: str, text_content: str) -> None:
        """Validate CAN-SPAM compliance."""
        errors = []
        
        # Check for unsubscribe link
        if 'unsubscribe' not in html_content.lower() and 'unsubscribe' not in text_content.lower():
            errors.append("Missing unsubscribe link")
        
        # Check for physical address
        if not any(addr in html_content.lower() for addr in ['address', 'street', 'suite']):
            if not any(addr in text_content.lower() for addr in ['address', 'street', 'suite']):
                errors.append("Missing physical address")
        
        # Check for sender identification
        if self.company_name.lower() not in html_content.lower():
            if self.company_name.lower() not in text_content.lower():
                errors.append("Missing sender identification")
        
        if errors:
            error_msg = "CAN-SPAM compliance issues: " + ", ".join(errors)
            logger.warning(error_msg)
            # Note: In production, you might want to raise an exception here
            # For now, we'll just log the warning
    
    def preview_email(
        self,
        template_name: str,
        context: Dict[str, Any],
        subscriber: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Generate email preview for testing.
        
        Returns detailed preview information including
        rendered content and validation results.
        """
        try:
            # Render email
            rendered = self.render_email(template_name, context, subscriber)
            
            # Generate preview information
            preview = {
                'template_name': template_name,
                'rendered_at': datetime.now(timezone.utc).isoformat(),
                'subscriber_email': subscriber.email if subscriber else 'test@example.com',
                'subject': rendered['subject'],
                'preview_text': rendered['preview_text'],
                'html_content': rendered['html'],
                'text_content': rendered['text'],
                'word_count': len(rendered['text'].split()),
                'character_count': len(rendered['text']),
                'has_unsubscribe': 'unsubscribe' in rendered['html'].lower(),
                'has_address': any(addr in rendered['html'].lower() for addr in ['address', 'street', 'suite']),
                'has_sender_id': self.company_name.lower() in rendered['html'].lower(),
                'links': self._extract_links(rendered['html']),
                'images': self._extract_images(rendered['html']),
                'validation_errors': []
            }
            
            # Validate content
            validation_errors = self._validate_content(rendered['html'], rendered['text'])
            preview['validation_errors'] = validation_errors
            
            return preview
            
        except Exception as e:
            logger.error("Failed to generate email preview", template=template_name, error=str(e))
            raise BaseLayerError(f"Failed to generate email preview: {e}")
    
    def _extract_links(self, html_content: str) -> List[Dict[str, str]]:
        """Extract links from HTML content."""
        import re
        
        links = []
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        matches = re.findall(link_pattern, html_content, re.IGNORECASE | re.DOTALL)
        
        for url, text in matches:
            links.append({
                'url': url.strip(),
                'text': text.strip(),
                'is_unsubscribe': 'unsubscribe' in url.lower() or 'unsubscribe' in text.lower()
            })
        
        return links
    
    def _extract_images(self, html_content: str) -> List[Dict[str, str]]:
        """Extract images from HTML content."""
        import re
        
        images = []
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>'
        matches = re.findall(img_pattern, html_content, re.IGNORECASE)
        
        for src, alt in matches:
            images.append({
                'src': src.strip(),
                'alt': alt.strip(),
                'is_external': src.startswith('http')
            })
        
        return images
    
    def _validate_content(self, html_content: str, text_content: str) -> List[str]:
        """Validate email content for common issues."""
        errors = []
        
        # Check content length
        if len(text_content) < 50:
            errors.append("Email content is too short (minimum 50 characters)")
        
        if len(text_content) > 100000:
            errors.append("Email content is too long (maximum 100,000 characters)")
        
        # Check for placeholder text
        placeholders = [
            'lorem ipsum', 'placeholder text', 'sample content',
            'your content here', '[placeholder]', '{{', '}}'
        ]
        
        content_lower = text_content.lower()
        for placeholder in placeholders:
            if placeholder in content_lower:
                errors.append(f"Contains placeholder text: {placeholder}")
        
        # Check for spam triggers
        spam_triggers = [
            'click here!!!', 'free money!!!', 'act now!!!',
            'limited time!!!', 'urgent!!!', '!!!'
        ]
        
        for trigger in spam_triggers:
            if trigger in content_lower:
                errors.append(f"Contains potential spam trigger: {trigger}")
        
        # Check for required elements
        if not self.company_name.lower() in html_content.lower():
            errors.append("Missing company name")
        
        if 'unsubscribe' not in html_content.lower():
            errors.append("Missing unsubscribe link")
        
        return errors
    
    def get_template_list(self) -> List[str]:
        """Get list of available templates."""
        return list(self.templates.keys())
    
    def template_exists(self, template_name: str) -> bool:
        """Check if template exists."""
        return template_name in self.templates
    
    def reload_templates(self) -> None:
        """Reload all templates."""
        self._load_templates()
        logger.info("Templates reloaded")


# Global template engine instance
template_engine = EmailTemplateEngine()
