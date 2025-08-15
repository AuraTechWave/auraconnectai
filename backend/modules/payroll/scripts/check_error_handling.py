#!/usr/bin/env python3
# backend/modules/payroll/scripts/check_error_handling.py

"""
Check for proper error handling in payroll services.
Ensures all service methods have appropriate try-except blocks.
"""

import ast
import sys
from pathlib import Path


class ErrorHandlingChecker(ast.NodeVisitor):
    """AST visitor to check error handling patterns."""

    def __init__(self, filename):
        self.filename = filename
        self.issues = []
        self.current_function = None
        self.in_try_block = False

    def visit_FunctionDef(self, node):
        """Visit function definitions."""
        self.current_function = node.name
        self.in_try_block = False

        # Check if function has any error handling
        has_try = any(isinstance(child, ast.Try) for child in ast.walk(node))

        # Functions that should have error handling
        needs_error_handling = any(
            [
                "calculate" in node.name,
                "process" in node.name,
                "export" in node.name,
                "save" in node.name,
                "create" in node.name,
                "update" in node.name,
                "delete" in node.name,
            ]
        )

        if needs_error_handling and not has_try:
            self.issues.append(
                f"{self.current_function}: Missing error handling for data operation"
            )

        # Continue visiting child nodes
        self.generic_visit(node)
        self.current_function = None

    def visit_Try(self, node):
        """Visit try blocks."""
        self.in_try_block = True

        # Check for bare except
        for handler in node.handlers:
            if handler.type is None:
                self.issues.append(
                    f"{self.current_function}: Bare except clause found - catch specific exceptions"
                )
            elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                # Check if it's re-raised or logged
                has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(handler))
                has_log = any(
                    isinstance(n, ast.Call)
                    and hasattr(n.func, "attr")
                    and "log" in n.func.attr.lower()
                    for n in ast.walk(handler)
                )

                if not has_raise and not has_log:
                    self.issues.append(
                        f"{self.current_function}: Generic Exception caught without logging or re-raising"
                    )

        self.generic_visit(node)
        self.in_try_block = False


def check_file(filepath):
    """Check a single file for error handling issues."""
    with open(filepath, "r") as f:
        content = f.read()

    try:
        tree = ast.parse(content)
        checker = ErrorHandlingChecker(filepath.name)
        checker.visit(tree)
        return checker.issues
    except SyntaxError as e:
        return [f"Syntax error in {filepath.name}: {e}"]


def main():
    """Main checking function."""
    print("Checking error handling in payroll services...")

    services_dir = Path(__file__).parent.parent / "services"
    if not services_dir.exists():
        print("Services directory not found!")
        return 1

    all_issues = []

    for service_file in services_dir.glob("*.py"):
        if service_file.name.startswith("__"):
            continue

        issues = check_file(service_file)
        if issues:
            all_issues.extend([(service_file, issue) for issue in issues])

    if all_issues:
        print("\n❌ Error handling issues found!\n")
        for filepath, issue in all_issues:
            print(f"  {filepath.name}: {issue}")
        print("\nPlease add appropriate error handling.")
        return 1
    else:
        print("✅ Error handling check passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
