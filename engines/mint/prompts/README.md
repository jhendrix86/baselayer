# MINT Prompts

This directory contains Jinja2 templates for digital product generation and Gumroad listing optimization.

## Template Files

### Product Generation Templates

#### product_outline_v1.j2
- **Purpose**: Generate comprehensive product structure outlines
- **Variables**: `title`, `target_audience`, `word_count_target`, `brief`, `product_type`
- **Usage**: Creates detailed section structure for different product types
- **Features**: Product type-specific instructions, word count targets, quality guidelines

#### section_writer_v1.j2
- **Purpose**: Generate individual sections of product content
- **Variables**: `section_name`, `section_focus`, `word_count_target`, `product_type`
- **Usage**: Creates detailed content for specific sections
- **Features**: Section-specific guidelines, writing standards, Kade persona compliance

### Marketing Templates

#### listing_copy_v1.j2
- **Purpose**: Generate optimized Gumroad listing copy
- **Variables**: `title`, `description`, `product_type`, `target_audience`, `optimization_strategy`
- **Frameworks**: AIDA, PAS, scarcity, social proof, risk reversal
- **Features**: Character limits, benefit-focused language, CTA optimization

#### title_generator_v1.j2
- **Purpose**: Generate compelling product titles
- **Variables**: `base_title`, `product_type`, `target_audience`, `optimization_strategy`
- **Strategies**: Benefit-driven, problem-solution, scarcity, social proof
- **Features**: SEO optimization, character limits, A/B testing variants

### Persona Templates

#### kade_system_v1.j2
- **Purpose**: Kade persona system message for consistent AI behavior
- **Usage**: Provides context and constraints for all AI agents
- **Features**: Professional tone, value focus, no personal anecdotes
- **Constraints**: No identity disclosure, no placeholder text

## Template Usage

### Basic Rendering
```python
from agents.llm.prompt_engine import prompt_engine

# Render template
result = prompt_engine.render("product_outline_v1", {
    "title": "Complete Guide to Remote Work",
    "target_audience": "remote workers",
    "word_count_target": 3000,
    "product_type": "pdf_guide",
    "brief": "Comprehensive guide for remote work productivity"
})
```

### With Built-in Patterns
```python
# Render with chain-of-thought pattern
result = prompt_engine.render_with_pattern(
    "section_writer_v1",
    "chain_of_thought",
    {
        "section_name": "Implementation Steps",
        "section_focus": "practical guidance",
        "word_count_target": 1000,
        "product_type": "pdf_guide"
    }
)
```

### System Message Creation
```python
# Create system message with Kade persona
system_message = prompt_engine.create_system_message(
    persona="Kade",
    role_description="Expert digital product creator",
    purpose="Generate high-quality product content",
    constraints=[
        "No personal anecdotes",
        "Professional tone",
        "Value-focused content"
    ]
)
```

## Product Type Support

### PDF Guides
- Comprehensive, in-depth content
- Step-by-step instructions
- Examples and case studies
- Best practices and tips

### Template Packs
- Ready-to-use templates
- Customization instructions
- Usage examples
- Time-saving tips

### Checklists
- Organized task lists
- Progress tracking elements
- Completion criteria
- Context and usage instructions

### Cheat Sheets
- Quick reference information
- Essential commands and shortcuts
- Key formulas and references
- Time-saving techniques

### Prompt Libraries
- Context for each prompt
- Usage examples and variations
- Optimization tips
- Categorization by complexity

### Code Snippets
- Working, tested examples
- Comments and explanations
- Installation instructions
- Error handling and debugging tips

### Notion Templates
- Notion-specific features
- Database structure guidance
- Setup and customization instructions
- Automation and integration tips

## Quality Standards

### Content Quality
- No placeholder text or incomplete sections
- Proper grammar and spelling
- Consistent formatting and structure
- Meets specified word count targets

### Kade Persona Compliance
- No personal anecdotes or identity disclosure
- Professional, authoritative tone
- Focus on practical value and actionable insights
- No "I think", "I believe", "In my opinion"

### Marketing Effectiveness
- Benefit-focused language
- Emotional appeal where appropriate
- Clear call-to-action
- Character limit compliance
- SEO optimization where applicable

## Template Variables

### Common Variables
- `title`: Product title
- `description`: Product description
- `product_type`: Type of digital product
- `target_audience`: Target audience demographic
- `word_count_target`: Target word count
- `brief`: Product brief or description
- `optimization_strategy`: Marketing optimization approach

### Framework Variables
- `framework`: AIDA, PAS, etc.
- `flow`: Step sequence in framework
- `focus`: Primary focus area
- `max_length`: Character or word limits

### Quality Variables
- `min_quality_score`: Minimum acceptable quality
- `require_human_review`: Whether human review is required
- `auto_approval_threshold`: Automatic approval threshold

## Template Validation

### Structure Validation
- All required variables present
- Valid product type specified
- Word count targets reasonable
- Character limits respected

### Content Validation
- No placeholder text detected
- Kade persona compliance verified
- Quality score thresholds met
- Marketing effectiveness criteria satisfied

## Best Practices

### Template Creation
- Use clear, descriptive names
- Include comprehensive metadata
- Specify all required variables
- Provide usage examples
- Document constraints and requirements

### Template Usage
- Validate all variables before rendering
- Use appropriate model for task complexity
- Monitor quality scores and compliance
- Cache frequently used templates

### Quality Assurance
- Test templates with various inputs
- Validate output quality and compliance
- Monitor performance metrics
- Update templates based on feedback

## Integration

### With Agent Framework
- Templates integrate with ProductGenerator agent
- Automatic variable validation
- Quality score calculation
- Error handling and retry logic

### With Pipeline System
- Templates used in product creation pipeline
- Consistent Kade persona across all steps
- Quality gates between pipeline stages
- Automatic template versioning

### With Gumroad Integration
- Listing optimization templates
- Character limit enforcement
- Marketing effectiveness tracking
- A/B testing support

## Template Management

### Versioning
- Semantic versioning (v1.0.0)
- Changelog tracking
- Backward compatibility
- Migration support

### Caching
- Template compilation caching
- Variable validation caching
- Performance optimization
- Memory management

### Updates
- Template improvement based on feedback
- Quality score threshold adjustments
- New product type support
- Marketing strategy updates

## Troubleshooting

### Common Issues
- Missing variables or invalid values
- Character limit violations
- Kade persona compliance failures
- Quality score below thresholds

### Debugging
- Enable debug logging
- Variable validation output
- Template rendering traces
- Performance metrics

### Support
- Template documentation
- Usage examples
- Best practices guide
- Troubleshooting guide
- Support contact information

## Future Enhancements

### Planned Features
- Dynamic template generation
- A/B testing framework
- Advanced quality scoring
- Multi-language support
- Custom template builder

### Template Library
- Community-contributed templates
- Template marketplace
- Template sharing platform
- Version control integration

## Security Considerations

### Input Validation
- Sanitize all template variables
- Validate input types and ranges
- Prevent injection attacks
- Enforce size limits

### Output Sanitization
- Remove sensitive information
- Validate output format
- Prevent XSS attacks
- Ensure safe content generation

### Access Control
- Role-based template access
- Template usage auditing
- Rate limiting for template generation
- Secure template storage

## Performance Optimization

### Caching Strategy
- Template compilation caching
- Variable validation caching
- Result caching where appropriate
- Memory-efficient storage

### Resource Management
- Monitor memory usage
- Optimize template rendering
- Limit concurrent operations
- Resource cleanup

### Metrics Tracking
- Template usage statistics
- Performance metrics collection
- Quality score trends
- Optimization effectiveness

## Maintenance

### Regular Updates
- Template quality reviews
- Performance optimization
- Security updates
- Feature enhancements

### Testing
- Unit tests for all templates
- Integration tests with agents
- Performance benchmarking
- Security testing

### Documentation
- Keep documentation current
- Update examples and best practices
- Maintain changelog
- Provide migration guides
