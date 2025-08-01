# backend/modules/tax/models/tax_compliance_models.py

from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, Date, DateTime, Text, 
    ForeignKey, UniqueConstraint, CheckConstraint, Index, JSON, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import date, datetime
import enum
from backend.core.database import Base
from backend.core.mixins import TimestampMixin, TenantMixin


class FilingStatus(str, enum.Enum):
    """Tax filing status enumeration"""
    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"
    PAID = "paid"


class FilingType(str, enum.Enum):
    """Tax filing type enumeration"""
    SALES_TAX = "sales_tax"
    INCOME_TAX = "income_tax"
    PAYROLL_TAX = "payroll_tax"
    PROPERTY_TAX = "property_tax"
    EXCISE_TAX = "excise_tax"
    FRANCHISE_TAX = "franchise_tax"
    OTHER = "other"


class TaxFiling(Base, TimestampMixin, TenantMixin):
    """Tax filing records for compliance tracking"""
    __tablename__ = "tax_filings"
    
    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Filing identification
    filing_number = Column(String(100), nullable=True)  # Assigned after submission
    internal_reference = Column(String(100), nullable=False, unique=True)
    
    # Jurisdiction and period
    jurisdiction_id = Column(Integer, ForeignKey("tax_jurisdictions.id"), nullable=False)
    filing_type = Column(Enum(FilingType), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    
    # Status tracking
    status = Column(Enum(FilingStatus), nullable=False, default=FilingStatus.DRAFT)
    due_date = Column(Date, nullable=False)
    filed_date = Column(DateTime, nullable=True)
    
    # Financial summary
    gross_sales = Column(Numeric(12, 2), nullable=True)
    taxable_sales = Column(Numeric(12, 2), nullable=True)
    exempt_sales = Column(Numeric(12, 2), nullable=True)
    tax_collected = Column(Numeric(12, 2), nullable=True)
    tax_due = Column(Numeric(12, 2), nullable=False)
    penalties = Column(Numeric(12, 2), default=0)
    interest = Column(Numeric(12, 2), default=0)
    total_due = Column(Numeric(12, 2), nullable=False)
    
    # Payment information
    payment_status = Column(String(50), nullable=True)  # pending, partial, paid
    payment_date = Column(Date, nullable=True)
    payment_reference = Column(String(100), nullable=True)
    payment_method = Column(String(50), nullable=True)
    
    # Filing details
    form_type = Column(String(50), nullable=True)  # e.g., "Form ST-100"
    confirmation_number = Column(String(100), nullable=True)
    
    # Preparer information
    prepared_by = Column(String(100), nullable=True)
    prepared_date = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_date = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    
    # Attachments and notes
    attachments = Column(JSONB, nullable=True)  # List of document references
    notes = Column(Text, nullable=True)
    
    # Audit fields
    is_amended = Column(Boolean, default=False)
    amendment_reason = Column(Text, nullable=True)
    original_filing_id = Column(Integer, ForeignKey("tax_filings.id"), nullable=True)
    
    # Relationships
    jurisdiction = relationship("TaxJurisdiction", back_populates="filings")
    original_filing = relationship("TaxFiling", remote_side=[id])
    line_items = relationship("TaxFilingLineItem", back_populates="filing", cascade="all, delete-orphan")
    audit_logs = relationship("TaxAuditLog", back_populates="filing")
    
    __table_args__ = (
        CheckConstraint('period_end >= period_start', name='check_period_valid'),
        CheckConstraint('tax_due >= 0', name='check_tax_due_non_negative'),
        Index('idx_filing_status_due', 'status', 'due_date'),
        Index('idx_filing_jurisdiction_period', 'jurisdiction_id', 'period_start', 'period_end'),
        UniqueConstraint('internal_reference', 'tenant_id', name='uq_filing_reference_tenant'),
    )


class TaxFilingLineItem(Base, TimestampMixin):
    """Detailed line items for tax filings"""
    __tablename__ = "tax_filing_line_items"
    
    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(Integer, ForeignKey("tax_filings.id"), nullable=False)
    
    # Line item details
    line_number = Column(String(20), nullable=False)
    description = Column(String(500), nullable=False)
    tax_category = Column(String(100), nullable=True)
    
    # Amounts
    gross_amount = Column(Numeric(12, 2), nullable=False)
    deductions = Column(Numeric(12, 2), default=0)
    exemptions = Column(Numeric(12, 2), default=0)
    taxable_amount = Column(Numeric(12, 2), nullable=False)
    tax_rate = Column(Numeric(8, 5), nullable=False)
    tax_amount = Column(Numeric(12, 2), nullable=False)
    
    # Additional information
    location_code = Column(String(50), nullable=True)
    product_category = Column(String(100), nullable=True)
    transaction_count = Column(Integer, nullable=True)
    
    # Relationships
    filing = relationship("TaxFiling", back_populates="line_items")
    
    __table_args__ = (
        UniqueConstraint('filing_id', 'line_number', name='uq_filing_line_number'),
        CheckConstraint('taxable_amount >= 0', name='check_taxable_amount_non_negative'),
        CheckConstraint('tax_amount >= 0', name='check_tax_amount_non_negative'),
    )


class TaxRemittance(Base, TimestampMixin, TenantMixin):
    """Tax payment remittance records"""
    __tablename__ = "tax_remittances"
    
    id = Column(Integer, primary_key=True, index=True)
    remittance_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Payment details
    payment_date = Column(Date, nullable=False)
    payment_method = Column(String(50), nullable=False)  # ach, wire, check, credit_card
    payment_reference = Column(String(100), nullable=False)
    
    # Amount information
    payment_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Applied to filings
    filing_references = Column(JSONB, nullable=False)  # List of filing IDs
    
    # Bank information
    bank_account_last4 = Column(String(4), nullable=True)
    bank_name = Column(String(100), nullable=True)
    confirmation_code = Column(String(100), nullable=True)
    
    # Status
    status = Column(String(50), nullable=False)  # pending, processed, failed, reversed
    processed_date = Column(DateTime, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    __table_args__ = (
        CheckConstraint('payment_amount > 0', name='check_payment_amount_positive'),
        Index('idx_remittance_date_status', 'payment_date', 'status'),
        UniqueConstraint('payment_reference', 'tenant_id', name='uq_payment_reference_tenant'),
    )


class TaxAuditLog(Base, TimestampMixin, TenantMixin):
    """Audit trail for tax-related activities"""
    __tablename__ = "tax_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Event information
    event_type = Column(String(100), nullable=False)  # calculation, filing, payment, adjustment
    event_subtype = Column(String(100), nullable=True)
    event_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Entity references
    entity_type = Column(String(50), nullable=False)  # order, filing, payment, certificate
    entity_id = Column(String(100), nullable=False)
    filing_id = Column(Integer, ForeignKey("tax_filings.id"), nullable=True)
    
    # User information
    user_id = Column(String(100), nullable=False)
    user_name = Column(String(200), nullable=True)
    user_role = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Change details
    action = Column(String(100), nullable=False)  # create, update, delete, calculate
    changes = Column(JSONB, nullable=True)  # Before/after values
    
    # Financial impact
    amount_before = Column(Numeric(12, 2), nullable=True)
    amount_after = Column(Numeric(12, 2), nullable=True)
    tax_impact = Column(Numeric(12, 2), nullable=True)
    
    # Additional context
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    audit_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    filing = relationship("TaxFiling", back_populates="audit_logs")
    
    __table_args__ = (
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_timestamp', 'event_timestamp'),
        Index('idx_audit_user', 'user_id', 'event_timestamp'),
        Index('idx_audit_event_type', 'event_type', 'event_subtype'),
    )


class TaxReportTemplate(Base, TimestampMixin, TenantMixin):
    """Templates for tax reports and forms"""
    __tablename__ = "tax_report_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Template identification
    template_code = Column(String(100), nullable=False)
    template_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template type
    report_type = Column(String(100), nullable=False)  # filing_form, summary_report, detail_report
    filing_type = Column(Enum(FilingType), nullable=True)
    
    # Jurisdiction
    jurisdiction_id = Column(Integer, ForeignKey("tax_jurisdictions.id"), nullable=True)
    
    # Template definition
    template_format = Column(String(50), nullable=False)  # json, xml, pdf, csv
    template_schema = Column(JSONB, nullable=False)  # Field definitions
    template_layout = Column(JSONB, nullable=True)  # Layout configuration
    
    # Validation rules
    validation_rules = Column(JSONB, nullable=True)
    
    # Version control
    version = Column(String(20), nullable=False, default="1.0")
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    
    # Relationships
    jurisdiction = relationship("TaxJurisdiction")
    
    __table_args__ = (
        UniqueConstraint('template_code', 'version', 'tenant_id', 
                        name='uq_template_code_version_tenant'),
        Index('idx_template_type_active', 'report_type', 'is_active'),
    )