#!/usr/bin/env python3

"""
Generate OpenAPI specification from the FastAPI application.
This script extracts the OpenAPI schema and saves it to a file.
"""

import json
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import the FastAPI app
from app.main import app


def generate_openapi_spec(output_file: str = "openapi.json", format: str = "json"):
    """
    Generate OpenAPI specification from the FastAPI app.
    
    Args:
        output_file: Path to save the OpenAPI specification
        format: Output format ('json' or 'yaml')
    """
    # Get the OpenAPI schema
    openapi_schema = app.openapi()
    
    # Save to file
    output_path = Path(output_file)
    
    if format == "json":
        with open(output_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)
        print(f"✅ OpenAPI specification saved to: {output_path}")
    
    elif format == "yaml":
        try:
            import yaml
            with open(output_path, "w") as f:
                yaml.dump(openapi_schema, f, default_flow_style=False, sort_keys=False)
            print(f"✅ OpenAPI specification saved to: {output_path}")
        except ImportError:
            print("❌ PyYAML is not installed. Install it with: pip install pyyaml")
            sys.exit(1)
    
    else:
        print(f"❌ Unknown format: {format}. Use 'json' or 'yaml'")
        sys.exit(1)
    
    # Print summary
    print(f"\n📊 API Summary:")
    print(f"   - Title: {openapi_schema.get('info', {}).get('title')}")
    print(f"   - Version: {openapi_schema.get('info', {}).get('version')}")
    print(f"   - Total Paths: {len(openapi_schema.get('paths', {}))}")
    
    # Count operations by method
    operations = {"GET": 0, "POST": 0, "PUT": 0, "DELETE": 0, "PATCH": 0}
    for path, methods in openapi_schema.get('paths', {}).items():
        for method in methods:
            if method.upper() in operations:
                operations[method.upper()] += 1
    
    print(f"   - Operations by Method:")
    for method, count in operations.items():
        if count > 0:
            print(f"     - {method}: {count}")
    
    # Count tags
    tags = set()
    for path, methods in openapi_schema.get('paths', {}).items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and 'tags' in operation:
                tags.update(operation['tags'])
    
    print(f"   - Total Tags: {len(tags)}")
    
    # List schemas
    schemas = openapi_schema.get('components', {}).get('schemas', {})
    print(f"   - Total Schemas: {len(schemas)}")


def main():
    """Main function to handle command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate OpenAPI specification from FastAPI app"
    )
    parser.add_argument(
        "-o", "--output",
        default="openapi.json",
        help="Output file path (default: openapi.json)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["json", "yaml"],
        default="json",
        help="Output format (default: json)"
    )
    
    args = parser.parse_args()
    
    # Generate the specification
    generate_openapi_spec(args.output, args.format)


if __name__ == "__main__":
    main()