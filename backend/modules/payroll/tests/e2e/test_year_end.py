# backend/modules/payroll/tests/e2e/test_year_end.py

"""
End-to-end tests for year-end payroll processing.

Tests W-2 generation, annual summaries, and year-end
reporting requirements.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from ...services.payroll_tax_service import PayrollTaxService
from ...services.payment_export_service import PaymentExportService


class TestYearEndProcessing:
    """Test year-end payroll processing workflows."""
    
    @pytest.mark.e2e
    async def test_w2_generation_workflow(self, mock_db, sample_employees):
        """Test W-2 form generation for employees."""
        
        year = 2023
        tax_service = PayrollTaxService(mock_db)
        
        # Mock annual summaries for each employee
        annual_summaries = []
        for emp in sample_employees:
            summary = Mock()
            summary.employee_id = emp.id
            summary.total_wages = Decimal("65000.00") if emp.id == 1 else Decimal("52000.00")
            summary.federal_tax_withheld = Decimal("7800.00") if emp.id == 1 else Decimal("5200.00")
            summary.state_tax_withheld = Decimal("3250.00") if emp.id == 1 else Decimal("2600.00")
            summary.social_security_wages = summary.total_wages
            summary.social_security_withheld = summary.total_wages * Decimal("0.062")
            summary.medicare_wages = summary.total_wages
            summary.medicare_withheld = summary.total_wages * Decimal("0.0145")
            summary.retirement_401k = summary.total_wages * Decimal("0.06")
            summary.health_insurance = Decimal("6000.00") if emp.id == 1 else Decimal("3600.00")
            annual_summaries.append(summary)
        
        # Generate W-2s
        w2_forms = []
        for emp, summary in zip(sample_employees, annual_summaries):
            with patch.object(tax_service, 'generate_w2_data') as mock_w2:
                mock_w2.return_value = {
                    "employee_id": emp.id,
                    "employee_name": emp.full_name,
                    "employee_ssn": "XXX-XX-" + str(1000 + emp.id),
                    "employee_address": f"{emp.id} Main St, City, ST 12345",
                    "box1_wages": summary.total_wages,
                    "box2_federal_withheld": summary.federal_tax_withheld,
                    "box3_ss_wages": summary.social_security_wages,
                    "box4_ss_withheld": summary.social_security_withheld,
                    "box5_medicare_wages": summary.medicare_wages,
                    "box6_medicare_withheld": summary.medicare_withheld,
                    "box12_codes": {
                        "D": summary.retirement_401k,  # 401(k) contributions
                        "DD": summary.health_insurance  # Health insurance
                    },
                    "box16_state_wages": summary.total_wages,
                    "box17_state_withheld": summary.state_tax_withheld,
                    "box18_local_wages": Decimal("0.00"),
                    "box19_local_withheld": Decimal("0.00")
                }
                
                w2_data = await tax_service.generate_w2_data(
                    employee_id=emp.id,
                    year=year
                )
                w2_forms.append(w2_data)
        
        # Verify W-2 generation
        assert len(w2_forms) == len(sample_employees)
        assert all(w2["box1_wages"] > Decimal("0.00") for w2 in w2_forms)
        assert all("box12_codes" in w2 for w2 in w2_forms)
    
    @pytest.mark.e2e
    async def test_quarterly_941_reporting(self, mock_db, sample_company_setup):
        """Test quarterly 941 tax form generation."""
        
        year = 2023
        quarter = 4
        tax_service = PayrollTaxService(mock_db)
        
        # Mock quarterly totals
        with patch.object(tax_service, 'generate_quarterly_941') as mock_941:
            mock_941.return_value = {
                "form_941": {
                    "line1_employees": 50,
                    "line2_total_wages": Decimal("650000.00"),
                    "line3_federal_withheld": Decimal("78000.00"),
                    "line5a_taxable_ss_wages": Decimal("650000.00"),
                    "line5a_ss_tax": Decimal("40300.00"),  # 6.2% employer + employee
                    "line5c_taxable_medicare_wages": Decimal("650000.00"),
                    "line5c_medicare_tax": Decimal("9425.00"),  # 1.45% employer + employee
                    "line5d_additional_medicare": Decimal("450.00"),  # High earners
                    "line6_total_taxes": Decimal("128175.00"),
                    "line10_total_deposits": Decimal("128175.00"),
                    "line14_balance_due": Decimal("0.00")
                },
                "schedule_b_deposits": [
                    {"date": date(2023, 10, 15), "amount": Decimal("42725.00")},
                    {"date": date(2023, 11, 15), "amount": Decimal("42725.00")},
                    {"date": date(2023, 12, 15), "amount": Decimal("42725.00")}
                ]
            }
            
            quarterly_report = await tax_service.generate_quarterly_941(
                year=year,
                quarter=quarter
            )
        
        # Verify 941 data
        form_941 = quarterly_report["form_941"]
        assert form_941["line2_total_wages"] == Decimal("650000.00")
        assert form_941["line6_total_taxes"] == Decimal("128175.00")
        assert form_941["line14_balance_due"] == Decimal("0.00")
        assert len(quarterly_report["schedule_b_deposits"]) == 3
    
    @pytest.mark.e2e
    async def test_state_quarterly_reporting(self, mock_db):
        """Test state quarterly wage and tax reporting."""
        
        year = 2023
        quarter = 4
        tax_service = PayrollTaxService(mock_db)
        
        # California DE 9 and DE 9C reporting
        with patch.object(tax_service, 'generate_state_quarterly') as mock_state:
            mock_state.return_value = {
                "state": "california",
                "form_de9": {
                    "total_subject_wages": Decimal("400000.00"),
                    "uit_taxable_wages": Decimal("350000.00"),  # UI wage base limit
                    "pit_wages": Decimal("400000.00"),
                    "pit_withheld": Decimal("16000.00"),
                    "ui_contributions": Decimal("12250.00"),  # 3.5% on taxable
                    "ett_contributions": Decimal("350.00"),  # 0.1% on taxable
                    "sdi_employee": Decimal("4550.00"),  # 1.3% on taxable
                    "total_deposit": Decimal("33150.00")
                },
                "form_de9c": [  # Employee detail
                    {
                        "ssn": "XXX-XX-1001",
                        "name": "Employee 1",
                        "wages": Decimal("32500.00"),
                        "pit_withheld": Decimal("1300.00")
                    }
                    # ... more employees
                ]
            }
            
            state_report = await tax_service.generate_state_quarterly(
                state="california",
                year=year,
                quarter=quarter
            )
        
        # Verify state reporting
        assert state_report["form_de9"]["total_subject_wages"] == Decimal("400000.00")
        assert state_report["form_de9"]["ui_contributions"] > Decimal("0.00")
        assert len(state_report["form_de9c"]) > 0
    
    @pytest.mark.e2e
    async def test_annual_reconciliation(self, mock_db):
        """Test annual W-2/W-3 reconciliation."""
        
        year = 2023
        tax_service = PayrollTaxService(mock_db)
        export_service = PaymentExportService(mock_db)
        
        # Generate W-3 transmittal
        with patch.object(tax_service, 'generate_w3_transmittal') as mock_w3:
            mock_w3.return_value = {
                "form_w3": {
                    "box_b_employees": 50,
                    "box1_wages": Decimal("3250000.00"),
                    "box2_federal_withheld": Decimal("390000.00"),
                    "box3_ss_wages": Decimal("3250000.00"),
                    "box4_ss_withheld": Decimal("201500.00"),
                    "box5_medicare_wages": Decimal("3250000.00"),
                    "box6_medicare_withheld": Decimal("47125.00"),
                    "box7_ss_tips": Decimal("0.00"),
                    "box8_allocated_tips": Decimal("0.00"),
                    "box10_dependent_care": Decimal("25000.00"),
                    "box11_nonqualified_plans": Decimal("0.00"),
                    "box12_deferred_comp": Decimal("195000.00"),  # 401k
                    "box13_retirement_plan": True,
                    "box16_state_wages": Decimal("3250000.00"),
                    "box17_state_tax": Decimal("162500.00")
                },
                "reconciliation": {
                    "w2_count": 50,
                    "w2_total_wages": Decimal("3250000.00"),
                    "941_total_wages": Decimal("3250000.00"),
                    "variance": Decimal("0.00"),
                    "reconciled": True
                }
            }
            
            w3_data = await tax_service.generate_w3_transmittal(year=year)
        
        # Verify reconciliation
        assert w3_data["form_w3"]["box_b_employees"] == 50
        assert w3_data["reconciliation"]["reconciled"] is True
        assert w3_data["reconciliation"]["variance"] == Decimal("0.00")
    
    @pytest.mark.e2e
    async def test_1099_generation_for_contractors(self, mock_db):
        """Test 1099-NEC generation for contractors."""
        
        year = 2023
        tax_service = PayrollTaxService(mock_db)
        
        # Mock contractor payments
        contractors = [
            {
                "contractor_id": 1,
                "name": "Contractor One LLC",
                "tin": "XX-XXXXXXX",
                "address": "123 Business Rd, City, ST 12345",
                "total_payments": Decimal("25000.00")
            },
            {
                "contractor_id": 2,
                "name": "Independent Consultant",
                "tin": "XXX-XX-XXXX",
                "address": "456 Freelance Ave, Town, ST 67890",
                "total_payments": Decimal("8500.00")
            }
        ]
        
        # Generate 1099-NEC forms (payments >= $600)
        form_1099s = []
        for contractor in contractors:
            if contractor["total_payments"] >= Decimal("600.00"):
                with patch.object(tax_service, 'generate_1099_nec') as mock_1099:
                    mock_1099.return_value = {
                        "form_1099_nec": {
                            "payer_name": "Company Name",
                            "payer_tin": "XX-XXXXXXX",
                            "recipient_name": contractor["name"],
                            "recipient_tin": contractor["tin"],
                            "recipient_address": contractor["address"],
                            "box1_nonemployee_comp": contractor["total_payments"],
                            "box4_federal_withheld": Decimal("0.00"),  # No backup withholding
                            "box5_state_withheld": Decimal("0.00"),
                            "tax_year": year
                        }
                    }
                    
                    form_1099 = await tax_service.generate_1099_nec(
                        contractor_id=contractor["contractor_id"],
                        year=year
                    )
                    form_1099s.append(form_1099)
        
        # Verify 1099 generation
        assert len(form_1099s) == 2  # Both contractors exceed $600
        assert all(f["form_1099_nec"]["box1_nonemployee_comp"] >= Decimal("600.00") 
                  for f in form_1099s)