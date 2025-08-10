#!/usr/bin/env python3
"""
Script to clean up stale migration references in alembic_version table
"""
import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment or use default
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/auraconnect')

def cleanup_migrations():
    """Remove old migration references that might be causing issues"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check current migration version
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        current_versions = [row[0] for row in result]
        print(f"Current migration versions in database: {current_versions}")
        
        # Remove any references to the old payroll tax migrations
        old_migrations = [
            '20250725_0730_0008',
            '20250725_0730_0008_v2',
            '20250725_0730_0008_v3',
            'create_enhanced_payroll_tax_tables',
            'create_enhanced_payroll_tax_tables_v2',
            'create_enhanced_payroll_tax_tables_v3'
        ]
        
        for old_migration in old_migrations:
            if old_migration in current_versions:
                print(f"Removing old migration reference: {old_migration}")
                conn.execute(text(f"DELETE FROM alembic_version WHERE version_num = :version"), 
                           {"version": old_migration})
                conn.commit()
                print(f"Removed {old_migration}")
        
        # Check if the taxtype enum exists
        enum_result = conn.execute(text("""
            SELECT typname FROM pg_type WHERE typname IN ('taxtype', 'paymentstatus', 'payfrequency', 'paymentmethod')
        """))
        existing_enums = [row[0] for row in enum_result]
        print(f"\nExisting enums in database: {existing_enums}")

if __name__ == "__main__":
    cleanup_migrations()