# System-Specific Migration Guides

This document provides detailed migration instructions for specific legacy payroll systems.

## ADP to AuraConnect

### ADP System Overview

ADP Workforce Now typically stores data in:
- Oracle or SQL Server databases
- CSV export files
- API endpoints (if enabled)

### ADP Field Mappings

```python
ADP_FIELD_MAPPING = {
    # Employee Information
    'AssociateID': 'employee_code',
    'FirstName': 'first_name',
    'LastName': 'last_name',
    'MiddleName': 'middle_name',
    'TaxID': 'ssn_encrypted',
    'BirthDate': 'date_of_birth',
    'HireDate': 'hire_date',
    'TerminationDate': 'termination_date',
    'AssociateStatus': 'employment_status',
    'HomeDepartment': 'department',
    'WorkLocation': 'location',
    
    # Compensation
    'PayRate': 'base_rate',
    'PayFrequency': 'pay_schedule',
    'SalaryFlag': 'pay_type',
    'AnnualSalary': 'annual_salary',
    'HourlyRate': 'hourly_rate',
    
    # Tax Information
    'FederalFilingStatus': 'federal_filing_status',
    'FederalAllowances': 'federal_allowances',
    'StateFilingStatus': 'state_filing_status',
    'StateAllowances': 'state_allowances'
}

# ADP Status Mapping
ADP_STATUS_MAPPING = {
    'Active': 'active',
    'Terminated': 'terminated',
    'Leave of Absence': 'leave',
    'Suspended': 'suspended'
}
```

### ADP Data Extraction

```python
class ADPMigration:
    """ADP-specific migration handler."""
    
    def connect_to_adp_db(self):
        """Connect to ADP database."""
        connection_string = (
            f"Driver={{ODBC Driver 17 for SQL Server}};"
            f"Server={self.config['server']};"
            f"Database={self.config['database']};"
            f"UID={self.config['username']};"
            f"PWD={self.config['password']}"
        )
        return pyodbc.connect(connection_string)
    
    def extract_employees(self):
        """Extract employee data from ADP."""
        query = """
        SELECT 
            a.AssociateID,
            a.FirstName,
            a.LastName,
            a.MiddleName,
            a.TaxID,
            a.BirthDate,
            a.HireDate,
            a.TerminationDate,
            a.AssociateStatus,
            d.DepartmentName as HomeDepartment,
            l.LocationCode as WorkLocation,
            c.PayRate,
            c.PayFrequency,
            c.SalaryFlag,
            c.AnnualSalary,
            c.HourlyRate
        FROM Associates a
        LEFT JOIN Departments d ON a.DepartmentID = d.DepartmentID
        LEFT JOIN Locations l ON a.LocationID = l.LocationID
        LEFT JOIN Compensation c ON a.AssociateID = c.AssociateID
        WHERE a.AssociateStatus IN ('Active', 'Leave of Absence')
        """
        
        df = pd.read_sql(query, self.connection)
        return self.transform_adp_data(df)
    
    def extract_from_api(self):
        """Extract data using ADP API."""
        headers = {
            'Authorization': f'Bearer {self.get_adp_token()}',
            'Content-Type': 'application/json'
        }
        
        # Get workers
        response = requests.get(
            'https://api.adp.com/hr/v2/workers',
            headers=headers
        )
        
        workers = response.json()['workers']
        return self.transform_api_data(workers)
```

### ADP-Specific Considerations

1. **Multi-Company Setup**: ADP may have multiple company codes
2. **Pay Groups**: Map ADP pay groups to AuraConnect schedules
3. **Deduction Codes**: ADP uses numeric codes that need mapping
4. **Time & Attendance**: May need separate extraction from ADP Time

## Paychex to AuraConnect

### Paychex System Overview

Paychex Flex typically provides data through:
- CSV/Excel exports
- API access (Paychex Flex API)
- Report downloads

### Paychex Field Mappings

```python
PAYCHEX_FIELD_MAPPING = {
    # Employee Information
    'Employee ID': 'employee_code',
    'First Name': 'first_name',
    'Last Name': 'last_name',
    'Social Security': 'ssn_encrypted',
    'Date of Birth': 'date_of_birth',
    'Hire Date': 'hire_date',
    'Status': 'employment_status',
    'Department': 'department',
    'Location': 'location',
    
    # Compensation
    'Annual Salary': 'annual_salary',
    'Hourly Rate': 'hourly_rate',
    'Pay Frequency': 'pay_schedule',
    'Employee Type': 'pay_type',
    
    # Tax Setup
    'Federal Status': 'federal_filing_status',
    'Federal Exemptions': 'federal_allowances',
    'State': 'state',
    'State Status': 'state_filing_status',
    'State Exemptions': 'state_allowances'
}

# Paychex Pay Frequency Mapping
PAYCHEX_FREQUENCY_MAPPING = {
    'Weekly': 'weekly',
    'Bi-Weekly': 'biweekly',
    'Semi-Monthly': 'semimonthly',
    'Monthly': 'monthly'
}
```

### Paychex Data Extraction

```python
class PaychexMigration:
    """Paychex-specific migration handler."""
    
    def extract_from_export_file(self, file_path: str):
        """Extract from Paychex export files."""
        # Paychex exports are typically Excel files
        df = pd.read_excel(
            file_path,
            sheet_name='Employee Data',
            dtype={
                'Employee ID': str,
                'Social Security': str,
                'Zip Code': str
            }
        )
        
        # Clean column names (remove extra spaces)
        df.columns = df.columns.str.strip()
        
        # Apply mappings
        df_mapped = df.rename(columns=PAYCHEX_FIELD_MAPPING)
        
        # Transform specific fields
        df_mapped['pay_schedule'] = df_mapped['pay_schedule'].map(
            PAYCHEX_FREQUENCY_MAPPING
        )
        
        return df_mapped
    
    def extract_ytd_from_report(self, report_path: str):
        """Extract YTD data from Paychex reports."""
        # Paychex YTD reports have specific format
        df = pd.read_csv(
            report_path,
            skiprows=3,  # Skip header rows
            usecols=[
                'Employee ID',
                'YTD Gross',
                'YTD Federal Tax',
                'YTD State Tax',
                'YTD Social Security',
                'YTD Medicare'
            ]
        )
        
        return df
```

### Paychex-Specific Considerations

1. **Report Formats**: Different reports have different layouts
2. **Multi-State**: Handle employees working in multiple states
3. **Check History**: May need to parse check register reports
4. **Benefits**: Benefit data often in separate reports

## QuickBooks Payroll to AuraConnect

### QuickBooks Overview

QuickBooks Desktop and Online have different data access methods:
- Desktop: Direct database access or IIF exports
- Online: API access or CSV exports

### QuickBooks Field Mappings

```python
QUICKBOOKS_FIELD_MAPPING = {
    # Employee Information
    'Employee': 'full_name',  # Need to split
    'SSN': 'ssn_encrypted',
    'Birth Date': 'date_of_birth',
    'Hire Date': 'hire_date',
    'Release Date': 'termination_date',
    'Employee Status': 'employment_status',
    
    # Payroll Info
    'Pay Period': 'pay_schedule',
    'Salary': 'annual_salary',
    'Hourly Rate': 'hourly_rate',
    'Regular Pay': 'regular_pay',
    'Overtime Pay': 'overtime_pay'
}

# QuickBooks Status Mapping
QB_STATUS_MAPPING = {
    'Active': 'active',
    'Inactive': 'terminated',
    'Not on Payroll': 'inactive'
}
```

### QuickBooks Data Extraction

```python
class QuickBooksMigration:
    """QuickBooks-specific migration handler."""
    
    def extract_from_qb_online(self):
        """Extract using QuickBooks Online API."""
        from quickbooks import QuickBooks
        from quickbooks.objects import Employee
        
        client = QuickBooks(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret'],
            refresh_token=self.config['refresh_token'],
            company_id=self.config['company_id']
        )
        
        # Get all employees
        employees = Employee.all(qb=client)
        
        employee_data = []
        for emp in employees:
            # Parse name
            first_name, last_name = self.parse_employee_name(
                emp.GivenName, 
                emp.FamilyName,
                emp.DisplayName
            )
            
            employee_data.append({
                'employee_code': emp.Id,
                'first_name': first_name,
                'last_name': last_name,
                'ssn_encrypted': self.encrypt_ssn(emp.SSN),
                'hire_date': emp.HiredDate,
                'employment_status': 'active' if emp.Active else 'terminated',
                'email': emp.PrimaryEmailAddr.Address if emp.PrimaryEmailAddr else None
            })
        
        return pd.DataFrame(employee_data)
    
    def extract_from_iif_file(self, file_path: str):
        """Extract from QuickBooks IIF export."""
        # IIF files are tab-delimited
        tables = {}
        current_table = None
        
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith('!'):
                    # Table header
                    parts = line.strip().split('\t')
                    current_table = parts[0][1:]  # Remove !
                    tables[current_table] = {'headers': parts[1:], 'data': []}
                elif current_table:
                    # Data row
                    parts = line.strip().split('\t')
                    if parts[0] == current_table:
                        tables[current_table]['data'].append(parts[1:])
        
        # Convert to DataFrames
        dfs = {}
        for table_name, table_data in tables.items():
            if table_data['data']:
                df = pd.DataFrame(
                    table_data['data'],
                    columns=table_data['headers']
                )
                dfs[table_name] = df
        
        return dfs
```

### QuickBooks-Specific Considerations

1. **Name Parsing**: Full names need to be split
2. **Limited Tax Info**: May need manual tax setup
3. **Payroll Items**: Map QB payroll items to deductions
4. **Classes/Locations**: Map to departments/locations

## SAP SuccessFactors to AuraConnect

### SuccessFactors Overview

SAP SuccessFactors Employee Central Payroll:
- OData API access
- CSV exports via Report Center
- Integration Center extracts

### SuccessFactors Field Mappings

```python
SUCCESSFACTORS_FIELD_MAPPING = {
    # Person Information
    'userId': 'employee_code',
    'firstName': 'first_name',
    'lastName': 'last_name',
    'middleName': 'middle_name',
    'nationalId': 'ssn_encrypted',
    'dateOfBirth': 'date_of_birth',
    
    # Employment Information
    'startDate': 'hire_date',
    'endDate': 'termination_date',
    'employmentStatus': 'employment_status',
    'department': 'department',
    'location': 'location',
    
    # Compensation
    'payType': 'pay_type',
    'payFrequency': 'pay_schedule',
    'annualSalary': 'annual_salary',
    'hourlyRate': 'hourly_rate'
}
```

### SuccessFactors Data Extraction

```python
class SuccessFactorsMigration:
    """SAP SuccessFactors migration handler."""
    
    def extract_via_odata(self):
        """Extract using OData API."""
        base_url = f"https://{self.config['api_server']}/odata/v2"
        
        headers = {
            'Authorization': f'Basic {self.get_auth_token()}',
            'Accept': 'application/json'
        }
        
        # Get employees with employment details
        endpoint = f"{base_url}/User"
        params = {
            '$select': 'userId,firstName,lastName,email',
            '$expand': 'empEmploymentNav,empCompensationNav',
            '$filter': "status eq 'active'"
        }
        
        response = requests.get(endpoint, headers=headers, params=params)
        employees = response.json()['d']['results']
        
        return self.transform_sf_data(employees)
```

## Workday to AuraConnect

### Workday Overview

Workday HCM provides:
- REST/SOAP APIs
- Report-as-a-Service (RaaS)
- Core Connector integrations

### Workday Field Mappings

```python
WORKDAY_FIELD_MAPPING = {
    # Worker Information
    'Employee_ID': 'employee_code',
    'Legal_First_Name': 'first_name',
    'Legal_Last_Name': 'last_name',
    'Social_Security_Number': 'ssn_encrypted',
    'Birth_Date': 'date_of_birth',
    'Original_Hire_Date': 'hire_date',
    'Termination_Date': 'termination_date',
    'Worker_Status': 'employment_status',
    
    # Organization
    'Cost_Center': 'department',
    'Work_Location': 'location',
    
    # Compensation
    'Compensation_Element_Amount': 'base_pay',
    'Frequency': 'pay_schedule',
    'Pay_Rate_Type': 'pay_type'
}
```

### Workday Data Extraction

```python
class WorkdayMigration:
    """Workday-specific migration handler."""
    
    def extract_via_report(self, report_name: str):
        """Extract using Workday Report-as-a-Service."""
        import zeep
        
        # Create SOAP client
        wsdl = f"https://{self.config['tenant']}.workday.com/ccx/service/customreport2/{self.config['tenant']}/{report_name}?wsdl"
        
        client = zeep.Client(wsdl=wsdl)
        
        # Set authentication
        client.set_default_soapheaders({
            'Username': self.config['username'],
            'Password': self.config['password']
        })
        
        # Execute report
        response = client.service.Execute_Report()
        
        # Parse response
        return self.parse_workday_xml(response)
```

## Common Migration Challenges

### Data Quality Issues

1. **Inconsistent Formats**
   - Dates in various formats
   - Names with special characters
   - Inconsistent status values

2. **Missing Data**
   - No SSN for some employees
   - Missing hire dates
   - Incomplete tax information

3. **Duplicate Records**
   - Same employee with multiple IDs
   - Terminated employees reappearing
   - Multiple compensation records

### Resolution Strategies

```python
class DataQualityResolver:
    """Handle common data quality issues."""
    
    def resolve_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resolve duplicate employee records."""
        # Sort by hire date and status to keep most recent active
        df_sorted = df.sort_values(
            ['employee_code', 'hire_date', 'employment_status'],
            ascending=[True, False, True]
        )
        
        # Keep first (most recent/active)
        df_deduped = df_sorted.drop_duplicates(
            subset=['employee_code'],
            keep='first'
        )
        
        return df_deduped
    
    def fill_missing_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing required data with defaults."""
        defaults = {
            'middle_name': '',
            'termination_date': None,
            'federal_allowances': 0,
            'state_allowances': 0,
            'additional_federal_withholding': 0.0,
            'additional_state_withholding': 0.0
        }
        
        for field, default_value in defaults.items():
            if field in df.columns:
                df[field] = df[field].fillna(default_value)
        
        return df
```

## Testing System-Specific Migrations

### Test Data Sets

Create test data sets for each system:

```python
def create_test_data(system: str, num_records: int = 100):
    """Create test data mimicking specific system format."""
    
    if system == 'adp':
        return create_adp_test_data(num_records)
    elif system == 'paychex':
        return create_paychex_test_data(num_records)
    elif system == 'quickbooks':
        return create_quickbooks_test_data(num_records)
    # ... etc
```

### Validation Scripts

System-specific validation:

```python
def validate_adp_migration(source_df: pd.DataFrame, target_df: pd.DataFrame):
    """Validate ADP-specific migration rules."""
    validations = []
    
    # Check employee count
    source_count = len(source_df[source_df['AssociateStatus'] == 'Active'])
    target_count = len(target_df[target_df['employment_status'] == 'active'])
    
    validations.append({
        'check': 'Active employee count',
        'source': source_count,
        'target': target_count,
        'match': source_count == target_count
    })
    
    # Check pay frequency mapping
    freq_mapping = source_df.groupby('PayFrequency').size()
    # ... validate mappings
    
    return validations
```

## Related Documentation

- [Migration Overview](overview.md)
- [Data Mapping Guide](data-mapping.md)
- [Validation Procedures](validation.md)
- [Legacy System Scripts](/scripts/migration/systems/)