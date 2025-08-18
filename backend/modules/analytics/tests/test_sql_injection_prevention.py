"""
Tests for SQL injection prevention measures.
"""

import pytest
from datetime import date
from modules.analytics.services.secure_query_builder import SecureQueryBuilder, TimeGranularity
from modules.analytics.utils.input_sanitizer import InputSanitizer


class TestSecureQueryBuilder:
    """Test secure query building functionality"""
    
    def test_product_demand_query_parameterized(self):
        """Test that product demand query uses parameters"""
        query, params = SecureQueryBuilder.build_product_demand_query(
            TimeGranularity.DAILY
        )
        
        # Check query uses parameter placeholders
        assert ":product_id" in query
        assert ":start_date" in query
        assert ":end_date" in query
        assert ":date_trunc" in query
        
        # Check no direct string formatting
        assert "{" not in query
        assert "%" not in query
        
        # Check params are properly set
        assert params["date_trunc"] == "day"
    
    def test_category_demand_query_parameterized(self):
        """Test that category demand query uses parameters"""
        query, params = SecureQueryBuilder.build_category_demand_query(
            TimeGranularity.WEEKLY
        )
        
        # Check query uses parameter placeholders
        assert ":category_id" in query
        assert ":start_date" in query
        assert ":end_date" in query
        assert ":date_trunc" in query
        
        # Check params are properly set
        assert params["date_trunc"] == "week"
    
    def test_overall_demand_query_parameterized(self):
        """Test that overall demand query uses parameters"""
        query, params = SecureQueryBuilder.build_overall_demand_query(
            TimeGranularity.MONTHLY
        )
        
        # Check query uses parameter placeholders
        assert ":start_date" in query
        assert ":end_date" in query
        assert ":date_trunc" in query
        
        # Check params are properly set
        assert params["date_trunc"] == "month"
    
    def test_sales_metrics_query_with_filters(self):
        """Test sales metrics query with various filters"""
        filters = {
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 12, 31),
            "status": ["completed", "pending"],
            "location_id": 123,
            "limit": 100
        }
        
        query, params = SecureQueryBuilder.build_sales_metrics_query(filters)
        
        # Check all filters are parameterized
        assert ":start_date" in query
        assert ":end_date" in query
        assert ":status_list" in query
        assert ":location_id" in query
        assert ":limit" in query
        
        # Check params match filters
        assert params["start_date"] == date(2024, 1, 1)
        assert params["end_date"] == date(2024, 12, 31)
        assert params["status_list"] == ["completed", "pending"]
        assert params["location_id"] == 123
        assert params["limit"] == 100
    
    def test_dynamic_aggregation_query_validation(self):
        """Test dynamic aggregation query with validation"""
        aggregations = [
            {"function": "SUM", "column": "total_amount", "alias": "revenue"},
            {"function": "COUNT", "column": "id", "alias": "order_count"}
        ]
        filters = {"status": "completed", "location_id": 1}
        group_by = ["customer_id", "date"]
        
        query, params = SecureQueryBuilder.build_dynamic_aggregation_query(
            "orders", aggregations, filters, group_by
        )
        
        # Check query structure
        assert "SUM(total_amount) as revenue" in query
        assert "COUNT(id) as order_count" in query
        assert "GROUP BY customer_id, date" in query
        
        # Check parameterized filters
        assert ":filter_status" in query
        assert ":filter_location_id" in query
        assert params["filter_status"] == "completed"
        assert params["filter_location_id"] == 1
    
    def test_invalid_table_name_rejected(self):
        """Test that invalid table names are rejected"""
        with pytest.raises(ValueError, match="Table.*not allowed"):
            SecureQueryBuilder.build_dynamic_aggregation_query(
                "users; DROP TABLE orders;--",
                [], {}, []
            )
    
    def test_invalid_aggregation_function_rejected(self):
        """Test that invalid aggregation functions are rejected"""
        with pytest.raises(ValueError, match="Aggregation function.*not allowed"):
            SecureQueryBuilder.build_dynamic_aggregation_query(
                "orders",
                [{"function": "EXEC", "column": "id", "alias": "test"}],
                {}, []
            )
    
    def test_invalid_column_name_rejected(self):
        """Test that invalid column names are rejected"""
        with pytest.raises(ValueError, match="Invalid column name"):
            SecureQueryBuilder.build_dynamic_aggregation_query(
                "orders",
                [{"function": "SUM", "column": "amount; DROP TABLE--", "alias": "test"}],
                {}, []
            )


class TestInputSanitizer:
    """Test input sanitization functionality"""
    
    def test_sanitize_string_removes_sql_keywords(self):
        """Test that SQL keywords are detected and rejected"""
        with pytest.raises(ValueError, match="forbidden keyword"):
            InputSanitizer.sanitize_string("SELECT * FROM users")
    
    def test_sanitize_string_removes_special_chars(self):
        """Test that special characters are removed"""
        result = InputSanitizer.sanitize_string(
            "Hello<script>alert('xss')</script>World", 
            allow_spaces=True
        )
        assert result == "HelloscriptalertxssscriptWorld"
    
    def test_validate_identifier_accepts_valid(self):
        """Test that valid identifiers are accepted"""
        assert InputSanitizer.validate_identifier("user_id") == "user_id"
        assert InputSanitizer.validate_identifier("OrderItems") == "orderitems"
    
    def test_validate_identifier_rejects_invalid(self):
        """Test that invalid identifiers are rejected"""
        with pytest.raises(ValueError):
            InputSanitizer.validate_identifier("123invalid")
        
        with pytest.raises(ValueError):
            InputSanitizer.validate_identifier("user-id")
        
        with pytest.raises(ValueError):
            InputSanitizer.validate_identifier("SELECT")
    
    def test_validate_numeric_accepts_valid(self):
        """Test numeric validation"""
        assert InputSanitizer.validate_numeric(42) == 42.0
        assert InputSanitizer.validate_numeric("3.14") == 3.14
        assert InputSanitizer.validate_numeric(-10, min_value=-100) == -10.0
    
    def test_validate_numeric_rejects_invalid(self):
        """Test numeric validation rejects invalid input"""
        with pytest.raises(ValueError):
            InputSanitizer.validate_numeric("not a number")
        
        with pytest.raises(ValueError):
            InputSanitizer.validate_numeric(5, max_value=4)
    
    def test_validate_date_accepts_valid(self):
        """Test date validation"""
        test_date = date(2024, 1, 1)
        assert InputSanitizer.validate_date(test_date) == test_date
        assert InputSanitizer.validate_date("2024-01-01") == test_date
    
    def test_validate_date_rejects_invalid(self):
        """Test date validation rejects invalid input"""
        with pytest.raises(ValueError):
            InputSanitizer.validate_date("2024/01/01")
        
        with pytest.raises(ValueError):
            InputSanitizer.validate_date("invalid-date")
    
    def test_validate_enum(self):
        """Test enum validation"""
        allowed = ["active", "inactive", "pending"]
        assert InputSanitizer.validate_enum("active", allowed) == "active"
        
        with pytest.raises(ValueError):
            InputSanitizer.validate_enum("deleted", allowed)
    
    def test_sanitize_order_by(self):
        """Test ORDER BY sanitization"""
        allowed_columns = ["created_at", "total_amount", "status"]
        
        col, dir = InputSanitizer.sanitize_order_by(
            "created_at", allowed_columns, "DESC"
        )
        assert col == "created_at"
        assert dir == "DESC"
        
        # Test invalid column
        with pytest.raises(ValueError):
            InputSanitizer.sanitize_order_by("password", allowed_columns)
        
        # Test invalid direction
        with pytest.raises(ValueError):
            InputSanitizer.sanitize_order_by("status", allowed_columns, "RANDOM")
    
    def test_escape_like_pattern(self):
        """Test LIKE pattern escaping"""
        assert InputSanitizer.escape_like_pattern("test%") == "test\\%"
        assert InputSanitizer.escape_like_pattern("_test") == "\\_test"
        assert InputSanitizer.escape_like_pattern("test[123]") == "test\\[123]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])