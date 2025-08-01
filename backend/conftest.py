"""
Pytest configuration file for backend testing.
"""
import sys
from pathlib import Path

# Add the backend directory to Python path so imports work correctly
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))