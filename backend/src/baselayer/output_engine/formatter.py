"""
BaseLayer Output Formatter

Output formatting engine with support for multiple formats
for the Output Engine subsystem.
"""

import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Union
from xml.dom import minidom

from structlog import get_logger

from .exceptions import FormattingError

logger = get_logger(__name__)


class OutputFormatter:
    """
    Output formatting engine.
    
    Supports multiple output formats (HTML, PDF, JSON, XML, CSV, TXT)
    with styling, validation, and error handling.
    """
    
    def __init__(self):
        self.supported_formats = ["html", "pdf", "json", "xml", "csv", "txt"]
        self.default_format = "html"
        self.max_format_time: int = 60  # seconds
        self.max_output_size: int = 50 * 1024 * 1024  # 50MB
        
        # Format-specific configurations
        self.format_configs = {
            "html": {
                "doctype": "<!DOCTYPE html>",
                "default_css": True,
                "minify": False,
                "validate": True
            },
            "pdf": {
                "page_size": "A4",
                "margin": "1cm",
                "orientation": "portrait"
            },
            "json": {
                "indent": 2,
                "sort_keys": False,
                "ensure_ascii": False
            },
            "xml": {
                "pretty_print": True,
                "xml_declaration": True,
                "encoding": "utf-8"
            },
            "csv": {
                "delimiter": ",",
                "quotechar": '"',
                "quoting": 1,  # csv.QUOTE_MINIMAL
                "lineterminator": "\n"
            },
            "txt": {
                "encoding": "utf-8",
                "line_wrap": 80
            }
        }
        
        # Formatting metrics
        self.formatting_metrics = {
            "total_formats": 0,
            "successful_formats": 0,
            "failed_formats": 0,
            "average_format_time": 0.0
        }
    
    async def format_output(
        self,
        content: str,
        format_type: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Format content to specified output format.
        
        Args:
            content: Content to format
            format_type: Target format
            options: Formatting options
            
        Returns:
            bytes: Formatted output
            
        Raises:
            FormattingError: If formatting fails
        """
        if format_type not in self.supported_formats:
            raise FormattingError(f"Unsupported format: {format_type}", format_type=format_type)
        
        try:
            # Validate inputs
            await self._validate_formatting_inputs(content, format_type)
            
            # Merge with default configuration
            config = {**self.format_configs[format_type], **(options or {})}
            
            # Format content
            start_time = datetime.utcnow()
            
            if format_type == "html":
                formatted_output = await self._format_html(content, config)
            elif format_type == "pdf":
                formatted_output = await self._format_pdf(content, config)
            elif format_type == "json":
                formatted_output = await self._format_json(content, config)
            elif format_type == "xml":
                formatted_output = await self._format_xml(content, config)
            elif format_type == "csv":
                formatted_output = await self._format_csv(content, config)
            elif format_type == "txt":
                formatted_output = await self._format_txt(content, config)
            else:
                raise FormattingError(f"Format type not implemented: {format_type}", format_type=format_type)
            
            format_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update metrics
            self._update_formatting_metrics(True, format_time)
            
            # Validate output size
            if len(formatted_output) > self.max_output_size:
                raise FormattingError(f"Formatted output too large: {len(formatted_output)} bytes")
            
            logger.debug(
                "Content formatted successfully",
                format_type=format_type,
                output_size=len(formatted_output),
                format_time=format_time
            )
            
            return formatted_output
            
        except Exception as e:
            self._update_formatting_metrics(False, 0)
            
            logger.error(
                "Content formatting failed",
                format_type=format_type,
                error=str(e)
            )
            
            raise FormattingError(f"Failed to format content: {str(e)}", format_type=format_type) from e
    
    async def format_data(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        format_type: str,
        template: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Format data to specified output format.
        
        Args:
            data: Data to format
            format_type: Target format
            template: Optional template for formatting
            options: Formatting options
            
        Returns:
            bytes: Formatted output
            
        Raises:
            FormattingError: If formatting fails
        """
        try:
            if format_type == "json":
                return await self._format_data_json(data, options or {})
            elif format_type == "xml":
                return await self._format_data_xml(data, template, options or {})
            elif format_type == "csv":
                return await self._format_data_csv(data, options or {})
            elif format_type == "txt":
                return await self._format_data_txt(data, template, options or {})
            else:
                # For other formats, convert to string first
                content = json.dumps(data, indent=2)
                return await self.format_output(content, format_type, options)
                
        except Exception as e:
            raise FormattingError(f"Failed to format data: {str(e)}", format_type=format_type) from e
    
    async def validate_format(
        self,
        content: bytes,
        format_type: str
    ) -> Dict[str, Any]:
        """
        Validate formatted content.
        
        Args:
            content: Content to validate
            format_type: Format type
            
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "format_type": format_type,
            "size": len(content)
        }
        
        try:
            if format_type == "json":
                await self._validate_json(content, validation_result)
            elif format_type == "xml":
                await self._validate_xml(content, validation_result)
            elif format_type == "html":
                await self._validate_html(content, validation_result)
            elif format_type == "csv":
                await self._validate_csv(content, validation_result)
            
            # Check size
            if len(content) > self.max_output_size:
                validation_result["warnings"].append(f"Output size ({len(content)} bytes) exceeds recommended limit")
            
            return validation_result
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(str(e))
            
            return validation_result
    
    async def get_formatting_stats(self) -> Dict[str, Any]:
        """
        Get formatting statistics.
        
        Returns:
            Dict[str, Any]: Formatting statistics
        """
        return {
            "supported_formats": self.supported_formats,
            "default_format": self.default_format,
            "max_format_time": self.max_format_time,
            "max_output_size": self.max_output_size,
            "format_configs": self.format_configs,
            "formatting_metrics": self.formatting_metrics
        }
    
    async def _format_html(self, content: str, config: Dict[str, Any]) -> bytes:
        """Format content as HTML."""
        try:
            # Basic HTML structure
            if config.get("doctype"):
                html_content = config["doctype"] + "\n"
            else:
                html_content = "<!DOCTYPE html>\n"
            
            html_content += "<html>\n<head>\n"
            
            # Add meta tags
            html_content += '<meta charset="utf-8">\n'
            html_content += '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            
            # Add title if not present
            if "<title>" not in content:
                html_content += "<title>Generated Output</title>\n"
            
            # Add default CSS if requested
            if config.get("default_css"):
                html_content += "<style>\n"
                html_content += """
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                h1, h2, h3 { color: #333; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                """
                html_content += "</style>\n"
            
            html_content += "</head>\n<body>\n"
            
            # Add content
            html_content += content
            
            html_content += "\n</body>\n</html>"
            
            # Minify if requested
            if config.get("minify"):
                import re
                html_content = re.sub(r'>\s+<', '><', html_content)
                html_content = re.sub(r'\s+', ' ', html_content).strip()
            
            return html_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"HTML formatting failed: {str(e)}", format_type="html") from e
    
    async def _format_pdf(self, content: str, config: Dict[str, Any]) -> bytes:
        """Format content as PDF."""
        try:
            # For PDF generation, we'll use a simple approach
            # In a real implementation, this would use libraries like ReportLab or WeasyPrint
            
            # Convert HTML to simple PDF-like format
            # This is a simplified implementation
            pdf_content = f"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 4 0 R
>>
>>
/MediaBox [0 0 612 792]
/Contents 5 0 R
>>
endobj

4 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj

5 0 obj
<<
/Length {len(content)}
>>
stream
{content}
endstream
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000201 00000 n 
0000000256 00000 n 

trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
{len(content) + 300}
%%EOF
"""
            
            return pdf_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"PDF formatting failed: {str(e)}", format_type="pdf") from e
    
    async def _format_json(self, content: str, config: Dict[str, Any]) -> bytes:
        """Format content as JSON."""
        try:
            # Try to parse as JSON first
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, treat as string
                data = {"content": content}
            
            # Format JSON
            json_content = json.dumps(
                data,
                indent=config.get("indent", 2),
                sort_keys=config.get("sort_keys", False),
                ensure_ascii=config.get("ensure_ascii", False)
            )
            
            return json_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"JSON formatting failed: {str(e)}", format_type="json") from e
    
    async def _format_xml(self, content: str, config: Dict[str, Any]) -> bytes:
        """Format content as XML."""
        try:
            # Try to parse as XML first
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                # If not valid XML, create a simple structure
                root = ET.Element("root")
                content_element = ET.SubElement(root, "content")
                content_element.text = content
            
            # Pretty print if requested
            if config.get("pretty_print", True):
                rough_string = ET.tostring(root, encoding='unicode')
                reparsed = minidom.parseString(rough_string)
                xml_content = reparsed.toprettyxml(indent="  ")
            else:
                xml_content = ET.tostring(root, encoding='unicode')
            
            # Add XML declaration if requested
            if config.get("xml_declaration", True) and not xml_content.startswith("<?xml"):
                xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_content
            
            return xml_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"XML formatting failed: {str(e)}", format_type="xml") from e
    
    async def _format_csv(self, content: str, config: Dict[str, Any]) -> bytes:
        """Format content as CSV."""
        try:
            import csv
            
            # Try to parse as JSON first to get structured data
            try:
                data = json.loads(content)
                if isinstance(data, list) and data:
                    # Convert list of dicts to CSV
                    output = StringIO()
                    writer = csv.DictWriter(
                        output,
                        fieldnames=data[0].keys(),
                        delimiter=config.get("delimiter", ","),
                        quotechar=config.get("quotechar", '"'),
                        quoting=config.get("quoting", 1),
                        lineterminator=config.get("lineterminator", "\n")
                    )
                    writer.writeheader()
                    writer.writerows(data)
                    csv_content = output.getvalue()
                else:
                    # Single value
                    csv_content = str(data)
            except json.JSONDecodeError:
                # Treat as plain text
                csv_content = content
            
            return csv_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"CSV formatting failed: {str(e)}", format_type="csv") from e
    
    async def _format_txt(self, content: str, config: Dict[str, Any]) -> bytes:
        """Format content as plain text."""
        try:
            # Clean up HTML if present
            import re
            txt_content = re.sub(r'<[^>]+>', '', content)
            
            # Handle line wrapping if specified
            line_wrap = config.get("line_wrap", 0)
            if line_wrap > 0:
                lines = []
                for line in txt_content.split('\n'):
                    while len(line) > line_wrap:
                        lines.append(line[:line_wrap])
                        line = line[line_wrap:]
                    lines.append(line)
                txt_content = '\n'.join(lines)
            
            return txt_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"Text formatting failed: {str(e)}", format_type="txt") from e
    
    async def _format_data_json(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], config: Dict[str, Any]) -> bytes:
        """Format data as JSON."""
        try:
            json_content = json.dumps(
                data,
                indent=config.get("indent", 2),
                sort_keys=config.get("sort_keys", False),
                ensure_ascii=config.get("ensure_ascii", False)
            )
            
            return json_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"JSON data formatting failed: {str(e)}", format_type="json") from e
    
    async def _format_data_xml(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], template: Optional[str], config: Dict[str, Any]) -> bytes:
        """Format data as XML."""
        try:
            # Create root element
            root_name = template or "data"
            root = ET.Element(root_name)
            
            def dict_to_xml(parent, data):
                if isinstance(data, dict):
                    for key, value in data.items():
                        child = ET.SubElement(parent, key)
                        dict_to_xml(child, value)
                elif isinstance(data, list):
                    for item in data:
                        child = ET.SubElement(parent, "item")
                        dict_to_xml(child, item)
                else:
                    parent.text = str(data)
            
            dict_to_xml(root, data)
            
            # Pretty print if requested
            if config.get("pretty_print", True):
                rough_string = ET.tostring(root, encoding='unicode')
                reparsed = minidom.parseString(rough_string)
                xml_content = reparsed.toprettyxml(indent="  ")
            else:
                xml_content = ET.tostring(root, encoding='unicode')
            
            # Add XML declaration if requested
            if config.get("xml_declaration", True) and not xml_content.startswith("<?xml"):
                xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_content
            
            return xml_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"XML data formatting failed: {str(e)}", format_type="xml") from e
    
    async def _format_data_csv(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], config: Dict[str, Any]) -> bytes:
        """Format data as CSV."""
        try:
            import csv
            
            if isinstance(data, list) and data:
                # Convert list of dicts to CSV
                output = StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=data[0].keys(),
                    delimiter=config.get("delimiter", ","),
                    quotechar=config.get("quotechar", '"'),
                    quoting=config.get("quoting", 1),
                    lineterminator=config.get("lineterminator", "\n")
                )
                writer.writeheader()
                writer.writerows(data)
                csv_content = output.getvalue()
            elif isinstance(data, dict):
                # Single dict to CSV
                output = StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=data.keys(),
                    delimiter=config.get("delimiter", ","),
                    quotechar=config.get("quotechar", '"'),
                    quoting=config.get("quoting", 1),
                    lineterminator=config.get("lineterminator", "\n")
                )
                writer.writeheader()
                writer.writerow(data)
                csv_content = output.getvalue()
            else:
                # Single value
                csv_content = str(data)
            
            return csv_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"CSV data formatting failed: {str(e)}", format_type="csv") from e
    
    async def _format_data_txt(self, data: Union[Dict[str, Any], List[Dict[str, Any]]], template: Optional[str], config: Dict[str, Any]) -> bytes:
        """Format data as plain text."""
        try:
            if isinstance(data, list):
                lines = []
                for item in data:
                    if isinstance(item, dict):
                        line = " | ".join(f"{k}: {v}" for k, v in item.items())
                        lines.append(line)
                    else:
                        lines.append(str(item))
                txt_content = "\n".join(lines)
            elif isinstance(data, dict):
                txt_content = "\n".join(f"{k}: {v}" for k, v in data.items())
            else:
                txt_content = str(data)
            
            return txt_content.encode('utf-8')
            
        except Exception as e:
            raise FormattingError(f"Text data formatting failed: {str(e)}", format_type="txt") from e
    
    async def _validate_formatting_inputs(self, content: str, format_type: str) -> None:
        """Validate formatting inputs."""
        if not content or not content.strip():
            raise FormattingError("Content is empty")
        
        if len(content.encode('utf-8')) > self.max_output_size:
            raise FormattingError(f"Content too large: {len(content.encode('utf-8'))} bytes")
    
    async def _validate_json(self, content: bytes, validation_result: Dict[str, Any]) -> None:
        """Validate JSON content."""
        try:
            json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Invalid JSON: {str(e)}")
    
    async def _validate_xml(self, content: bytes, validation_result: Dict[str, Any]) -> None:
        """Validate XML content."""
        try:
            ET.fromstring(content.decode('utf-8'))
        except ET.ParseError as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Invalid XML: {str(e)}")
    
    async def _validate_html(self, content: bytes, validation_result: Dict[str, Any]) -> None:
        """Validate HTML content."""
        try:
            # Basic HTML validation
            html_content = content.decode('utf-8')
            
            # Check for basic HTML structure
            if not html_content.strip().startswith("<"):
                validation_result["warnings"].append("Content doesn't start with HTML tag")
            
            if not html_content.strip().endswith(">"):
                validation_result["warnings"].append("Content doesn't end with HTML tag")
            
            # Check for unclosed tags (simplified)
            import re
            tags = re.findall(r'<(/?)(\w+)', html_content)
            open_tags = []
            
            for closing, tag in tags:
                if not closing:
                    open_tags.append(tag)
                elif open_tags and open_tags[-1] == tag:
                    open_tags.pop()
            
            if open_tags:
                validation_result["warnings"].append(f"Unclosed tags: {open_tags}")
                
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"HTML validation failed: {str(e)}")
    
    async def _validate_csv(self, content: bytes, validation_result: Dict[str, Any]) -> None:
        """Validate CSV content."""
        try:
            import csv
            csv.reader(content.decode('utf-8').splitlines())
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Invalid CSV: {str(e)}")
    
    def _update_formatting_metrics(self, success: bool, format_time: float) -> None:
        """Update formatting metrics."""
        self.formatting_metrics["total_formats"] += 1
        
        if success:
            self.formatting_metrics["successful_formats"] += 1
        else:
            self.formatting_metrics["failed_formats"] += 1
        
        # Update average format time
        successful = self.formatting_metrics["successful_formats"]
        if successful > 0:
            current_avg = self.formatting_metrics["average_format_time"]
            self.formatting_metrics["average_format_time"] = (
                (current_avg * (successful - 1) + format_time) / successful
            )
