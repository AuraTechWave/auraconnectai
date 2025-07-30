# Payroll Module Test Suite

Comprehensive testing suite for the AuraConnect Payroll & Tax Module (Phase 5: Testing - AUR-307).

## Overview

This test suite provides complete coverage for the payroll module, including:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test interactions between components
- **End-to-End Tests**: Test complete workflows from start to finish
- **Performance Tests**: Measure and validate system performance
- **Test Fixtures**: Reusable test data and mock objects

## Test Structure

```
tests/
├── conftest.py                      # Pytest fixtures and factories
├── pytest.ini                       # Pytest configuration
├── .coveragerc                      # Coverage configuration
├── run_tests.sh                     # Test runner script
├── README.md                        # This file
│
├── test_payroll_configuration_service.py  # Unit tests for configuration service
├── test_payment_export_service.py         # Unit tests for export service
├── test_batch_payroll_service.py          # Unit tests for batch processing
├── test_payroll_tax_service.py            # Unit tests for tax service
├── test_payroll_tax_engine.py             # Unit tests for tax engine
│
├── test_tax_integration.py          # Integration tests for tax calculations
├── test_payroll_e2e.py             # End-to-end workflow tests
├── test_payroll_performance.py      # Performance and load tests
│
├── test_audit_logs.py              # Functional tests for audit logging
├── test_batch_processing.py         # Functional tests for batch API
├── test_webhooks.py                # Functional tests for webhooks
├── test_payroll_routes.py          # API route tests
├── test_payroll_models_validation.py # Model validation tests
└── test_v1_imports.py              # Import verification tests
```

## Running Tests

### Quick Start

```bash
# Run all tests with coverage
./tests/run_tests.sh

# Run only unit tests
./tests/run_tests.sh --unit

# Run tests without coverage report
./tests/run_tests.sh --no-coverage

# Run with verbose output
./tests/run_tests.sh --verbose
```

### Using Pytest Directly

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_payroll_configuration_service.py

# Run tests matching pattern
pytest tests/ -k "test_calculate_federal_tax"

# Run with specific marker
pytest tests/ -m unit
pytest tests/ -m integration
pytest tests/ -m performance

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Markers

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.smoke` - Quick smoke tests

## Test Coverage

### Coverage Goals

- **Overall Coverage**: 90%+
- **Critical Components**: 95%+
  - Tax calculations
  - Payment processing
  - Batch operations

### Viewing Coverage Reports

After running tests with coverage:

1. **Terminal Report**: Displayed after test run
2. **HTML Report**: Open `tests/htmlcov/index.html` in browser
3. **XML Report**: `coverage.xml` for CI/CD integration

### Coverage Configuration

Coverage settings are defined in `.coveragerc`:

- Excludes test files, migrations, and virtual environments
- Reports missing lines
- Shows branch coverage
- Generates HTML, XML, and JSON reports

## Writing Tests

### Using Test Fixtures

```python
def test_employee_payroll(employee_factory, payment_factory, sample_pay_period):
    # Create test employee
    employee = employee_factory(
        name="John Doe",
        employment_type="salaried",
        annual_salary=Decimal("75000.00")
    )
    
    # Create payment
    payment = payment_factory(
        employee_id=employee.id,
        pay_period_start=sample_pay_period["start"],
        pay_period_end=sample_pay_period["end"],
        gross_pay=Decimal("2884.62")  # Bi-weekly salary
    )
    
    assert payment.net_pay > Decimal("2000.00")
```

### Available Fixtures

- `mock_db_session` - Mock database session
- `employee_factory` - Create test employees
- `timesheet_factory` - Create test timesheets
- `payment_factory` - Create test payments
- `pay_policy_factory` - Create pay policies
- `overtime_rule_factory` - Create overtime rules
- `batch_job_factory` - Create batch jobs
- `sample_pay_period` - Standard pay period dates
- `sample_calculation_options` - Standard calculation options
- `tax_brackets_2024` - Federal tax brackets
- `california_tax_brackets` - State tax brackets

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_calculation(service):
    result = await service.calculate_payroll(
        employee_id=1,
        pay_period_start=date(2024, 1, 1),
        pay_period_end=date(2024, 1, 14)
    )
    assert result.gross_pay > Decimal("0.00")
```

## Performance Testing

### Running Performance Tests

```bash
# Run all performance tests
./tests/run_tests.sh --performance

# Run specific performance test
pytest tests/test_payroll_performance.py::test_batch_processing_1000_employees -v
```

### Performance Metrics

Performance tests measure:

- **Throughput**: Employees processed per second
- **Latency**: Time per employee calculation
- **Scalability**: Performance with increasing load
- **Memory Usage**: Memory consumption patterns
- **Concurrency**: Parallel processing efficiency

### Performance Benchmarks

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Single payroll calculation | < 50ms | Per employee |
| Batch processing (100) | < 5s | Total time |
| Batch processing (1000) | < 30s | Total time |
| Export (1000 records) | < 5s | Per format |
| Concurrent batches (5) | > 2x speedup | vs sequential |

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run Payroll Tests
  run: |
    cd backend/modules/payroll
    ./tests/run_tests.sh
    
- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./backend/modules/payroll/coverage.xml
    flags: payroll
```

### Pre-commit Hooks

```yaml
- repo: local
  hooks:
    - id: payroll-tests
      name: Payroll Tests
      entry: backend/modules/payroll/tests/run_tests.sh --unit
      language: system
      pass_filenames: false
      files: ^backend/modules/payroll/
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure you're in the correct directory
   cd backend/modules/payroll
   
   # Install dependencies
   pip install -r requirements-test.txt
   ```

2. **Async Test Failures**
   ```python
   # Ensure test is marked as async
   @pytest.mark.asyncio
   async def test_async_function():
       ...
   ```

3. **Database Mock Issues**
   ```python
   # Use the provided mock_db_session fixture
   def test_with_db(mock_db_session):
       service = PayrollService(mock_db_session)
       ...
   ```

### Debug Mode

```bash
# Run with full traceback
pytest tests/ --tb=long

# Run with pdb on failure
pytest tests/ --pdb

# Run specific test with print statements
pytest tests/test_file.py::test_function -s
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Use Fixtures**: Leverage provided fixtures for consistency
3. **Mock External Dependencies**: Don't make real API/DB calls
4. **Test Edge Cases**: Include boundary and error conditions
5. **Clear Test Names**: Describe what is being tested
6. **Arrange-Act-Assert**: Structure tests clearly

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all tests pass
3. Maintain or improve coverage
4. Update this README if adding new test categories

## Test Data

### Standard Test Scenarios

1. **Single Employee** - Basic calculation
2. **Hourly with Overtime** - Complex hours calculation
3. **Multi-State** - Cross-jurisdiction taxes
4. **Year-End** - W-2 and annual summaries
5. **Corrections** - Payment adjustments
6. **Garnishments** - Wage deductions

### Performance Test Data

- **Small Batch**: 10-50 employees
- **Medium Batch**: 100-500 employees
- **Large Batch**: 1000+ employees
- **Concurrent**: Multiple departments

## Maintenance

### Regular Tasks

1. **Update Tax Brackets**: Annual tax table updates
2. **Performance Baselines**: Re-baseline after optimizations
3. **Coverage Review**: Quarterly coverage analysis
4. **Fixture Updates**: Keep test data current

### Version Compatibility

- Python: 3.8+
- Pytest: 7.0+
- Coverage: 6.0+
- AsyncIO: Python 3.7+