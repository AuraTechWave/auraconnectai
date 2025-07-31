#!/usr/bin/env python3
"""
Core extraction framework for payroll data migration.

This module provides the base classes and utilities for extracting data
from legacy payroll systems.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Base class for all system-specific extractors."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize extractor with configuration."""
        self.config = config
        self.connection = None
        self.extraction_timestamp = datetime.now()
        self.extraction_stats = {
            'start_time': None,
            'end_time': None,
            'records_extracted': {},
            'errors': []
        }
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to source system."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to source system."""
        pass
    
    @abstractmethod
    def extract_employees(self, as_of_date: Optional[date] = None) -> pd.DataFrame:
        """Extract employee master data."""
        pass
    
    @abstractmethod
    def extract_compensation(self, as_of_date: Optional[date] = None) -> pd.DataFrame:
        """Extract compensation data."""
        pass
    
    @abstractmethod
    def extract_tax_info(self, as_of_date: Optional[date] = None) -> pd.DataFrame:
        """Extract tax configuration data."""
        pass
    
    @abstractmethod
    def extract_payment_history(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Extract payment history for date range."""
        pass
    
    def extract_all(self, as_of_date: Optional[date] = None) -> Dict[str, pd.DataFrame]:
        """Extract all data from source system."""
        self.extraction_stats['start_time'] = datetime.now()
        logger.info(f"Starting extraction at {self.extraction_stats['start_time']}")
        
        try:
            self.connect()
            
            datasets = {
                'employees': self.extract_employees(as_of_date),
                'compensation': self.extract_compensation(as_of_date),
                'tax_info': self.extract_tax_info(as_of_date),
                'payment_history': self.extract_payment_history(
                    start_date=date(date.today().year, 1, 1),
                    end_date=date.today()
                )
            }
            
            # Record statistics
            for name, df in datasets.items():
                self.extraction_stats['records_extracted'][name] = len(df)
                logger.info(f"Extracted {len(df)} {name} records")
            
            return datasets
            
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            self.extraction_stats['errors'].append(str(e))
            raise
            
        finally:
            self.disconnect()
            self.extraction_stats['end_time'] = datetime.now()
            duration = self.extraction_stats['end_time'] - self.extraction_stats['start_time']
            logger.info(f"Extraction completed in {duration}")
    
    def validate_extraction(self, data: pd.DataFrame, expected_count: Optional[int] = None) -> bool:
        """Validate extracted data meets basic criteria."""
        validations = []
        
        # Check if data is empty
        if data.empty:
            logger.warning("Extracted data is empty")
            validations.append(False)
        
        # Check expected count if provided
        if expected_count and len(data) != expected_count:
            logger.warning(f"Expected {expected_count} records, got {len(data)}")
            validations.append(False)
        
        # Check for required columns
        if hasattr(self, 'required_columns'):
            missing_columns = set(self.required_columns) - set(data.columns)
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                validations.append(False)
        
        return all(validations) if validations else True
    
    def save_checkpoint(self, data: pd.DataFrame, checkpoint_name: str) -> None:
        """Save extraction checkpoint for recovery."""
        checkpoint_path = f"{self.config['checkpoint_dir']}/{checkpoint_name}_{self.extraction_timestamp:%Y%m%d_%H%M%S}.parquet"
        data.to_parquet(checkpoint_path, index=False)
        logger.info(f"Saved checkpoint to {checkpoint_path}")


class SQLExtractor(BaseExtractor):
    """Base extractor for SQL-based legacy systems."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.engine = None
    
    def connect(self) -> None:
        """Create SQLAlchemy engine."""
        connection_string = self._build_connection_string()
        self.engine = create_engine(connection_string)
        logger.info("Connected to database")
    
    def disconnect(self) -> None:
        """Dispose of SQLAlchemy engine."""
        if self.engine:
            self.engine.dispose()
            logger.info("Disconnected from database")
    
    def _build_connection_string(self) -> str:
        """Build database connection string from config."""
        db_config = self.config['database']
        
        if db_config['type'] == 'postgresql':
            return f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        elif db_config['type'] == 'mysql':
            return f"mysql+pymysql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        elif db_config['type'] == 'mssql':
            return f"mssql+pyodbc://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}?driver=ODBC+Driver+17+for+SQL+Server"
        else:
            raise ValueError(f"Unsupported database type: {db_config['type']}")
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame."""
        try:
            with self.engine.connect() as conn:
                return pd.read_sql_query(text(query), conn, params=params)
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            logger.debug(f"Query: {query}")
            raise


class FileExtractor(BaseExtractor):
    """Base extractor for file-based legacy systems."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_paths = config.get('file_paths', {})
    
    def connect(self) -> None:
        """Verify file paths exist."""
        for name, path in self.file_paths.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
        logger.info("All file paths verified")
    
    def disconnect(self) -> None:
        """No disconnection needed for file-based systems."""
        pass
    
    def read_csv(self, file_path: str, **kwargs) -> pd.DataFrame:
        """Read CSV file with standard options."""
        return pd.read_csv(file_path, **kwargs)
    
    def read_excel(self, file_path: str, **kwargs) -> pd.DataFrame:
        """Read Excel file with standard options."""
        return pd.read_excel(file_path, **kwargs)


class APIExtractor(BaseExtractor):
    """Base extractor for API-based legacy systems."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config['api']['base_url']
        self.auth_token = None
        self.session = None
    
    def connect(self) -> None:
        """Authenticate and create session."""
        import requests
        
        self.session = requests.Session()
        
        # Authenticate
        auth_response = self.session.post(
            f"{self.base_url}/auth",
            json={
                'username': self.config['api']['username'],
                'password': self.config['api']['password']
            }
        )
        auth_response.raise_for_status()
        
        self.auth_token = auth_response.json()['token']
        self.session.headers.update({
            'Authorization': f'Bearer {self.auth_token}'
        })
        
        logger.info("API authentication successful")
    
    def disconnect(self) -> None:
        """Close API session."""
        if self.session:
            self.session.close()
            logger.info("API session closed")
    
    def fetch_data(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Fetch data from API endpoint."""
        all_data = []
        page = 1
        
        while True:
            if params is None:
                params = {}
            params['page'] = page
            
            response = self.session.get(f"{self.base_url}/{endpoint}", params=params)
            response.raise_for_status()
            
            data = response.json()
            all_data.extend(data['results'])
            
            if not data.get('has_next', False):
                break
            
            page += 1
        
        return all_data


# Utility functions

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean common data issues in extracted DataFrames."""
    # Remove leading/trailing whitespace from string columns
    string_columns = df.select_dtypes(include=['object']).columns
    for col in string_columns:
        df[col] = df[col].str.strip()
    
    # Replace empty strings with None
    df = df.replace('', None)
    
    # Remove duplicate rows
    df = df.drop_duplicates()
    
    return df


def save_extraction_report(stats: Dict, output_path: str) -> None:
    """Save extraction statistics to a report file."""
    import json
    
    with open(output_path, 'w') as f:
        json.dump(stats, f, indent=2, default=str)
    
    logger.info(f"Extraction report saved to {output_path}")


if __name__ == "__main__":
    # Example usage
    import yaml
    
    with open('config/extraction_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # This would be implemented by system-specific extractors
    # extractor = ADPExtractor(config)
    # data = extractor.extract_all()
    
    print("Base extraction framework loaded successfully")