# backend/core/query_logger.py

import logging
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from core.config import get_settings

logger = logging.getLogger("sqlalchemy.engine")
query_logger = logging.getLogger("query_performance")

settings = get_settings()


class QueryLogger:
    """SQL Query Logger for development and debugging"""
    
    def __init__(self):
        self.enabled = settings.ENVIRONMENT == "development" or settings.DEBUG
        self.slow_query_threshold = 1.0  # 1 second
        self.query_stats: Dict[str, Any] = {
            "total_queries": 0,
            "slow_queries": 0,
            "total_time": 0.0,
            "queries_by_table": {}
        }
        
        if self.enabled:
            self.setup_logging()
    
    def setup_logging(self):
        """Setup SQL query logging for development"""
        # Configure SQLAlchemy engine logging
        if settings.LOG_SQL_QUERIES:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
            
            # Setup custom formatter for SQL queries
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '\n%(levelname)s [%(asctime)s] SQL Query:\n%(message)s\n'
            ))
            logger.addHandler(handler)
        
        # Setup query performance logger
        query_handler = logging.StreamHandler()
        query_handler.setFormatter(logging.Formatter(
            '%(levelname)s [%(asctime)s] Query Performance: %(message)s'
        ))
        query_logger.addHandler(query_handler)
        query_logger.setLevel(logging.INFO)
    
    def log_query_stats(self):
        """Log accumulated query statistics"""
        if not self.enabled:
            return
        
        query_logger.info(f"""
        Query Statistics:
        - Total Queries: {self.query_stats['total_queries']}
        - Slow Queries (>{self.slow_query_threshold}s): {self.query_stats['slow_queries']}
        - Total Query Time: {self.query_stats['total_time']:.3f}s
        - Average Query Time: {self.query_stats['total_time'] / max(self.query_stats['total_queries'], 1):.3f}s
        - Queries by Table: {self.query_stats['queries_by_table']}
        """)
    
    def reset_stats(self):
        """Reset query statistics"""
        self.query_stats = {
            "total_queries": 0,
            "slow_queries": 0,
            "total_time": 0.0,
            "queries_by_table": {}
        }


# Singleton instance
query_logger_instance = QueryLogger()


def setup_query_logging(engine: Engine):
    """
    Setup query logging for an SQLAlchemy engine
    
    Args:
        engine: SQLAlchemy engine instance
    """
    if not query_logger_instance.enabled:
        return
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(time.time())
        
        # Extract table name from query (simple extraction)
        tables = extract_tables_from_query(statement)
        conn.info.setdefault('query_tables', []).append(tables)
        
        if settings.LOG_SQL_QUERIES:
            logger.debug("Start Query: %s", statement)
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - conn.info['query_start_time'].pop(-1)
        tables = conn.info['query_tables'].pop(-1)
        
        # Update statistics
        query_logger_instance.query_stats['total_queries'] += 1
        query_logger_instance.query_stats['total_time'] += total_time
        
        # Track queries by table
        for table in tables:
            if table not in query_logger_instance.query_stats['queries_by_table']:
                query_logger_instance.query_stats['queries_by_table'][table] = 0
            query_logger_instance.query_stats['queries_by_table'][table] += 1
        
        # Log slow queries
        if total_time > query_logger_instance.slow_query_threshold:
            query_logger_instance.query_stats['slow_queries'] += 1
            query_logger.warning(
                f"SLOW QUERY ({total_time:.3f}s): {statement[:200]}..."
            )
        
        if settings.LOG_SQL_QUERIES:
            logger.debug("Query Complete in %.3fs", total_time)
    
    @event.listens_for(Pool, "connect")
    def setup_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign keys and optimize SQLite connections"""
        if 'sqlite' in str(engine.url):
            # Enable foreign key constraints for SQLite
            dbapi_conn.execute("PRAGMA foreign_keys = ON")
            # Optimize SQLite performance
            dbapi_conn.execute("PRAGMA journal_mode = WAL")
    
    @event.listens_for(engine, "connect")
    def log_new_connection(dbapi_conn, connection_record):
        """Log new database connections"""
        logger.info("New database connection established")


def extract_tables_from_query(query: str) -> list:
    """
    Extract table names from SQL query (simple implementation)
    
    Args:
        query: SQL query string
    
    Returns:
        List of table names found in query
    """
    query_upper = query.upper()
    tables = []
    
    # Common patterns to find table names
    patterns = ['FROM ', 'JOIN ', 'UPDATE ', 'INSERT INTO ', 'DELETE FROM ']
    
    for pattern in patterns:
        pos = 0
        while True:
            pos = query_upper.find(pattern, pos)
            if pos == -1:
                break
            
            # Extract table name after pattern
            start = pos + len(pattern)
            end = start
            
            # Find end of table name (space, comma, or parenthesis)
            while end < len(query) and query[end] not in ' ,();\n':
                end += 1
            
            if end > start:
                table_name = query[start:end].strip().lower()
                # Remove schema prefix if present
                if '.' in table_name:
                    table_name = table_name.split('.')[-1]
                # Remove quotes
                table_name = table_name.strip('"\'`')
                
                if table_name and not table_name.startswith('('):
                    tables.append(table_name)
            
            pos = end
    
    return list(set(tables))  # Remove duplicates


@contextmanager
def log_query_performance(operation_name: str):
    """
    Context manager to log performance of a database operation
    
    Args:
        operation_name: Name of the operation being performed
    
    Example:
        with log_query_performance("fetch_customer_orders"):
            orders = db.query(Order).filter(Order.customer_id == 123).all()
    """
    if not query_logger_instance.enabled:
        yield
        return
    
    start_queries = query_logger_instance.query_stats['total_queries']
    start_time = time.time()
    
    try:
        yield
    finally:
        elapsed_time = time.time() - start_time
        query_count = query_logger_instance.query_stats['total_queries'] - start_queries
        
        query_logger.info(
            f"Operation '{operation_name}': {query_count} queries in {elapsed_time:.3f}s"
        )
        
        # Warn if potential N+1 query detected
        if query_count > 10:
            query_logger.warning(
                f"Potential N+1 query detected in '{operation_name}': {query_count} queries executed"
            )


def analyze_n_plus_one(threshold: int = 10):
    """
    Decorator to detect potential N+1 query issues
    
    Args:
        threshold: Number of queries that triggers a warning
    
    Example:
        @analyze_n_plus_one(threshold=5)
        def get_orders_with_items():
            # Function that might have N+1 issues
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not query_logger_instance.enabled:
                return func(*args, **kwargs)
            
            with log_query_performance(func.__name__):
                result = func(*args, **kwargs)
            
            return result
        
        return wrapper
    
    return decorator