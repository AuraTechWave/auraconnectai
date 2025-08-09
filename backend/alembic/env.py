from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from core.database import Base
from modules.staff.models import (
    staff_models, shift_models, attendance_models, payroll_models
)
from modules.orders.models import order_models
from modules.tax.models import tax_models
from modules.payroll.models import payroll_models as new_payroll_models

# Ensure all models are imported — even if not directly used
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.models.shift_models import Shift
from modules.staff.models.attendance_models import AttendanceLog
from modules.staff.models.payroll_models import Payroll, Payslip
from modules.orders.models.order_models import Order, OrderItem
from modules.tax.models.tax_models import TaxRule as ExistingTaxRule
from modules.payroll.models.payroll_models import (
    TaxRule, PayrollPolicy, EmployeePayment, EmployeePaymentTaxApplication
)
from modules.feedback.models.feedback_models import (
    Review, Feedback, ReviewAggregate, ReviewTemplate, ReviewInvitation,
    ReviewMedia, ReviewVote, BusinessResponse, FeedbackResponse, FeedbackCategory
)

target_metadata = Base.metadata


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with DATABASE_URL from environment
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# target_metadata = Base.metadata  # Already set above

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()