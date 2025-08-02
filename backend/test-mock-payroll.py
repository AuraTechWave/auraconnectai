#!/usr/bin/env python3
"""Test payroll functionality with mock data (no database required)"""

import asyncio
from datetime import date
from decimal import Decimal

# Mock payroll service for testing
class MockPayrollService:
    async def process_payroll(self, staff_id: int, pay_period_start: date, pay_period_end: date):
        """Mock payroll processing"""
        print(f"Processing payroll for staff {staff_id}")
        print(f"  Period: {pay_period_start} to {pay_period_end}")
        
        # Mock calculations
        hours_worked = 80  # 2 weeks * 40 hours
        hourly_rate = 25.00
        gross_pay = hours_worked * hourly_rate
        
        # Mock deductions
        federal_tax = gross_pay * 0.15
        state_tax = gross_pay * 0.05
        social_security = gross_pay * 0.062
        medicare = gross_pay * 0.0145
        
        total_deductions = federal_tax + state_tax + social_security + medicare
        net_pay = gross_pay - total_deductions
        
        result = {
            "staff_id": staff_id,
            "gross_pay": Decimal(str(gross_pay)),
            "net_pay": Decimal(str(net_pay)),
            "deductions": {
                "federal_tax": Decimal(str(federal_tax)),
                "state_tax": Decimal(str(state_tax)),
                "social_security": Decimal(str(social_security)),
                "medicare": Decimal(str(medicare))
            },
            "hours": {
                "regular": hours_worked,
                "overtime": 0
            }
        }
        
        print(f"  Gross Pay: ${gross_pay:.2f}")
        print(f"  Deductions: ${total_deductions:.2f}")
        print(f"  Net Pay: ${net_pay:.2f}")
        
        return result

async def main():
    print("Mock Payroll Processing Test")
    print("=" * 50)
    
    service = MockPayrollService()
    
    # Test data
    staff_ids = [1, 2, 3]
    pay_period_start = date(2025, 1, 15)
    pay_period_end = date(2025, 1, 31)
    
    print(f"\nProcessing payroll for period: {pay_period_start} to {pay_period_end}")
    print(f"Staff members: {staff_ids}")
    print()
    
    # Process each staff member
    results = []
    for staff_id in staff_ids:
        result = await service.process_payroll(staff_id, pay_period_start, pay_period_end)
        results.append(result)
        print()
    
    # Summary
    total_gross = sum(r["gross_pay"] for r in results)
    total_net = sum(r["net_pay"] for r in results)
    total_deductions = total_gross - total_net
    
    print("Summary")
    print("=" * 50)
    print(f"Total Staff Processed: {len(results)}")
    print(f"Total Gross Pay: ${total_gross:.2f}")
    print(f"Total Deductions: ${total_deductions:.2f}")
    print(f"Total Net Pay: ${total_net:.2f}")

if __name__ == "__main__":
    asyncio.run(main())