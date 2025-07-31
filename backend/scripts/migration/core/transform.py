#!/usr/bin/env python3
"""
Core transformation utilities for payroll data migration.

This module provides common transformation functions used across
different legacy system migrations.
"""

import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import hashlib
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class DataTransformer:
    """Common data transformation utilities."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize transformer with optional encryption key."""
        self.encryption_key = encryption_key
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode()[:32])
        else:
            self.cipher = None
    
    # Date transformations
    
    @staticmethod
    def transform_date(date_str: str, source_format: Optional[str] = None) -> Optional[date]:
        """Convert various date formats to ISO format date object."""
        if not date_str or str(date_str).upper() in ('NULL', 'NONE', 'NAN', ''):
            return None
        
        # Handle numeric dates (Excel serial numbers)
        if isinstance(date_str, (int, float)):
            try:
                # Excel date serial number
                return datetime(1900, 1, 1) + timedelta(days=int(date_str) - 2)
            except:
                pass
        
        # Common date formats to try
        formats = [
            '%Y-%m-%d',      # ISO format
            '%Y%m%d',        # YYYYMMDD
            '%m/%d/%Y',      # MM/DD/YYYY
            '%m-%d-%Y',      # MM-DD-YYYY
            '%d/%m/%Y',      # DD/MM/YYYY
            '%d-%m-%Y',      # DD-MM-YYYY
            '%Y/%m/%d',      # YYYY/MM/DD
            '%d-%b-%Y',      # DD-MON-YYYY
            '%d-%B-%Y',      # DD-MONTH-YYYY
            '%m%d%Y',        # MMDDYYYY
            '%Y-%m-%d %H:%M:%S',  # DateTime formats
            '%m/%d/%Y %H:%M:%S',
        ]
        
        # Add source format to the beginning if provided
        if source_format:
            formats.insert(0, source_format)
        
        date_str = str(date_str).strip()
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        logger.warning(f"Unable to parse date: {date_str}")
        return None
    
    # Numeric transformations
    
    @staticmethod
    def transform_decimal(value: Any, precision: int = 2) -> Optional[Decimal]:
        """Convert value to Decimal with specified precision."""
        if value is None or str(value).upper() in ('NULL', 'NONE', 'NAN', ''):
            return None
        
        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                value = value.replace('$', '').replace(',', '').strip()
                
                # Handle parentheses for negative numbers
                if value.startswith('(') and value.endswith(')'):
                    value = '-' + value[1:-1]
            
            decimal_value = Decimal(str(value))
            
            # Round to specified precision
            quantize_str = '0.' + '0' * precision
            return decimal_value.quantize(Decimal(quantize_str))
            
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Unable to convert to decimal: {value} - {str(e)}")
            return None
    
    @staticmethod
    def transform_percentage(value: Any) -> Optional[Decimal]:
        """Convert percentage value to decimal (e.g., 6% -> 0.06)."""
        if value is None:
            return None
        
        try:
            # Remove % symbol if present
            if isinstance(value, str):
                value = value.replace('%', '').strip()
            
            decimal_value = Decimal(str(value))
            
            # If value is greater than 1, assume it's already a percentage
            if decimal_value > 1:
                return decimal_value / 100
            
            return decimal_value
            
        except (InvalidOperation, ValueError):
            logger.warning(f"Unable to convert percentage: {value}")
            return None
    
    # String transformations
    
    @staticmethod
    def transform_name(name: str) -> str:
        """Clean and format names with proper capitalization."""
        if not name:
            return ''
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Handle special cases
        name_parts = []
        for part in name.split():
            # Suffixes that should be uppercase
            if part.upper() in ['II', 'III', 'IV', 'JR', 'SR', 'MD', 'PHD', 'ESQ']:
                name_parts.append(part.upper())
            # Handle names with apostrophes (O'Brien, D'Angelo)
            elif "'" in part:
                subparts = part.split("'")
                name_parts.append("'".join(p.capitalize() for p in subparts))
            # Handle hyphenated names (Smith-Jones)
            elif "-" in part:
                subparts = part.split("-")
                name_parts.append("-".join(p.capitalize() for p in subparts))
            # Handle names with periods (St. James)
            elif "." in part and len(part) <= 3:
                name_parts.append(part.capitalize())
            else:
                name_parts.append(part.capitalize())
        
        return ' '.join(name_parts)
    
    @staticmethod
    def transform_phone(phone: str) -> Optional[str]:
        """Clean and format phone numbers to standard format."""
        if not phone:
            return None
        
        # Remove all non-numeric characters
        digits = re.sub(r'\D', '', str(phone))
        
        # Check for valid length
        if len(digits) == 10:
            # Format as (XXX) XXX-XXXX
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            # Remove country code
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            logger.warning(f"Invalid phone number length: {phone}")
            return phone  # Return original if can't format
    
    @staticmethod
    def transform_email(email: str) -> Optional[str]:
        """Validate and clean email addresses."""
        if not email:
            return None
        
        email = str(email).strip().lower()
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, email):
            return email
        else:
            logger.warning(f"Invalid email format: {email}")
            return None
    
    # SSN transformations
    
    def transform_ssn(self, ssn: str) -> Optional[str]:
        """Clean, validate, and encrypt SSN."""
        if not ssn:
            return None
        
        # Remove all non-digits
        clean_ssn = re.sub(r'\D', '', str(ssn))
        
        # Validate SSN format
        if len(clean_ssn) != 9:
            logger.warning(f"Invalid SSN length: {len(clean_ssn)}")
            return None
        
        # Check for invalid SSNs
        if clean_ssn == '000000000':
            logger.warning("Invalid SSN: all zeros")
            return None
        
        if clean_ssn[:3] == '000' or clean_ssn[3:5] == '00' or clean_ssn[5:] == '0000':
            logger.warning("Invalid SSN format")
            return None
        
        # Encrypt if cipher is available
        if self.cipher:
            encrypted = self.cipher.encrypt(clean_ssn.encode())
            return encrypted.decode()
        else:
            # If no encryption, at least hash it
            return hashlib.sha256(clean_ssn.encode()).hexdigest()
    
    # Boolean transformations
    
    @staticmethod
    def transform_boolean(value: Any) -> Optional[bool]:
        """Convert various boolean representations to Python bool."""
        if value is None:
            return None
        
        if isinstance(value, bool):
            return value
        
        # String representations
        str_value = str(value).upper().strip()
        
        true_values = {'Y', 'YES', '1', 'T', 'TRUE', 'X', 'ACTIVE', 'ENABLED'}
        false_values = {'N', 'NO', '0', 'F', 'FALSE', '', 'INACTIVE', 'DISABLED'}
        
        if str_value in true_values:
            return True
        elif str_value in false_values:
            return False
        else:
            logger.warning(f"Unable to parse boolean: {value}")
            return None
    
    # Status mappings
    
    @staticmethod
    def transform_employment_status(status: str, status_mapping: Optional[Dict[str, str]] = None) -> str:
        """Map legacy employment status to standard values."""
        if not status:
            return 'unknown'
        
        # Default mapping if none provided
        if not status_mapping:
            status_mapping = {
                'A': 'active',
                'ACTIVE': 'active',
                'T': 'terminated',
                'TERM': 'terminated',
                'TERMINATED': 'terminated',
                'L': 'leave',
                'LOA': 'leave',
                'LEAVE': 'leave',
                'S': 'suspended',
                'SUSPENDED': 'suspended',
                'R': 'retired',
                'RETIRED': 'retired',
                'I': 'inactive',
                'INACTIVE': 'inactive'
            }
        
        status_upper = str(status).upper().strip()
        return status_mapping.get(status_upper, 'unknown')
    
    @staticmethod
    def transform_pay_frequency(frequency: str, frequency_mapping: Optional[Dict[str, str]] = None) -> str:
        """Map legacy pay frequency to standard values."""
        if not frequency:
            return 'unknown'
        
        # Default mapping if none provided
        if not frequency_mapping:
            frequency_mapping = {
                'W': 'weekly',
                'WEEKLY': 'weekly',
                '52': 'weekly',
                'B': 'biweekly',
                'BW': 'biweekly',
                'BIWEEKLY': 'biweekly',
                'BI-WEEKLY': 'biweekly',
                '26': 'biweekly',
                'S': 'semimonthly',
                'SM': 'semimonthly',
                'SEMIMONTHLY': 'semimonthly',
                'SEMI-MONTHLY': 'semimonthly',
                '24': 'semimonthly',
                'M': 'monthly',
                'MONTHLY': 'monthly',
                '12': 'monthly'
            }
        
        frequency_upper = str(frequency).upper().strip()
        return frequency_mapping.get(frequency_upper, 'unknown')
    
    # Address transformations
    
    @staticmethod
    def transform_state_code(state: str) -> Optional[str]:
        """Standardize state codes to 2-letter abbreviations."""
        if not state:
            return None
        
        state = str(state).strip().upper()
        
        # Already 2-letter code
        if len(state) == 2:
            return state
        
        # State name to code mapping (partial list)
        state_mapping = {
            'CALIFORNIA': 'CA',
            'NEW YORK': 'NY',
            'TEXAS': 'TX',
            'FLORIDA': 'FL',
            'ILLINOIS': 'IL',
            'PENNSYLVANIA': 'PA',
            'OHIO': 'OH',
            'GEORGIA': 'GA',
            'NORTH CAROLINA': 'NC',
            'MICHIGAN': 'MI'
            # Add more as needed
        }
        
        return state_mapping.get(state, state[:2] if len(state) > 2 else state)
    
    @staticmethod
    def transform_zip_code(zip_code: str) -> Optional[str]:
        """Clean and format ZIP codes."""
        if not zip_code:
            return None
        
        # Remove all non-alphanumeric characters
        clean_zip = re.sub(r'[^A-Z0-9]', '', str(zip_code).upper())
        
        # US ZIP code formatting
        if clean_zip.isdigit():
            if len(clean_zip) == 5:
                return clean_zip
            elif len(clean_zip) == 9:
                return f"{clean_zip[:5]}-{clean_zip[5:]}"
            else:
                logger.warning(f"Invalid ZIP code length: {zip_code}")
                return clean_zip
        
        # Return as-is for international postal codes
        return clean_zip


# DataFrame transformation functions

def apply_field_mappings(df: pd.DataFrame, field_mapping: Dict[str, Union[str, callable]]) -> pd.DataFrame:
    """Apply field mappings to a DataFrame."""
    result_df = pd.DataFrame()
    
    for source_field, target in field_mapping.items():
        if callable(target):
            # Apply transformation function
            result_df[source_field] = df.apply(target, axis=1)
        elif source_field in df.columns:
            # Direct mapping
            result_df[target] = df[source_field]
        else:
            logger.warning(f"Source field '{source_field}' not found in DataFrame")
    
    return result_df


def validate_transformed_data(df: pd.DataFrame, validation_rules: Dict[str, callable]) -> List[Dict]:
    """Validate transformed data against business rules."""
    violations = []
    
    for rule_name, rule_func in validation_rules.items():
        try:
            invalid_rows = df[~df.apply(rule_func, axis=1)]
            if not invalid_rows.empty:
                violations.append({
                    'rule': rule_name,
                    'count': len(invalid_rows),
                    'sample_indices': invalid_rows.index[:5].tolist()
                })
        except Exception as e:
            logger.error(f"Error applying validation rule '{rule_name}': {str(e)}")
            violations.append({
                'rule': rule_name,
                'error': str(e)
            })
    
    return violations


def create_transformation_report(source_df: pd.DataFrame, 
                               target_df: pd.DataFrame,
                               violations: List[Dict]) -> Dict:
    """Create a report summarizing the transformation results."""
    report = {
        'source_records': len(source_df),
        'target_records': len(target_df),
        'records_dropped': len(source_df) - len(target_df),
        'columns_mapped': list(target_df.columns),
        'null_counts': target_df.isnull().sum().to_dict(),
        'validation_violations': violations,
        'transformation_date': datetime.now().isoformat()
    }
    
    return report


if __name__ == "__main__":
    # Example usage
    transformer = DataTransformer()
    
    # Test transformations
    print(f"Date: {transformer.transform_date('01/15/2024')}")
    print(f"Name: {transformer.transform_name('john o\\'brien')}")
    print(f"Phone: {transformer.transform_phone('555-123-4567')}")
    print(f"Decimal: {transformer.transform_decimal('$1,234.56')}")
    print(f"Boolean: {transformer.transform_boolean('Y')}")
    
    print("Transformation utilities loaded successfully")