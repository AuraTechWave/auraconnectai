"""
Pytest configuration file for backend testing.
"""
import sys
from pathlib import Path

# Add the backend directory to Python path so imports work correctly
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Add the parent directory to handle 'backend.' imports
parent_dir = backend_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import all models to ensure SQLAlchemy relationships work
try:
    # Import all models to register them with SQLAlchemy
    from modules.staff.models import staff_models, attendance_models, payroll_models as staff_payroll_models
    from modules.payroll.models import payroll_models, payroll_configuration
    from modules.orders.models import order_models
except ImportError:
    # If models can't be imported, that's ok for some tests
    pass