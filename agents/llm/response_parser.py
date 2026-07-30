"""
BaseLayer Response Parser

Parse and validate LLM outputs with JSON extraction,
retry-with-feedback, and Pydantic model validation.
"""

import json
import re
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ValidationError

from baselayer.core.logging import get_logger
from baselayer.agents.exceptions import AgentError as BaseLayerError

logger = get_logger(__name__)


class ParseResult:
    """Result of parsing attempt."""
    
    def __init__(
        self,
        success: bool,
        data: Optional[Any] = None,
        error: Optional[str] = None,
        raw_text: Optional[str] = None
    ) -> None:
        """Initialize parse result."""
        self.success: bool = success
        self.data: Optional[Any] = data
        self.error: Optional[str] = error
        self.raw_text: Optional[str] = raw_text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "raw_text": self.raw_text
        }


class ResponseParser:
    """
    LLM response parser with validation and retry logic.
    
    Extracts JSON from freeform text, validates against
    Pydantic models, and provides retry-with-feedback.
    """
    
    def __init__(self, max_retries: int = 3) -> None:
        """Initialize response parser."""
        self.max_retries: int = max_retries
        
        logger.info(
            "Response parser initialized",
            max_retries=max_retries
        )
    
    def parse_json(
        self,
        response_text: str,
        schema_model: Optional[Type[BaseModel]] = None
    ) -> ParseResult:
        """
        Parse JSON from response text.
        
        Args:
            response_text: LLM response text
            schema_model: Optional Pydantic model for validation
            
        Returns:
            ParseResult with parsed data or error
        """
        try:
            # Try to extract JSON from response
            json_data = self._extract_json(response_text)
            
            if json_data is None:
                return ParseResult(
                    success=False,
                    error="No JSON found in response",
                    raw_text=response_text
                )
            
            # Validate against schema if provided
            if schema_model:
                validated_data = self._validate_pydantic(json_data, schema_model)
                if not validated_data.success:
                    return validated_data
                
                return ParseResult(
                    success=True,
                    data=validated_data.data,
                    raw_text=response_text
                )
            
            return ParseResult(
                success=True,
                data=json_data,
                raw_text=response_text
            )
            
        except Exception as e:
            logger.error(
                "JSON parsing failed",
                error=str(e),
                response_length=len(response_text)
            )
            
            return ParseResult(
                success=False,
                error=f"JSON parsing failed: {str(e)}",
                raw_text=response_text
            )
    
    def parse_with_retry(
        self,
        response_text: str,
        schema_model: Optional[Type[BaseModel]] = None,
        original_request: Optional[str] = None
    ) -> ParseResult:
        """
        Parse with retry-with-feedback logic.
        
        Args:
            response_text: LLM response text
            schema_model: Optional Pydantic model for validation
            original_request: Original request for retry feedback
            
        Returns:
            ParseResult with final result or error
        """
        current_text = response_text
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            result = self.parse_json(current_text, schema_model)
            
            if result.success:
                if attempt > 0:
                    logger.info(
                        "Parse succeeded after retry",
                        attempt=attempt + 1,
                        max_attempts=self.max_retries + 1
                    )
                
                return result
            
            last_error = result.error
            
            if attempt < self.max_retries and original_request:
                # Generate retry feedback
                retry_prompt = self._generate_retry_feedback(
                    original_request,
                    result.error,
                    attempt + 1
                )
                
                logger.info(
                    "Parse failed, generating retry feedback",
                    attempt=attempt + 1,
                    error=result.error
                )
                
                # In a real implementation, would send this back to LLM
                # For now, just log it
                logger.debug(
                    "Retry feedback generated",
                    feedback=retry_prompt
                )
                
                # Simulate LLM correction by trying common fixes
                current_text = self._attempt_common_fixes(current_text, result.error)
            else:
                # Final attempt failed
                logger.error(
                    "Parse failed after all retries",
                    attempts=attempt + 1,
                    final_error=last_error
                )
                
                return ParseResult(
                    success=False,
                    error=f"Parse failed after {attempt + 1} attempts: {last_error}",
                    raw_text=response_text
                )
        
        # Should not reach here
        return ParseResult(
            success=False,
            error="Unexpected parsing state",
            raw_text=response_text
        )
    
    def extract_structured_data(
        self,
        response_text: str,
        structure: Dict[str, Type]
    ) -> ParseResult:
        """
        Extract structured data based on provided structure.
        
        Args:
            response_text: LLM response text
            structure: Dictionary mapping field names to types
            
        Returns:
            ParseResult with extracted data
        """
        try:
            # First try JSON parsing
            json_result = self.parse_json(response_text)
            
            if json_result.success:
                # Extract fields according to structure
                extracted_data = {}
                for field_name, field_type in structure.items():
                    if field_name in json_result.data:
                        value = json_result.data[field_name]
                        
                        # Type conversion
                        try:
                            if field_type == int:
                                extracted_data[field_name] = int(value)
                            elif field_type == float:
                                extracted_data[field_name] = float(value)
                            elif field_type == str:
                                extracted_data[field_name] = str(value)
                            elif field_type == bool:
                                extracted_data[field_name] = bool(value)
                            elif field_type == list:
                                extracted_data[field_name] = list(value) if isinstance(value, (list, tuple)) else [value]
                            elif field_type == dict:
                                extracted_data[field_name] = dict(value) if isinstance(value, dict) else {}
                            else:
                                extracted_data[field_name] = value
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                "Type conversion failed",
                                field=field_name,
                                target_type=field_type.__name__,
                                value=value,
                                error=str(e)
                            )
                
                return ParseResult(
                    success=True,
                    data=extracted_data,
                    raw_text=response_text
                )
            
            # If JSON parsing failed, try regex extraction
            return self._extract_with_regex(response_text, structure)
            
        except Exception as e:
            logger.error(
                "Structured data extraction failed",
                error=str(e)
            )
            
            return ParseResult(
                success=False,
                error=f"Extraction failed: {str(e)}",
                raw_text=response_text
            )
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from text using multiple methods.
        
        Args:
            text: Text to extract JSON from
            
        Returns:
            Extracted JSON data or None
        """
        # Method 1: Look for JSON in markdown code fences
        fence_pattern = r'```(?:json)?\s*(.*?)\s*```'
        fence_matches = re.findall(fence_pattern, text, re.DOTALL | re.IGNORECASE)
        
        for match in fence_matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # Method 2: Look for JSON object with braces
        brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        brace_matches = re.findall(brace_pattern, text, re.DOTALL)
        
        for match in brace_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # Method 3: Try to parse entire text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Method 4: Look for JSON array
        array_pattern = r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]'
        array_matches = re.findall(array_pattern, text, re.DOTALL)
        
        for match in array_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _validate_pydantic(
        self,
        data: Dict[str, Any],
        schema_model: Type[BaseModel]
    ) -> ParseResult:
        """
        Validate data against Pydantic model.
        
        Args:
            data: Data to validate
            schema_model: Pydantic model class
            
        Returns:
            ParseResult with validation result
        """
        try:
            validated = schema_model(**data)
            
            return ParseResult(
                success=True,
                data=validated.dict(),
                raw_text=json.dumps(data, indent=2)
            )
            
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                error_details.append(f"{field}: {error['msg']}")
            
            error_msg = f"Validation failed: {'; '.join(error_details)}"
            
            logger.debug(
                "Pydantic validation failed",
                model=schema_model.__name__,
                errors=error_details
            )
            
            return ParseResult(
                success=False,
                error=error_msg,
                raw_text=json.dumps(data, indent=2)
            )
    
    def _generate_retry_feedback(
        self,
        original_request: str,
        error: str,
        attempt: int
    ) -> str:
        """
        Generate retry feedback for LLM.
        
        Args:
            original_request: Original request
            error: Error from previous attempt
            attempt: Current attempt number
            
        Returns:
            Retry feedback prompt
        """
        feedback = f"""
The previous response (attempt {attempt}) was invalid.

Error: {error}

Please fix the response to address this error.

Original request: {original_request}

Requirements:
- Valid JSON format only
- All required fields present
- Correct data types
- No explanations or extra text

Response:
"""
        
        return feedback.strip()
    
    def _attempt_common_fixes(self, text: str, error: str) -> str:
        """
        Attempt common fixes for parsing errors.
        
        Args:
            text: Original text
            error: Error message
            
        Returns:
            Fixed text
        """
        fixed_text = text
        
        # Fix 1: Remove trailing commas before closing braces
        if "Expecting ',' delimiter" in error:
            fixed_text = re.sub(r',(\s*[}\]])', r'\1', fixed_text)
        
        # Fix 2: Add missing quotes around keys
        if "Expecting property name" in error:
            fixed_text = re.sub(r'(\w+)\s*:', r'"\1":', fixed_text)
        
        # Fix 3: Remove trailing commas
        if "Expecting '}'" in error or "Expecting ']'" in error:
            fixed_text = re.sub(r',(\s*[}\]])', r'\1', fixed_text)
        
        # Fix 4: Escape unescaped quotes in strings
        if "Invalid control character" in error:
            fixed_text = re.sub(r'(?<!\\)"', r'\\"', fixed_text)
        
        # Fix 5: Remove comments (not valid in JSON)
        fixed_text = re.sub(r'//.*?\n', '\n', fixed_text)
        fixed_text = re.sub(r'/\*.*?\*/', '', fixed_text, flags=re.DOTALL)
        
        if fixed_text != text:
            logger.debug(
                "Applied common fixes",
                original_length=len(text),
                fixed_length=len(fixed_text)
            )
        
        return fixed_text
    
    def _extract_with_regex(
        self,
        text: str,
        structure: Dict[str, Type]
    ) -> ParseResult:
        """
        Extract structured data using regex patterns.
        
        Args:
            text: Text to extract from
            structure: Expected structure
            
        Returns:
            ParseResult with extracted data
        """
        extracted_data = {}
        
        for field_name, field_type in structure.items():
            # Create regex pattern for field
            if field_type == str:
                # Look for quoted strings
                pattern = rf'{field_name}\s*[:=]\s*["\']([^"\']*)["\']'
            elif field_type in (int, float):
                # Look for numbers
                pattern = rf'{field_name}\s*[:=]\s*(\d+(?:\.\d+)?)'
            elif field_type == bool:
                # Look for boolean values
                pattern = rf'{field_name}\s*[:=]\s*(true|false)'
            else:
                # Skip complex types for regex extraction
                continue
            
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                value = matches[0]
                
                # Type conversion
                try:
                    if field_type == int:
                        extracted_data[field_name] = int(value)
                    elif field_type == float:
                        extracted_data[field_name] = float(value)
                    elif field_type == bool:
                        extracted_data[field_name] = value.lower() == 'true'
                    else:
                        extracted_data[field_name] = value
                except (ValueError, TypeError):
                    logger.warning(
                        "Regex type conversion failed",
                        field=field_name,
                        value=value
                    )
        
        if extracted_data:
            return ParseResult(
                success=True,
                data=extracted_data,
                raw_text=text
            )
        
        return ParseResult(
            success=False,
            error="Could not extract structured data with regex",
            raw_text=text
        )
    
    def clean_response(self, text: str) -> str:
        """
        Clean response text for better parsing.
        
        Args:
            text: Raw response text
            
        Returns:
            Cleaned text
        """
        # Remove common LLM artifacts
        cleaned = text.strip()
        
        # Remove "Here's the JSON:" prefixes
        cleaned = re.sub(r'^(?:Here\'s the JSON:|JSON:|Response:)\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Remove explanatory text after JSON
        json_end = cleaned.find('}')
        if json_end != -1:
            # Check if there's significant text after the JSON
            after_json = cleaned[json_end + 1:].strip()
            if len(after_json) > 50:  # If substantial text after JSON
                cleaned = cleaned[:json_end + 1]
        
        # Fix common JSON formatting issues
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)  # Remove trailing commas
        cleaned = re.sub(r'(\w+)\s*:', r'"\1":', cleaned)  # Quote unquoted keys
        
        return cleaned.strip()
    
    def get_parse_statistics(self) -> Dict[str, Any]:
        """
        Get parsing statistics.
        
        Returns:
            Dictionary with parsing statistics
        """
        return {
            "max_retries": self.max_retries,
            "extraction_methods": [
                "markdown_code_fences",
                "brace_matching", 
                "full_json_parse",
                "array_matching",
                "regex_extraction"
            ]
        }


# Global response parser instance
response_parser = ResponseParser()
