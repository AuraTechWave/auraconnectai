# backend/modules/tax/models/tax_jurisdiction_models.py

from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, Date, Text, 
    ForeignKey, UniqueConstraint, CheckConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import date
from core.database import Base
from core.mixins import TimestampMixin, TenantMixin


class TaxJurisdiction(Base, TimestampMixin, TenantMixin):
    """Tax jurisdictions (federal, state, county, city)"""
    __tablename__ = "tax_jurisdictions"
    
    id = Column(Integer, primary_key=True, index=True)
    jurisdiction_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Jurisdiction details
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., "US", "CA", "NY-NYC"
    jurisdiction_type = Column(String(50), nullable=False)  # federal, state, county, city, special
    parent_jurisdiction_id = Column(Integer, ForeignKey("tax_jurisdictions.id"), nullable=True)
    
    # Geographic information
    country_code = Column(String(2), nullable=False)
    state_code = Column(String(10), nullable=True)
    county_name = Column(String(100), nullable=True)
    city_name = Column(String(100), nullable=True)
    zip_codes = Column(JSONB, nullable=True)  # List of zip codes
    
    # Jurisdiction metadata
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False, default=date.today)
    expiry_date = Column(Date, nullable=True)
    
    # Configuration
    filing_frequency = Column(String(50), nullable=True)  # monthly, quarterly, annually
    filing_due_day = Column(Integer, nullable=True)  # Day of month
    registration_number = Column(String(100), nullable=True)
    tax_id = Column(String(100), nullable=True)
    
    # Contact information
    tax_authority_name = Column(String(200), nullable=True)
    tax_authority_website = Column(String(500), nullable=True)
    tax_authority_phone = Column(String(50), nullable=True)
    tax_authority_email = Column(String(200), nullable=True)
    tax_authority_address = Column(Text, nullable=True)
    
    # Relationships
    parent_jurisdiction = relationship("TaxJurisdiction", remote_side=[id])
    tax_rates = relationship("TaxRate", back_populates="jurisdiction", cascade="all, delete-orphan")
    tax_rules = relationship("TaxRuleConfiguration", back_populates="jurisdiction")
    filings = relationship("TaxFiling", back_populates="jurisdiction")
    
    __table_args__ = (
        UniqueConstraint('code', 'jurisdiction_type', 'tenant_id', name='uq_jurisdiction_code_type_tenant'),
        Index('idx_jurisdiction_type_active', 'jurisdiction_type', 'is_active'),
        Index('idx_jurisdiction_location', 'country_code', 'state_code'),
    )


class TaxRate(Base, TimestampMixin, TenantMixin):
    """Tax rates for different jurisdictions and tax types"""
    __tablename__ = "tax_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    rate_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Jurisdiction reference
    jurisdiction_id = Column(Integer, ForeignKey("tax_jurisdictions.id"), nullable=False)
    
    # Tax type and category
    tax_type = Column(String(50), nullable=False)  # sales, income, payroll, property, excise
    tax_subtype = Column(String(50), nullable=True)  # e.g., state_income, federal_income
    tax_category = Column(String(100), nullable=True)  # e.g., prepared_food, general_merchandise
    
    # Rate information
    rate_percent = Column(Numeric(8, 5), nullable=False)
    flat_amount = Column(Numeric(12, 2), nullable=True)  # For flat taxes
    
    # Thresholds and brackets
    min_amount = Column(Numeric(12, 2), nullable=True)  # Minimum taxable amount
    max_amount = Column(Numeric(12, 2), nullable=True)  # Maximum taxable amount
    bracket_name = Column(String(100), nullable=True)  # e.g., "10% bracket"
    
    # Applicability
    applies_to = Column(String(100), nullable=True)  # products, services, labor, all
    exemption_categories = Column(JSONB, nullable=True)  # List of exempt categories
    
    # Validity period
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Additional rules
    compound_on = Column(JSONB, nullable=True)  # List of tax types this compounds on
    ordering = Column(Integer, default=0)  # Order of calculation
    calculation_method = Column(String(50), default="percentage")  # percentage, flat, tiered
    
    # Relationships
    jurisdiction = relationship("TaxJurisdiction", back_populates="tax_rates")
    
    __table_args__ = (
        CheckConstraint('rate_percent >= 0', name='check_rate_non_negative'),
        CheckConstraint('flat_amount >= 0', name='check_flat_amount_non_negative'),
        Index('idx_tax_rate_type_active', 'tax_type', 'is_active'),
        Index('idx_tax_rate_jurisdiction_type', 'jurisdiction_id', 'tax_type'),
        UniqueConstraint(
            'jurisdiction_id', 'tax_type', 'tax_subtype', 'tax_category', 
            'effective_date', 'tenant_id',
            name='uq_tax_rate_jurisdiction_type_date'
        ),
    )


class TaxRuleConfiguration(Base, TimestampMixin, TenantMixin):
    """Complex tax rules and special conditions"""
    __tablename__ = "tax_rule_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Rule identification
    rule_name = Column(String(200), nullable=False)
    rule_code = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Jurisdiction and tax type
    jurisdiction_id = Column(Integer, ForeignKey("tax_jurisdictions.id"), nullable=False)
    tax_type = Column(String(50), nullable=False)
    
    # Rule type
    rule_type = Column(String(100), nullable=False)  # exemption, holiday, threshold, nexus
    
    # Rule conditions (stored as JSON for flexibility)
    conditions = Column(JSONB, nullable=False)
    # Example conditions:
    # - {"customer_type": "nonprofit", "certificate_required": true}
    # - {"date_range": {"start": "2024-11-25", "end": "2024-11-27"}}
    # - {"threshold": {"sales_amount": 100000, "transaction_count": 200}}
    
    # Rule actions
    actions = Column(JSONB, nullable=False)
    # Example actions:
    # - {"apply_rate": 0, "reason": "tax_exempt"}
    # - {"reduce_rate_by": 50, "max_discount": 1000}
    
    # Validity
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0)  # Higher priority rules apply first
    
    # Compliance
    requires_documentation = Column(Boolean, default=False)
    documentation_types = Column(JSONB, nullable=True)  # List of required documents
    
    # Relationships
    jurisdiction = relationship("TaxJurisdiction", back_populates="tax_rules")
    
    __table_args__ = (
        Index('idx_tax_rule_type_active', 'rule_type', 'is_active'),
        Index('idx_tax_rule_jurisdiction', 'jurisdiction_id', 'tax_type'),
    )


class TaxExemptionCertificate(Base, TimestampMixin, TenantMixin):
    """Customer tax exemption certificates"""
    __tablename__ = "tax_exemption_certificates"
    
    id = Column(Integer, primary_key=True, index=True)
    certificate_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Customer information
    customer_id = Column(Integer, nullable=False)
    customer_name = Column(String(200), nullable=False)
    customer_tax_id = Column(String(100), nullable=True)
    
    # Certificate details
    certificate_number = Column(String(100), nullable=False)
    exemption_type = Column(String(100), nullable=False)  # resale, nonprofit, government
    exemption_reason = Column(Text, nullable=True)
    
    # Jurisdiction coverage
    jurisdiction_ids = Column(JSONB, nullable=False)  # List of jurisdiction IDs
    tax_types = Column(JSONB, nullable=False)  # List of tax types exempted
    
    # Validity
    issue_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_date = Column(Date, nullable=True)
    verified_by = Column(String(100), nullable=True)
    
    # Documentation
    document_url = Column(String(500), nullable=True)
    document_hash = Column(String(200), nullable=True)  # For integrity verification
    
    # Audit trail
    last_used_date = Column(Date, nullable=True)
    usage_count = Column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint('certificate_number', 'tenant_id', name='uq_certificate_number_tenant'),
        Index('idx_exemption_customer', 'customer_id', 'is_active'),
        Index('idx_exemption_expiry', 'expiry_date', 'is_active'),
    )


class TaxNexus(Base, TimestampMixin, TenantMixin):
    """Tax nexus configuration for multi-state operations"""
    __tablename__ = "tax_nexus"
    
    id = Column(Integer, primary_key=True, index=True)
    nexus_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    # Jurisdiction
    jurisdiction_id = Column(Integer, ForeignKey("tax_jurisdictions.id"), nullable=False)
    
    # Nexus type
    nexus_type = Column(String(50), nullable=False)  # physical, economic, affiliate, click_through
    
    # Nexus details
    establishment_date = Column(Date, nullable=False)
    registration_date = Column(Date, nullable=True)
    registration_number = Column(String(100), nullable=True)
    
    # Thresholds (for economic nexus)
    sales_threshold = Column(Numeric(12, 2), nullable=True)
    transaction_threshold = Column(Integer, nullable=True)
    threshold_period = Column(String(50), nullable=True)  # annual, quarterly
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    requires_filing = Column(Boolean, default=True, nullable=False)
    
    # Compliance
    last_filing_date = Column(Date, nullable=True)
    next_filing_date = Column(Date, nullable=True)
    filing_frequency = Column(String(50), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    jurisdiction = relationship("TaxJurisdiction")
    
    __table_args__ = (
        UniqueConstraint('jurisdiction_id', 'nexus_type', 'tenant_id', 
                        name='uq_nexus_jurisdiction_type_tenant'),
        Index('idx_nexus_active', 'is_active', 'requires_filing'),
    )