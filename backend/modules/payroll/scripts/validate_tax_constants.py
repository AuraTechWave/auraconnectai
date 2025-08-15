#!/usr/bin/env python3
# backend/modules/payroll/scripts/validate_tax_constants.py

"""
Validate tax constants and rates in payroll module.
Used by pre-commit hooks to ensure tax data integrity.
"""

import sys
import re
from decimal import Decimal
from pathlib import Path

# Known valid tax rates for 2024
VALID_TAX_RATES = {
    "federal": {
        "brackets": [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37],
        "social_security": 0.062,
        "medicare": 0.0145,
        "additional_medicare": 0.009,
    },
    "california": {
        "brackets": [0.01, 0.02, 0.04, 0.06, 0.08, 0.093, 0.103, 0.113, 0.123],
        "sdi": 0.009,  # 2024 rate
        "ui": {"min": 0.015, "max": 0.061},
    },
    "limits": {
        "social_security_wage_base": 168600,  # 2024 limit
        "401k_contribution": 23000,  # 2024 limit
        "401k_catch_up": 7500,
    },
}


def find_tax_files():
    """Find all Python files that might contain tax constants."""
    payroll_dir = Path(__file__).parent.parent
    tax_files = []

    for pattern in ["*tax*.py", "*rate*.py", "*constant*.py"]:
        tax_files.extend(payroll_dir.rglob(pattern))

    return [
        f for f in tax_files if "test" not in str(f) and "__pycache__" not in str(f)
    ]


def validate_tax_rate(value_str, valid_rates):
    """Validate a tax rate value."""
    try:
        value = float(value_str)
        return any(abs(value - rate) < 0.0001 for rate in valid_rates)
    except ValueError:
        return False


def check_file_for_rates(filepath):
    """Check a file for tax rate constants."""
    issues = []

    with open(filepath, "r") as f:
        content = f.read()

    # Check for federal tax brackets
    federal_pattern = r"federal.*tax.*=.*(\d+\.?\d*)"
    federal_matches = re.findall(federal_pattern, content, re.IGNORECASE)
    for match in federal_matches:
        rate = float(match)
        if rate < 1:  # Percentage as decimal
            if not validate_tax_rate(match, VALID_TAX_RATES["federal"]["brackets"]):
                issues.append(f"Invalid federal tax rate: {rate}")

    # Check for FICA rates
    fica_pattern = r"(social_security|medicare).*=.*(\d+\.?\d*)"
    fica_matches = re.findall(fica_pattern, content, re.IGNORECASE)
    for tax_type, rate_str in fica_matches:
        rate = float(rate_str)
        if rate < 1:  # Percentage as decimal
            if "social" in tax_type.lower() and abs(rate - 0.062) > 0.0001:
                issues.append(f"Invalid Social Security rate: {rate} (expected 0.062)")
            elif "medicare" in tax_type.lower() and rate not in [0.0145, 0.009]:
                issues.append(f"Invalid Medicare rate: {rate}")

    # Check for wage base limits
    wage_base_pattern = r"wage_base.*=.*(\d+)"
    wage_base_matches = re.findall(wage_base_pattern, content, re.IGNORECASE)
    for match in wage_base_matches:
        limit = int(match)
        if limit != VALID_TAX_RATES["limits"]["social_security_wage_base"]:
            issues.append(
                f"Invalid SS wage base: {limit} (expected {VALID_TAX_RATES['limits']['social_security_wage_base']})"
            )

    return issues


def main():
    """Main validation function."""
    print("Validating tax constants in payroll module...")

    tax_files = find_tax_files()
    all_issues = []

    for filepath in tax_files:
        issues = check_file_for_rates(filepath)
        if issues:
            all_issues.extend([(filepath, issue) for issue in issues])

    if all_issues:
        print("\n❌ Tax constant validation failed!\n")
        for filepath, issue in all_issues:
            print(f"  {filepath.name}: {issue}")
        print("\nPlease update tax constants to match current rates.")
        return 1
    else:
        print("✅ All tax constants validated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
