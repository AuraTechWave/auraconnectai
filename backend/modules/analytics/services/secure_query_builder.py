"""
Secure SQL query builder for analytics services.

This module provides safe query construction methods to prevent SQL injection
vulnerabilities by using parameterized queries instead of string formatting.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import date
from sqlalchemy import text
from enum import Enum


class TimeGranularity(str, Enum):
    """Time granularity options for analytics queries"""
    HOURLY = "hour"
    DAILY = "day"
    WEEKLY = "week"
    MONTHLY = "month"


class SecureQueryBuilder:
    """Builds secure parameterized SQL queries for analytics"""
    
    @staticmethod
    def build_product_demand_query(
        granularity: TimeGranularity
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build parameterized SQL query for product demand data.
        
        Returns:
            Tuple of (query_template, parameters_dict)
        """
        # Use parameterized query with placeholders
        query = """
        SELECT 
            DATE_TRUNC(:date_trunc, o.created_at) as date,
            SUM(oi.quantity) as demand,
            COUNT(DISTINCT o.id) as order_count,
            AVG(oi.unit_price) as avg_price
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE oi.menu_item_id = :product_id
            AND o.created_at >= :start_date
            AND o.created_at <= :end_date
            AND o.status NOT IN ('cancelled', 'failed')
        GROUP BY DATE_TRUNC(:date_trunc, o.created_at)
        ORDER BY date
        """
        
        return query, {"date_trunc": granularity.value}
    
    @staticmethod
    def build_category_demand_query(
        granularity: TimeGranularity
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build parameterized SQL query for category demand data.
        
        Returns:
            Tuple of (query_template, parameters_dict)
        """
        query = """
        SELECT 
            DATE_TRUNC(:date_trunc, o.created_at) as date,
            SUM(oi.quantity) as demand,
            COUNT(DISTINCT o.id) as order_count,
            COUNT(DISTINCT oi.menu_item_id) as product_variety
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN menu_items mi ON oi.menu_item_id = mi.id
        WHERE mi.category_id = :category_id
            AND o.created_at >= :start_date
            AND o.created_at <= :end_date
            AND o.status NOT IN ('cancelled', 'failed')
        GROUP BY DATE_TRUNC(:date_trunc, o.created_at)
        ORDER BY date
        """
        
        return query, {"date_trunc": granularity.value}
    
    @staticmethod
    def build_overall_demand_query(
        granularity: TimeGranularity
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build parameterized SQL query for overall demand data.
        
        Returns:
            Tuple of (query_template, parameters_dict)
        """
        query = """
        SELECT 
            DATE_TRUNC(:date_trunc, created_at) as date,
            COUNT(*) as demand,
            SUM(total_amount) as revenue,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM orders
        WHERE created_at >= :start_date
            AND created_at <= :end_date
            AND status NOT IN ('cancelled', 'failed')
        GROUP BY DATE_TRUNC(:date_trunc, created_at)
        ORDER BY date
        """
        
        return query, {"date_trunc": granularity.value}
    
    @staticmethod
    def build_sales_metrics_query(
        filters: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build secure query for sales metrics with dynamic filters.
        
        Args:
            filters: Dictionary of filter criteria
            
        Returns:
            Tuple of (query_template, parameters_dict)
        """
        # Base query
        query_parts = ["""
        SELECT 
            DATE(o.created_at) as date,
            COUNT(DISTINCT o.id) as order_count,
            SUM(o.total_amount) as revenue,
            COUNT(DISTINCT o.customer_id) as unique_customers,
            AVG(o.total_amount) as avg_order_value
        FROM orders o
        WHERE 1=1
        """]
        
        params = {}
        
        # Add date range filter
        if "start_date" in filters:
            query_parts.append("AND o.created_at >= :start_date")
            params["start_date"] = filters["start_date"]
            
        if "end_date" in filters:
            query_parts.append("AND o.created_at <= :end_date")
            params["end_date"] = filters["end_date"]
        
        # Add status filter
        if "status" in filters:
            if isinstance(filters["status"], list):
                # Use ANY for array parameters
                query_parts.append("AND o.status = ANY(:status_list)")
                params["status_list"] = filters["status"]
            else:
                query_parts.append("AND o.status = :status")
                params["status"] = filters["status"]
        
        # Add location filter
        if "location_id" in filters:
            query_parts.append("AND o.location_id = :location_id")
            params["location_id"] = filters["location_id"]
        
        # Add grouping and ordering
        query_parts.extend([
            "GROUP BY DATE(o.created_at)",
            "ORDER BY date DESC"
        ])
        
        # Add limit if specified
        if "limit" in filters:
            query_parts.append("LIMIT :limit")
            params["limit"] = filters["limit"]
        
        return "\n".join(query_parts), params
    
    @staticmethod
    def build_dynamic_aggregation_query(
        table: str,
        aggregations: List[Dict[str, str]],
        filters: Dict[str, Any],
        group_by: Optional[List[str]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build secure dynamic aggregation query.
        
        Args:
            table: Table name (validated against whitelist)
            aggregations: List of aggregation definitions
            filters: Filter criteria
            group_by: Grouping columns
            
        Returns:
            Tuple of (query_template, parameters_dict)
        """
        # Whitelist of allowed tables
        allowed_tables = {
            "orders", "order_items", "menu_items", 
            "customers", "staff", "inventory"
        }
        
        if table not in allowed_tables:
            raise ValueError(f"Table '{table}' is not allowed")
        
        # Build SELECT clause with validated aggregations
        select_parts = []
        for agg in aggregations:
            func = agg.get("function", "").upper()
            column = agg.get("column", "")
            alias = agg.get("alias", "")
            
            # Validate aggregation function
            allowed_functions = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
            if func not in allowed_functions:
                raise ValueError(f"Aggregation function '{func}' is not allowed")
            
            # Validate column name (alphanumeric + underscore only)
            if not column.replace("_", "").isalnum():
                raise ValueError(f"Invalid column name: {column}")
            
            if not alias.replace("_", "").isalnum():
                raise ValueError(f"Invalid alias: {alias}")
            
            select_parts.append(f"{func}({column}) as {alias}")
        
        # Build WHERE clause
        where_parts = ["1=1"]
        params = {}
        
        for key, value in filters.items():
            # Validate filter key
            if not key.replace("_", "").isalnum():
                raise ValueError(f"Invalid filter key: {key}")
            
            param_name = f"filter_{key}"
            where_parts.append(f"AND {key} = :{param_name}")
            params[param_name] = value
        
        # Build GROUP BY clause
        group_by_clause = ""
        if group_by:
            validated_columns = []
            for col in group_by:
                if not col.replace("_", "").isalnum():
                    raise ValueError(f"Invalid group by column: {col}")
                validated_columns.append(col)
            group_by_clause = f"GROUP BY {', '.join(validated_columns)}"
        
        # Construct final query
        query = f"""
        SELECT {', '.join(select_parts)}
        FROM {table}
        WHERE {' '.join(where_parts)}
        {group_by_clause}
        """
        
        return query.strip(), params
    
    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """
        Sanitize database identifier (table/column name).
        
        Args:
            identifier: The identifier to sanitize
            
        Returns:
            Sanitized identifier
            
        Raises:
            ValueError: If identifier contains invalid characters
        """
        # Allow only alphanumeric characters and underscores
        if not identifier.replace("_", "").isalnum():
            raise ValueError(
                f"Invalid identifier '{identifier}': "
                "Only alphanumeric characters and underscores are allowed"
            )
        
        # Additional check for SQL keywords
        sql_keywords = {
            "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", 
            "CREATE", "ALTER", "EXEC", "EXECUTE", "UNION"
        }
        
        if identifier.upper() in sql_keywords:
            raise ValueError(f"Identifier '{identifier}' is a reserved SQL keyword")
        
        return identifier