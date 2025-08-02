"""
Payroll Configuration Service for production-ready business logic.

Replaces hardcoded values with database-driven configurations to address
business logic concerns from code review.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models.payroll_configuration import (
    PayrollConfiguration, StaffPayPolicy, OvertimeRule, 
    TaxApproximationRule, RoleBasedPayRate, PayrollJobTracking,
    PayrollConfigurationType, PayrollJobStatus
)
from ...staff.models.staff_models import StaffMember


class PayrollConfigurationService:
    """
    Service for managing payroll configurations and replacing hardcoded business logic.
    
    This service addresses the concerns raised about:
    - Fixed benefit deduction factors (0.46)
    - Static policy data from get_staff_pay_policy
    - Hardcoded overtime rules and tax approximations
    - In-memory job tracking
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_staff_pay_policy_from_db(self, staff_id: int, location: str, effective_date: datetime = None) -> Optional[StaffPayPolicy]:
        """
        Get staff pay policy from database instead of returning static data.
        
        Addresses: "Staff Policy Source: get_staff_pay_policy returns static data; 
        ensure future work includes a real DB table."
        """
        if effective_date is None:
            effective_date = datetime.now()
        
        policy = self.db.query(StaffPayPolicy).filter(
            and_(
                StaffPayPolicy.staff_id == staff_id,
                StaffPayPolicy.location == location,
                StaffPayPolicy.effective_date <= effective_date,
                or_(
                    StaffPayPolicy.expiry_date.is_(None),
                    StaffPayPolicy.expiry_date > effective_date
                ),
                StaffPayPolicy.is_active == True
            )
        ).order_by(StaffPayPolicy.effective_date.desc()).first()
        
        return policy
    
    def get_benefit_proration_factor(self, location: str = "default", tenant_id: Optional[int] = None) -> Decimal:
        """
        Get configurable benefit proration factor instead of hardcoded 0.46.
        
        Addresses: "Tax Calculation Mocking: Current implementation of benefit deductions 
        uses a fixed factor (0.46). This is fine for demo purposes but should be 
        configurable or derived dynamically in production."
        """
        config = self.db.query(PayrollConfiguration).filter(
            and_(
                PayrollConfiguration.config_type == PayrollConfigurationType.BENEFIT_PRORATION,
                PayrollConfiguration.config_key == "monthly_to_biweekly_factor",
                PayrollConfiguration.location == location,
                PayrollConfiguration.tenant_id == tenant_id,
                PayrollConfiguration.is_active == True,
                PayrollConfiguration.effective_date <= datetime.now(),
                or_(
                    PayrollConfiguration.expiry_date.is_(None),
                    PayrollConfiguration.expiry_date > datetime.now()
                )
            )
        ).order_by(PayrollConfiguration.effective_date.desc()).first()
        
        if config:
            return Decimal(str(config.config_value.get("factor", "0.46")))
        
        # Fallback to configurable default
        return self._get_default_proration_factor()
    
    def get_overtime_rules(self, jurisdiction: str, tenant_id: Optional[int] = None) -> List[OvertimeRule]:
        """
        Get jurisdiction-specific overtime rules instead of flat 40-hour thresholds.
        
        Addresses concerns about flexible overtime calculation rules for daily overtime
        and jurisdiction-specific requirements.
        """
        rules = self.db.query(OvertimeRule).filter(
            and_(
                OvertimeRule.jurisdiction == jurisdiction,
                OvertimeRule.tenant_id == tenant_id,
                OvertimeRule.is_active == True,
                OvertimeRule.effective_date <= datetime.now(),
                or_(
                    OvertimeRule.expiry_date.is_(None),
                    OvertimeRule.expiry_date > datetime.now()
                )
            )
        ).order_by(OvertimeRule.precedence.desc()).all()
        
        return rules
    
    def get_tax_approximation_breakdown(self, jurisdiction: str, tenant_id: Optional[int] = None) -> Dict[str, Decimal]:
        """
        Get configurable tax breakdown percentages instead of hardcoded values.
        
        Addresses: "Tax deduction breakdowns should use real values or be explicitly 
        marked as estimates with configurable approximation rules."
        """
        rule = self.db.query(TaxApproximationRule).filter(
            and_(
                TaxApproximationRule.jurisdiction == jurisdiction,
                TaxApproximationRule.tenant_id == tenant_id,
                TaxApproximationRule.is_active == True,
                TaxApproximationRule.effective_date <= datetime.now(),
                or_(
                    TaxApproximationRule.expiry_date.is_(None),
                    TaxApproximationRule.expiry_date > datetime.now()
                )
            )
        ).order_by(TaxApproximationRule.effective_date.desc()).first()
        
        if rule:
            return {
                "federal_tax": rule.federal_tax_percentage,
                "state_tax": rule.state_tax_percentage,
                "local_tax": rule.local_tax_percentage,
                "social_security": rule.social_security_percentage,
                "medicare": rule.medicare_percentage,
                "unemployment": rule.unemployment_percentage
            }
        
        # Return fallback with clear indication these are estimates
        return self._get_default_tax_approximation()
    
    def get_role_based_pay_rate(self, role_name: str, location: str, experience_level: str = "default") -> Optional[RoleBasedPayRate]:
        """
        Get role-based pay rates from database instead of static data.
        
        Addresses concerns about static role rate mappings and provides
        experience-based rate adjustments.
        """
        rate = self.db.query(RoleBasedPayRate).filter(
            and_(
                RoleBasedPayRate.role_name == role_name,
                RoleBasedPayRate.location == location,
                RoleBasedPayRate.is_active == True,
                RoleBasedPayRate.effective_date <= datetime.now(),
                or_(
                    RoleBasedPayRate.expiry_date.is_(None),
                    RoleBasedPayRate.expiry_date > datetime.now()
                )
            )
        ).order_by(RoleBasedPayRate.effective_date.desc()).first()
        
        return rate
    
    def create_job_tracking(self, job_type: str, job_params: Dict[str, Any], 
                          created_by: str = None, tenant_id: Optional[int] = None) -> PayrollJobTracking:
        """
        Create persistent job tracking instead of in-memory dictionary.
        
        Addresses: "API Reliability: In-memory job status tracking (payroll_job_status) 
        will be lost on server restart. Consider persistent storage."
        """
        import uuid
        
        job_tracking = PayrollJobTracking(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            status=PayrollJobStatus.PENDING,
            started_at=datetime.utcnow(),
            job_metadata=job_params,  # Store all job parameters in metadata
            tenant_id=tenant_id,
            created_by_user_id=1 if created_by else None  # Would map from email to user ID in production
        )
        
        self.db.add(job_tracking)
        self.db.commit()
        self.db.refresh(job_tracking)
        
        return job_tracking
    
    def update_job_progress(self, job_id: str, status: str = None, 
                          progress_percentage: int = None, 
                          completed_items: int = None,
                          failed_items: int = None,
                          error_details: Dict = None,
                          result_data: Dict = None) -> Optional[PayrollJobTracking]:
        """
        Update job tracking progress with persistent storage.
        """
        job = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if not job:
            return None
        
        if status:
            job.status = status
            if status == "running" and not job.started_at:
                job.started_at = datetime.now()
            elif status in ["completed", "failed", "cancelled"]:
                job.completed_at = datetime.now()
        
        if progress_percentage is not None:
            job.progress_percentage = progress_percentage
        
        if completed_items is not None:
            job.completed_items = completed_items
        
        if failed_items is not None:
            job.failed_items = failed_items
        
        if error_details:
            job.error_details = error_details
        
        if result_data:
            job.result_data = result_data
        
        self.db.commit()
        self.db.refresh(job)
        
        return job
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get persistent job status instead of in-memory lookup.
        """
        job = self.db.query(PayrollJobTracking).filter(
            PayrollJobTracking.job_id == job_id
        ).first()
        
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress_percentage": job.progress_percentage,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "estimated_completion": job.estimated_completion.isoformat() if job.estimated_completion else None,
            "error_details": job.error_details,
            "result_data": job.result_data
        }
    
    def _get_default_proration_factor(self) -> Decimal:
        """Get system-wide default proration factor."""
        # This could also be configurable
        return Decimal("0.46")
    
    def _get_default_tax_approximation(self) -> Dict[str, Decimal]:
        """Get default tax approximation percentages with clear estimates marking."""
        return {
            "federal_tax": Decimal("0.22"),      # 22% estimate
            "state_tax": Decimal("0.08"),        # 8% estimate
            "local_tax": Decimal("0.02"),        # 2% estimate
            "social_security": Decimal("0.062"),  # 6.2% actual rate
            "medicare": Decimal("0.0145"),       # 1.45% actual rate
            "unemployment": Decimal("0.006")     # 0.6% estimate
        }
    
    def seed_default_configurations(self, location: str = "default", tenant_id: Optional[int] = None):
        """
        Seed the database with default configurations for initial setup.
        
        This helps transition from hardcoded values to configurable system.
        """
        now = datetime.now()
        
        # Seed benefit proration configuration
        proration_config = PayrollConfiguration(
            config_type=PayrollConfigurationType.BENEFIT_PRORATION,
            config_key="monthly_to_biweekly_factor",
            config_value={"factor": "0.46", "description": "Monthly benefit to biweekly proration"},
            description="Factor for converting monthly benefit amounts to biweekly deductions",
            location=location,
            tenant_id=tenant_id,
            effective_date=now,
            is_active=True
        )
        
        # Seed tax approximation rule
        tax_approx = TaxApproximationRule(
            rule_name="Default US Tax Approximation",
            jurisdiction="US",
            federal_tax_percentage=Decimal("0.22"),
            state_tax_percentage=Decimal("0.08"),
            local_tax_percentage=Decimal("0.02"),
            social_security_percentage=Decimal("0.062"),
            medicare_percentage=Decimal("0.0145"),
            unemployment_percentage=Decimal("0.006"),
            total_percentage=Decimal("0.3525"),
            effective_date=now,
            tenant_id=tenant_id,
            is_active=True
        )
        
        # Seed overtime rule
        overtime_rule = OvertimeRule(
            rule_name="Standard US Overtime",
            jurisdiction="US",
            weekly_threshold_hours=Decimal("40.0"),
            weekly_overtime_multiplier=Decimal("1.5"),
            daily_threshold_hours=Decimal("8.0"),
            daily_overtime_multiplier=Decimal("1.5"),
            precedence=1,
            effective_date=now,
            tenant_id=tenant_id,
            is_active=True
        )
        
        self.db.add_all([proration_config, tax_approx, overtime_rule])
        self.db.commit()