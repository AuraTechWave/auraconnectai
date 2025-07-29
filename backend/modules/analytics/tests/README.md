# Analytics Module Test Suite

This directory contains comprehensive tests for the Analytics module, including performance tests and negative test cases as requested in the user feedback.

## Test Structure

### Core Tests
- `test_sales_report_service.py` - Tests for the main sales reporting service
- `test_analytics_api.py` - API endpoint tests with authentication and validation
- `conftest.py` - Test fixtures and shared test data

### Performance & Load Tests
- `test_performance.py` - Performance tests for large datasets and concurrent operations
- `test_load_testing.py` - Load testing and stress testing for high concurrent usage
- `test_negative_cases.py` - Negative test cases and edge condition handling

## Performance Tests

The performance test suite includes:

### Large Dataset Performance
- Tests with 10,000+ analytics snapshots
- Measures query execution times under load
- Validates memory usage patterns
- Tests pagination with large page sizes

### Concurrent User Simulation
- Tests 5-50 concurrent users
- Mixed workload simulation (40% summaries, 30% detailed reports, etc.)
- Database connection pool stress testing
- Thread safety validation

### Async Task Processing
- High-load async task submission (200+ tasks)
- Task completion rate monitoring
- Memory leak detection
- Queue performance under stress

### Key Performance Metrics
- Sales summary generation: < 2 seconds
- Detailed reports (5000 records): < 5 seconds
- Trend calculations: < 1.5 seconds
- Export operations: < 5 seconds for large datasets
- Concurrent operations: 95%+ success rate

## Negative Test Cases

The negative test suite covers:

### Input Validation
- Invalid date ranges (future dates, reverse ranges)
- Malformed filter parameters
- Boundary condition testing
- Data type validation errors

### Error Handling
- Database connection failures
- Missing/corrupted data scenarios
- Memory exhaustion conditions
- Timeout handling

### Security & Permissions
- Unauthorized access attempts
- Permission boundary testing
- Data filtering based on user roles
- Export format restrictions

### Resource Management
- Memory pressure scenarios
- File system errors
- Network timeout handling
- Graceful degradation testing

## Load Testing

The load testing suite includes:

### Concurrent Operations
- 25-100 simultaneous users
- Mixed operation patterns
- Database connection pooling stress
- Memory usage monitoring

### Stress Testing
- Extreme date ranges (5+ years)
- Maximum pagination limits
- High-frequency task submissions
- Resource exhaustion scenarios

### Performance Benchmarks
- Response time distribution analysis
- Throughput measurements
- Resource utilization tracking
- Scalability limit identification

## Running the Tests

### Full Test Suite
```bash
pytest backend/modules/analytics/tests/
```

### Performance Tests Only
```bash
pytest backend/modules/analytics/tests/test_performance.py -v
```

### Load Tests (Long Running)
```bash
pytest backend/modules/analytics/tests/test_load_testing.py -v -s
```

### Negative Cases
```bash
pytest backend/modules/analytics/tests/test_negative_cases.py -v
```

### With Coverage
```bash
pytest backend/modules/analytics/tests/ --cov=backend.modules.analytics --cov-report=html
```

## Test Configuration

### Environment Variables
- `TEST_DATABASE_URL` - Test database connection
- `REDIS_URL` - Redis connection for caching tests
- `MAX_TEST_WORKERS` - Maximum concurrent test workers

### Performance Test Settings
- Large dataset size: 10,000 records (configurable)
- Concurrent user simulation: 5-50 users
- Load test duration: 30-60 seconds
- Memory monitoring interval: 1 second

### Assertions & Thresholds
- Query performance: < 2s for standard operations
- Memory growth: < 100MB during sustained load
- Success rate: > 95% under normal load, > 85% under stress
- Concurrent user support: 50+ users with acceptable response times

## Test Data Management

### Fixtures
- `performance_test_data` - Large dataset for performance testing
- `mock_user_with_permissions` - User with specific analytics permissions
- `mock_admin_user` - Administrative user with all permissions
- `mock_limited_user` - Restricted user for negative testing

### Data Generation
- Realistic sales data patterns
- Time-series data across multiple periods
- Staff and product performance variations
- Category-based analytics snapshots

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

### Fast Tests (< 30 seconds)
- Unit tests and API tests
- Basic performance validation
- Negative case handling

### Extended Tests (< 5 minutes)
- Load testing with moderate concurrency
- Large dataset performance tests
- Memory usage validation

### Stress Tests (Optional)
- High concurrency load tests
- Extended duration stress tests
- Resource exhaustion scenarios

## Troubleshooting

### Common Issues
1. **Slow performance tests**: Reduce dataset size or concurrent users
2. **Memory errors**: Increase test environment memory allocation
3. **Database timeouts**: Check connection pool configuration
4. **Assertion failures**: Review performance thresholds for your environment

### Performance Tuning
- Adjust test thresholds based on hardware capabilities
- Scale concurrent user counts based on database capacity
- Monitor test database performance during execution
- Consider test data cleanup between runs

## Contributing

When adding new tests:

1. Follow existing naming conventions
2. Include docstrings explaining test purpose
3. Add appropriate fixtures for test data
4. Consider both positive and negative scenarios
5. Include performance considerations for new features
6. Update this README for significant test additions