# Data Mapping Guide

This guide provides detailed field mappings and transformation rules for migrating data from legacy payroll systems to AuraConnect.

## Employee Master Data Mapping

### Basic Employee Information

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| EMP_ID | employee_code | Direct | Unique identifier |
| FIRST_NAME | first_name | Trim whitespace | |
| LAST_NAME | last_name | Trim whitespace | |
| MIDDLE_NAME | middle_name | Trim whitespace | Optional |
| SSN | ssn_encrypted | Encrypt | AES-256 encryption |
| BIRTH_DATE | date_of_birth | Date format | YYYY-MM-DD |
| HIRE_DATE | hire_date | Date format | YYYY-MM-DD |
| TERM_DATE | termination_date | Date format | Nullable |
| STATUS | employment_status | Map values | See status mapping |
| DEPT_CODE | department | Lookup | Map to department name |
| LOCATION_CODE | location | Lowercase | State/location identifier |

### Status Mapping

```python
STATUS_MAPPING = {
    'A': 'active',
    'T': 'terminated',
    'L': 'leave',
    'S': 'suspended',
    'R': 'retired',
    '1': 'active',  # Some systems use numbers
    '0': 'terminated'
}
```

### Compensation Data Mapping

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| PAY_RATE | base_salary/hourly_rate | Conditional | Based on pay type |
| PAY_FREQUENCY | pay_schedule | Map values | See frequency mapping |
| SALARY_FLAG | pay_type | Binary to text | Y='salary', N='hourly' |
| OVERTIME_ELIG | overtime_eligible | Y/N to boolean | |
| ANNUAL_SALARY | annual_salary | Calculate if needed | |
| PAY_GRADE | pay_grade | Direct | Optional |
| EFFECTIVE_DATE | compensation_effective_date | Date format | |

### Frequency Mapping

```python
FREQUENCY_MAPPING = {
    'W': 'weekly',
    'B': 'biweekly',
    'S': 'semimonthly',
    'M': 'monthly',
    'BW': 'biweekly',
    'SM': 'semimonthly',
    '26': 'biweekly',
    '24': 'semimonthly',
    '52': 'weekly',
    '12': 'monthly'
}

# Multipliers for annual calculation
FREQUENCY_MULTIPLIER = {
    'weekly': 52,
    'biweekly': 26,
    'semimonthly': 24,
    'monthly': 12
}
```

## Tax Configuration Mapping

### Federal Tax Information

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| FED_FILING_STATUS | federal_filing_status | Map values | See filing status |
| FED_ALLOWANCES | federal_allowances | Integer | W-4 allowances |
| FED_EXEMPT | is_exempt_federal | Y/N to boolean | |
| EXTRA_FED_WH | additional_federal_withholding | Decimal | |
| W4_YEAR | w4_form_year | Integer | 2019 or 2020+ |

### State Tax Information

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| STATE_CODE | state | Uppercase | Two-letter code |
| STATE_FILING_STATUS | state_filing_status | Map values | State-specific |
| STATE_ALLOWANCES | state_allowances | Integer | |
| STATE_EXEMPT | is_exempt_state | Y/N to boolean | |
| EXTRA_STATE_WH | additional_state_withholding | Decimal | |
| WORK_STATE | work_location_state | Uppercase | For multi-state |
| RESIDENT_STATE | resident_state | Uppercase | For reciprocity |

### Filing Status Mapping

```python
FILING_STATUS_MAPPING = {
    # Federal
    'S': 'single',
    'M': 'married',
    'MH': 'married_separately',
    'H': 'head_of_household',
    '1': 'single',
    '2': 'married',
    
    # State variations
    'SINGLE': 'single',
    'MAR': 'married',
    'MAR-SEP': 'married_separately',
    'HOH': 'head_of_household'
}
```

## Benefit and Deduction Mapping

### Benefit Enrollments

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| HEALTH_PLAN | health_insurance_plan | Map plan codes | |
| HEALTH_COST | health_insurance_cost | Decimal | Monthly cost |
| DENTAL_PLAN | dental_insurance_plan | Map plan codes | |
| VISION_PLAN | vision_insurance_plan | Map plan codes | |
| LIFE_COVERAGE | life_insurance_coverage | Calculate | Multiple of salary |
| 401K_PERCENT | retirement_contribution_percent | Decimal | |
| 401K_AMOUNT | retirement_contribution_amount | Decimal | Fixed amount |

### Deduction Codes Mapping

```python
DEDUCTION_MAPPING = {
    # Benefits
    'HLTH': 'health_insurance',
    'DENT': 'dental_insurance',
    'VIS': 'vision_insurance',
    'LIFE': 'life_insurance',
    '401K': '401k_contribution',
    'ROTH': 'roth_401k',
    
    # Other deductions
    'GARN': 'garnishment',
    'UNION': 'union_dues',
    'PARK': 'parking',
    'LOAN': 'employee_loan',
    'CHAR': 'charitable_contribution'
}
```

## Payment History Mapping

### Payment Records

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| PAY_DATE | pay_date | Date format | |
| CHECK_NUM | check_number | String | Nullable for DD |
| GROSS_PAY | gross_pay | Decimal(12,2) | |
| NET_PAY | net_pay | Decimal(12,2) | |
| FED_TAX | federal_tax_withheld | Decimal(12,2) | |
| STATE_TAX | state_tax_withheld | Decimal(12,2) | |
| SOC_SEC | social_security_withheld | Decimal(12,2) | |
| MEDICARE | medicare_withheld | Decimal(12,2) | |
| PERIOD_START | pay_period_start | Date format | |
| PERIOD_END | pay_period_end | Date format | |

### Hours and Earnings

| Legacy Field | AuraConnect Field | Transformation | Notes |
|-------------|-------------------|----------------|-------|
| REG_HOURS | regular_hours | Decimal(6,2) | |
| OT_HOURS | overtime_hours | Decimal(6,2) | |
| DT_HOURS | double_time_hours | Decimal(6,2) | Optional |
| SICK_HOURS | sick_hours_used | Decimal(6,2) | |
| VAC_HOURS | vacation_hours_used | Decimal(6,2) | |
| BONUS | bonus_amount | Decimal(12,2) | |
| COMMISSION | commission_amount | Decimal(12,2) | |

## Transformation Functions

### Data Type Conversions

```python
def transform_date(date_str: str, format: str = '%Y%m%d') -> date:
    """Convert various date formats to ISO format."""
    if not date_str or date_str == '00000000':
        return None
    
    # Handle common formats
    formats = [
        '%Y%m%d',      # 20240115
        '%m/%d/%Y',    # 01/15/2024
        '%Y-%m-%d',    # 2024-01-15
        '%d-%b-%Y',    # 15-JAN-2024
        '%m%d%Y'       # 01152024
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {date_str}")

def transform_decimal(value: Any, precision: int = 2) -> Decimal:
    """Convert to Decimal with proper precision."""
    if not value or str(value).upper() in ('NULL', 'NONE', ''):
        return Decimal('0.00')
    
    # Clean the value
    cleaned = str(value).replace('$', '').replace(',', '').strip()
    
    try:
        decimal_value = Decimal(cleaned)
        return decimal_value.quantize(Decimal(f'0.{"0" * precision}'))
    except InvalidOperation:
        return Decimal('0.00')

def transform_boolean(value: Any) -> bool:
    """Convert various boolean representations."""
    if isinstance(value, bool):
        return value
    
    true_values = {'Y', 'YES', '1', 'T', 'TRUE', 'X'}
    false_values = {'N', 'NO', '0', 'F', 'FALSE', ''}
    
    str_value = str(value).upper().strip()
    
    if str_value in true_values:
        return True
    elif str_value in false_values:
        return False
    else:
        raise ValueError(f"Unable to parse boolean: {value}")
```

### Name Formatting

```python
def transform_name(name: str) -> str:
    """Clean and format names."""
    if not name:
        return ''
    
    # Remove extra whitespace
    cleaned = ' '.join(name.split())
    
    # Handle special characters
    cleaned = cleaned.replace('  ', ' ')
    
    # Proper case (with special handling)
    words = cleaned.split()
    formatted_words = []
    
    for word in words:
        if word.upper() in ['II', 'III', 'IV', 'JR', 'SR']:
            formatted_words.append(word.upper())
        elif "'" in word:  # Handle O'Brien, D'Angelo
            parts = word.split("'")
            formatted_words.append("'".join(p.capitalize() for p in parts))
        elif "-" in word:  # Handle Smith-Jones
            parts = word.split("-")
            formatted_words.append("-".join(p.capitalize() for p in parts))
        else:
            formatted_words.append(word.capitalize())
    
    return ' '.join(formatted_words)
```

### SSN Handling

```python
def transform_ssn(ssn: str) -> str:
    """Clean and validate SSN."""
    if not ssn:
        return None
    
    # Remove all non-digits
    cleaned = ''.join(filter(str.isdigit, str(ssn)))
    
    # Validate length
    if len(cleaned) != 9:
        raise ValueError(f"Invalid SSN length: {len(cleaned)}")
    
    # Validate not all zeros
    if cleaned == '000000000':
        raise ValueError("Invalid SSN: all zeros")
    
    # Validate format rules
    if cleaned[:3] == '000' or cleaned[3:5] == '00' or cleaned[5:] == '0000':
        raise ValueError("Invalid SSN format")
    
    # Format as XXX-XX-XXXX for display (encrypt for storage)
    return f"{cleaned[:3]}-{cleaned[3:5]}-{cleaned[5:]}"
```

## Validation Rules

### Required Fields Validation

```python
REQUIRED_FIELDS = {
    'employee': [
        'employee_code',
        'first_name',
        'last_name',
        'hire_date',
        'employment_status'
    ],
    'compensation': [
        'employee_id',
        'pay_type',
        'pay_schedule',
        'effective_date'
    ],
    'tax_info': [
        'employee_id',
        'federal_filing_status',
        'state',
        'state_filing_status'
    ]
}

def validate_required_fields(record: dict, record_type: str) -> List[str]:
    """Validate required fields are present and not empty."""
    errors = []
    required = REQUIRED_FIELDS.get(record_type, [])
    
    for field in required:
        if field not in record or not record[field]:
            errors.append(f"Missing required field: {field}")
    
    return errors
```

### Business Rules Validation

```python
def validate_business_rules(record: dict) -> List[str]:
    """Validate business rules."""
    errors = []
    
    # Hire date validation
    if 'hire_date' in record and 'termination_date' in record:
        if record['termination_date'] and record['hire_date'] > record['termination_date']:
            errors.append("Termination date cannot be before hire date")
    
    # Pay rate validation
    if record.get('pay_type') == 'hourly':
        if not record.get('hourly_rate') or record['hourly_rate'] <= 0:
            errors.append("Hourly employees must have positive hourly rate")
    elif record.get('pay_type') == 'salary':
        if not record.get('annual_salary') or record['annual_salary'] <= 0:
            errors.append("Salaried employees must have positive annual salary")
    
    # Tax withholding validation
    if record.get('is_exempt_federal') and record.get('federal_allowances', 0) > 0:
        errors.append("Exempt employees should not have allowances")
    
    return errors
```

## Data Quality Checks

### Duplicate Detection

```python
def check_duplicates(records: List[dict], key_field: str) -> List[dict]:
    """Identify duplicate records."""
    seen = {}
    duplicates = []
    
    for record in records:
        key = record.get(key_field)
        if key in seen:
            duplicates.append({
                'key': key,
                'first_occurrence': seen[key],
                'duplicate_record': record
            })
        else:
            seen[key] = record
    
    return duplicates
```

### Data Completeness

```python
def calculate_completeness(records: List[dict]) -> dict:
    """Calculate data completeness metrics."""
    total_records = len(records)
    field_completeness = {}
    
    if not records:
        return {}
    
    # Check each field
    all_fields = set()
    for record in records:
        all_fields.update(record.keys())
    
    for field in all_fields:
        populated = sum(1 for r in records if r.get(field))
        field_completeness[field] = {
            'populated': populated,
            'total': total_records,
            'percentage': (populated / total_records) * 100
        }
    
    return field_completeness
```

## Related Documentation

- [Migration Overview](overview.md)
- [System-Specific Guides](system-specific.md)
- [Validation Procedures](validation.md)
- [Migration Scripts](/scripts/migration/)