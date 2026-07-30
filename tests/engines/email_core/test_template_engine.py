"""
EMAIL_CORE Template Engine Tests

Unit tests for email template engine functionality.
"""

import pytest
from datetime import datetime, timezone
from jinja2 import Template, TemplateSyntaxError

from ..template_engine import EmailTemplateEngine


@pytest.mark.unit
class TestEmailTemplateEngine:
    """Test email template engine functionality."""
    
    def test_template_engine_initialization(self):
        """Test template engine initialization."""
        engine = EmailTemplateEngine(base_url="https://test.example.com")
        
        assert engine.base_url == "https://test.example.com"
        assert engine.template_dir is not None
        assert engine.jinja_env is not None
    
    def test_template_engine_default_base_url(self):
        """Test template engine with default base URL."""
        engine = EmailTemplateEngine()
        assert engine.base_url == "https://app.example.com"
    
    async def test_render_simple_template(self, template_engine, sample_template_context):
        """Test rendering a simple template."""
        template_content = """
        <h1>Hello {{ subscriber.first_name }}!</h1>
        <p>Welcome to {{ company_name }}.</p>
        """
        
        rendered = await template_engine.render_template_content(
            template_content, sample_template_context
        )
        
        assert "Hello Test!" in rendered["html"]
        assert "Welcome to Test Company." in rendered["html"]
        assert "Hello Test!" in rendered["text"]
        assert "Welcome to Test Company." in rendered["text"]
    
    async def test_render_template_with_conditionals(self, template_engine, sample_template_context):
        """Test rendering template with conditional logic."""
        template_content = """
        {% if subscriber.first_name %}
        <p>Hello {{ subscriber.first_name }}!</p>
        {% else %}
        <p>Hello!</p>
        {% endif %}
        """
        
        rendered = await template_engine.render_template_content(
            template_content, sample_template_context
        )
        
        assert "Hello Test!" in rendered["html"]
        assert "Hello Test!" in rendered["text"]
        
        # Test with missing first name
        context_no_name = sample_template_context.copy()
        context_no_name["subscriber"]["first_name"] = None
        
        rendered_no_name = await template_engine.render_template_content(
            template_content, context_no_name
        )
        
        assert "<p>Hello!</p>" in rendered_no_name["html"]
    
    async def test_render_template_with_loops(self, template_engine, sample_template_context):
        """Test rendering template with loops."""
        context_with_list = sample_template_context.copy()
        context_with_list["items"] = ["Item 1", "Item 2", "Item 3"]
        
        template_content = """
        <ul>
        {% for item in items %}
        <li>{{ item }}</li>
        {% endfor %}
        </ul>
        """
        
        rendered = await template_engine.render_template_content(
            template_content, context_with_list
        )
        
        assert "<li>Item 1</li>" in rendered["html"]
        assert "<li>Item 2</li>" in rendered["html"]
        assert "<li>Item 3</li>" in rendered["html"]
    
    async def test_render_template_with_filters(self, template_engine, sample_template_context):
        """Test rendering template with custom filters."""
        template_content = """
        <p>Date: {{ current_date|date_filter }}</p>
        <p>Email: {{ subscriber.email|mask_email }}</p>
        """
        
        rendered = await template_engine.render_template_content(
            template_content, sample_template_context
        )
        
        assert "Date:" in rendered["html"]
        assert "t***@example.com" in rendered["html"]
    
    async def test_html_to_text_conversion(self, template_engine):
        """Test HTML to text conversion."""
        html_content = """
        <h1>Title</h1>
        <p>Paragraph with <strong>bold</strong> text.</p>
        <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        </ul>
        """
        
        text = template_engine._html_to_text(html_content)
        
        assert "Title" in text
        assert "Paragraph with bold text." in text
        assert "Item 1" in text
        assert "Item 2" in text
    
    async def test_validate_can_spam_compliance(self, template_engine):
        """Test CAN-SPAM compliance validation."""
        compliant_content = """
        <html>
        <body>
        <p>Email content with unsubscribe link.</p>
        <a href="{{ unsubscribe_url }}">Unsubscribe</a>
        <p>123 Business St, Suite 100, City, State 12345</p>
        </body>
        </html>
        """
        
        issues = await template_engine.validate_can_spam_compliance(
            compliant_content, "https://test.com/unsubscribe"
        )
        
        assert len(issues) == 0
    
    async def test_validate_can_spam_non_compliance(self, template_engine):
        """Test CAN-SPAM non-compliance detection."""
        non_compliant_content = """
        <html>
        <body>
        <p>Email content without unsubscribe link or address.</p>
        </body>
        </html>
        """
        
        issues = await template_engine.validate_can_spam_compliance(
            non_compliant_content, "https://test.com/unsubscribe"
        )
        
        assert len(issues) > 0
        assert any("unsubscribe" in issue.lower() for issue in issues)
        assert any("address" in issue.lower() for issue in issues)
    
    async def test_generate_preview(self, template_engine, sample_template_context):
        """Test preview generation."""
        template_content = """
        <h1>{{ subject }}</h1>
        <p>This is the main content of the email.</p>
        <p>{{ subscriber.first_name }}, welcome to our newsletter!</p>
        """
        
        context_with_subject = sample_template_context.copy()
        context_with_subject["subject"] = "Test Newsletter"
        
        preview = await template_engine.generate_preview(
            template_content, context_with_subject
        )
        
        assert len(preview) <= 150  # Preview should be truncated
        assert "Test Newsletter" in preview or "This is the main content" in preview
    
    async def test_render_email_with_subscriber(self, template_engine, sample_subscriber):
        """Test rendering email with subscriber object."""
        template_content = """
        <h1>Hello {{ subscriber.first_name }}!</h1>
        <p>Your email: {{ subscriber.email }}</p>
        <p>Status: {{ subscriber.status }}</p>
        """
        
        context = {
            "subscriber": sample_subscriber,
            "company_name": "Test Company",
            "unsubscribe_url": "https://test.com/unsubscribe"
        }
        
        rendered = await template_engine.render_email(
            "test_template", context, sample_subscriber
        )
        
        assert "Hello Test!" in rendered["html"]
        assert "test@example.com" in rendered["html"]
        assert "active" in rendered["html"].lower()
    
    async def test_template_inheritance(self, template_engine, sample_template_context):
        """Test template inheritance."""
        # This would test extending base templates
        # Implementation depends on having actual template files
        pass
    
    async def test_custom_filters(self, template_engine):
        """Test custom template filters."""
        # Test date filter
        date_obj = datetime(2023, 5, 15, 10, 30, tzinfo=timezone.utc)
        filtered_date = template_engine._date_filter(date_obj)
        assert isinstance(filtered_date, str)
        
        # Test email mask filter
        masked_email = template_engine._mask_email_filter("test@example.com")
        assert masked_email == "t***@example.com"
        
        # Test currency filter
        currency = template_engine._currency_filter(1234.56)
        assert "$" in currency or "1,234.56" in currency
    
    async def test_template_error_handling(self, template_engine, sample_template_context):
        """Test template error handling."""
        invalid_template = """
        <p>This template has invalid syntax:
        {% if condition %}
        <p>Missing endif
        """
        
        with pytest.raises(TemplateSyntaxError):
            await template_engine.render_template_content(
                invalid_template, sample_template_context
            )
    
    async def test_template_security(self, template_engine, sample_template_context):
        """Test template security (XSS prevention)."""
        malicious_context = sample_template_context.copy()
        malicious_context["user_input"] = "<script>alert('xss')</script>"
        
        template_content = """
        <p>User input: {{ user_input }}</p>
        """
        
        rendered = await template_engine.render_template_content(
            template_content, malicious_context
        )
        
        # Script tags should be escaped by default
        assert "<script>" not in rendered["html"]
        assert "&lt;script&gt;" in rendered["html"]


@pytest.mark.integration
class TestTemplateEngineIntegration:
    """Test template engine integration scenarios."""
    
    async def test_render_complete_newsletter(self, template_engine, sample_template_context):
        """Test rendering a complete newsletter template."""
        newsletter_context = sample_template_context.copy()
        newsletter_context.update({
            "newsletter_title": "Weekly Insights",
            "newsletter_date": datetime.now(timezone.utc),
            "articles": [
                {"title": "Article 1", "summary": "Summary 1"},
                {"title": "Article 2", "summary": "Summary 2"}
            ]
        })
        
        template_content = """
        <h1>{{ newsletter_title }}</h1>
        <p>Date: {{ newsletter_date|date_filter }}</p>
        {% for article in articles %}
        <h2>{{ article.title }}</h2>
        <p>{{ article.summary }}</p>
        {% endfor %}
        """
        
        rendered = await template_engine.render_template_content(
            template_content, newsletter_context
        )
        
        assert "Weekly Insights" in rendered["html"]
        assert "Article 1" in rendered["html"]
        assert "Article 2" in rendered["html"]
        assert "Summary 1" in rendered["html"]
        assert "Summary 2" in rendered["html"]
    
    async def test_render_welcome_sequence_email(self, template_engine, sample_template_context):
        """Test rendering welcome sequence email."""
        welcome_context = sample_template_context.copy()
        welcome_context.update({
            "lead_magnet": {
                "name": "Free Guide",
                "url": "https://test.com/guide"
            },
            "sequence_step": 1,
            "total_steps": 5
        })
        
        template_content = """
        <h1>Welcome to {{ company_name }}!</h1>
        <p>This is step {{ sequence_step }} of {{ total_steps }}.</p>
        {% if lead_magnet %}
        <p>Your free {{ lead_magnet.name }} is ready:</p>
        <a href="{{ lead_magnet.url }}">Download Now</a>
        {% endif %}
        """
        
        rendered = await template_engine.render_template_content(
            template_content, welcome_context
        )
        
        assert "Welcome to Test Company!" in rendered["html"]
        assert "step 1 of 5" in rendered["html"]
        assert "Free Guide" in rendered["html"]
        assert "Download Now" in rendered["html"]
    
    async def test_render_product_launch_email(self, template_engine, sample_template_context):
        """Test rendering product launch email."""
        product_context = sample_template_context.copy()
        product_context.update({
            "product": {
                "name": "Amazing Product",
                "description": "This product will change your life",
                "price": "$99.99",
                "features": ["Feature 1", "Feature 2", "Feature 3"]
            },
            "launch_date": datetime.now(timezone.utc),
            "discount_code": "LAUNCH20"
        })
        
        template_content = """
        <h1>Introducing {{ product.name }}!</h1>
        <p>{{ product.description }}</p>
        <p>Price: {{ product.price }}</p>
        <p>Features:</p>
        <ul>
        {% for feature in product.features %}
        <li>{{ feature }}</li>
        {% endfor %}
        </ul>
        <p>Use code: {{ discount_code }}</p>
        """
        
        rendered = await template_engine.render_template_content(
            template_content, product_context
        )
        
        assert "Introducing Amazing Product!" in rendered["html"]
        assert "$99.99" in rendered["html"]
        assert "Feature 1" in rendered["html"]
        assert "LAUNCH20" in rendered["html"]


@pytest.mark.unit
class TestTemplateEnginePerformance:
    """Test template engine performance."""
    
    async def test_render_performance(self, template_engine, sample_template_context):
        """Test template rendering performance."""
        import time
        
        template_content = """
        <h1>{{ subject }}</h1>
        {% for item in items %}
        <p>{{ item.title }} - {{ item.description }}</p>
        {% endfor %}
        """
        
        context = sample_template_context.copy()
        context["items"] = [
            {"title": f"Item {i}", "description": f"Description {i}"}
            for i in range(100)
        ]
        
        start_time = time.time()
        
        # Render multiple times to test performance
        for _ in range(10):
            await template_engine.render_template_content(
                template_content, context
            )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete reasonably quickly (adjust threshold as needed)
        assert total_time < 5.0  # 5 seconds for 10 renders of 100 items
    
    async def test_memory_usage(self, template_engine, sample_template_context):
        """Test memory usage during rendering."""
        import gc
        
        template_content = """
        <h1>Large Template</h1>
        {% for item in large_list %}
        <p>{{ item }}</p>
        {% endfor %}
        """
        
        context = sample_template_context.copy()
        context["large_list"] = [f"Item {i}" for i in range(1000)]
        
        # Render and check memory doesn't grow excessively
        initial_objects = len(gc.get_objects())
        
        await template_engine.render_template_content(
            template_content, context
        )
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Object count shouldn't grow excessively
        object_growth = final_objects - initial_objects
        assert object_growth < 1000  # Adjust threshold as needed
