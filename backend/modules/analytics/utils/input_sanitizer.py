"""
Input sanitization utilities for analytics services.

This module provides functions to sanitize and validate user inputs
to prevent SQL injection and other security vulnerabilities.
"""

import re
from typing import Any, List, Optional, Union
from datetime import date, datetime
from enum import Enum


class InputSanitizer:
    """Provides input sanitization and validation methods"""
    
    # SQL keywords that should never appear in user input
    SQL_KEYWORDS = {
        "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", 
        "ALTER", "EXEC", "EXECUTE", "UNION", "HAVING", "WHERE",
        "JOIN", "SCRIPT", "JAVASCRIPT", "VBSCRIPT", "ONLOAD",
        "ONERROR", "ONCLICK", "ONMOUSEOVER"
    }
    
    # Regex patterns for validation
    PATTERNS = {
        "alphanumeric": re.compile(r"^[a-zA-Z0-9]+$"),
        "identifier": re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$"),
        "numeric": re.compile(r"^-?\d+(\.\d+)?$"),
        "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        "safe_string": re.compile(r"^[a-zA-Z0-9\s\-_.,]+$")
    }
    
    @classmethod
    def sanitize_string(
        cls, 
        value: str, 
        max_length: int = 255,
        allow_spaces: bool = True,
        allow_special_chars: str = ""
    ) -> str:
        """
        Sanitize a string input by removing potentially dangerous characters.
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            allow_spaces: Whether to allow spaces
            allow_special_chars: Additional allowed special characters
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If input contains dangerous content
        """
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Truncate to max length
        value = value[:max_length]
        
        # Check for SQL keywords
        value_upper = value.upper()
        for keyword in cls.SQL_KEYWORDS:
            if keyword in value_upper:
                raise ValueError(f"Input contains forbidden keyword: {keyword}")
        
        # Build allowed character set
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        if allow_spaces:
            allowed_chars.add(" ")
        allowed_chars.update(allow_special_chars)
        
        # Filter characters
        sanitized = "".join(char for char in value if char in allowed_chars)
        
        # Additional XSS prevention
        sanitized = sanitized.replace("<", "").replace(">", "")
        sanitized = sanitized.replace("'", "").replace('"', "")
        sanitized = sanitized.replace("&", "and")
        
        return sanitized.strip()
    
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        """
        Validate and sanitize a database identifier (table/column name).
        
        Args:
            value: Identifier to validate
            
        Returns:
            Validated identifier
            
        Raises:
            ValueError: If identifier is invalid
        """
        if not value or not isinstance(value, str):
            raise ValueError("Identifier must be a non-empty string")
        
        # Check length
        if len(value) > 63:  # PostgreSQL identifier limit
            raise ValueError("Identifier too long (max 63 characters)")
        
        # Check pattern
        if not cls.PATTERNS["identifier"].match(value):
            raise ValueError(
                "Invalid identifier format. Must start with letter and "
                "contain only letters, numbers, and underscores"
            )
        
        # Check against SQL keywords
        if value.upper() in cls.SQL_KEYWORDS:
            raise ValueError(f"Identifier '{value}' is a reserved keyword")
        
        return value.lower()
    
    @classmethod
    def validate_numeric(
        cls, 
        value: Union[int, float, str],
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> float:
        """
        Validate and sanitize numeric input.
        
        Args:
            value: Numeric value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            
        Returns:
            Validated numeric value
            
        Raises:
            ValueError: If value is invalid
        """
        try:
            # Convert to float
            if isinstance(value, str):
                if not cls.PATTERNS["numeric"].match(value):
                    raise ValueError("Invalid numeric format")
                num_value = float(value)
            else:
                num_value = float(value)
            
            # Check range
            if min_value is not None and num_value < min_value:
                raise ValueError(f"Value must be >= {min_value}")
            if max_value is not None and num_value > max_value:
                raise ValueError(f"Value must be <= {max_value}")
            
            return num_value
            
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid numeric value: {str(e)}")
    
    @classmethod
    def validate_date(
        cls,
        value: Union[str, date, datetime],
        min_date: Optional[date] = None,
        max_date: Optional[date] = None
    ) -> date:
        """
        Validate and sanitize date input.
        
        Args:
            value: Date value to validate
            min_date: Minimum allowed date
            max_date: Maximum allowed date
            
        Returns:
            Validated date
            
        Raises:
            ValueError: If date is invalid
        """
        # Convert to date object
        if isinstance(value, datetime):
            date_value = value.date()
        elif isinstance(value, date):
            date_value = value
        elif isinstance(value, str):
            if not cls.PATTERNS["date"].match(value):
                raise ValueError("Invalid date format. Use YYYY-MM-DD")
            try:
                date_value = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid date value")
        else:
            raise ValueError("Date must be string, date, or datetime object")
        
        # Check range
        if min_date and date_value < min_date:
            raise ValueError(f"Date must be >= {min_date}")
        if max_date and date_value > max_date:
            raise ValueError(f"Date must be <= {max_date}")
        
        return date_value
    
    @classmethod
    def validate_enum(cls, value: str, allowed_values: List[str]) -> str:
        """
        Validate input against a list of allowed values.
        
        Args:
            value: Value to validate
            allowed_values: List of allowed values
            
        Returns:
            Validated value
            
        Raises:
            ValueError: If value is not in allowed list
        """
        if not isinstance(value, str):
            raise ValueError("Value must be a string")
        
        if value not in allowed_values:
            raise ValueError(
                f"Invalid value '{value}'. Allowed values: {', '.join(allowed_values)}"
            )
        
        return value
    
    @classmethod
    def validate_list_input(
        cls,
        values: List[Any],
        max_items: int = 100,
        item_validator: Optional[callable] = None
    ) -> List[Any]:
        """
        Validate a list of inputs.
        
        Args:
            values: List of values to validate
            max_items: Maximum number of items allowed
            item_validator: Optional function to validate each item
            
        Returns:
            Validated list
            
        Raises:
            ValueError: If list or items are invalid
        """
        if not isinstance(values, list):
            raise ValueError("Input must be a list")
        
        if len(values) > max_items:
            raise ValueError(f"Too many items (max {max_items})")
        
        if item_validator:
            validated_items = []
            for item in values:
                validated_items.append(item_validator(item))
            return validated_items
        
        return values
    
    @classmethod
    def sanitize_order_by(
        cls,
        column: str,
        allowed_columns: List[str],
        direction: str = "ASC"
    ) -> tuple[str, str]:
        """
        Sanitize ORDER BY clause inputs.
        
        Args:
            column: Column name to order by
            allowed_columns: List of allowed column names
            direction: Sort direction (ASC/DESC)
            
        Returns:
            Tuple of (column, direction)
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate column
        column = cls.validate_identifier(column)
        if column not in allowed_columns:
            raise ValueError(f"Invalid sort column. Allowed: {', '.join(allowed_columns)}")
        
        # Validate direction
        direction = direction.upper()
        if direction not in ["ASC", "DESC"]:
            raise ValueError("Sort direction must be ASC or DESC")
        
        return column, direction
    
    @classmethod
    def escape_like_pattern(cls, pattern: str) -> str:
        """
        Escape special characters in LIKE patterns.
        
        Args:
            pattern: LIKE pattern to escape
            
        Returns:
            Escaped pattern safe for use in LIKE queries
        """
        # Escape special LIKE characters
        pattern = pattern.replace("\\", "\\\\")
        pattern = pattern.replace("%", "\\%")
        pattern = pattern.replace("_", "\\_")
        pattern = pattern.replace("[", "\\[")
        
        return pattern