#!/usr/bin/env python3
"""
Sync OpenAPI Specification to Frontend Projects

This script synchronizes the OpenAPI specification to frontend project directories
to ensure they always have the latest API definitions.
"""

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime


def sync_openapi_spec(spec_path: Path, frontend_dirs: list[str]):
    """
    Sync OpenAPI specification to frontend directories.
    
    Args:
        spec_path: Path to the OpenAPI specification JSON file
        frontend_dirs: List of frontend directory paths to sync to
    """
    if not spec_path.exists():
        print(f"❌ Error: OpenAPI spec not found at {spec_path}")
        return False
    
    # Load the spec to validate it's valid JSON
    try:
        with open(spec_path, 'r') as f:
            spec_data = json.load(f)
        print(f"✅ Loaded OpenAPI spec v{spec_data.get('info', {}).get('version', 'unknown')}")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in OpenAPI spec: {e}")
        return False
    
    synced_count = 0
    
    for frontend_dir in frontend_dirs:
        frontend_path = Path(frontend_dir)
        
        if not frontend_path.exists():
            print(f"⚠️  Warning: Frontend directory not found: {frontend_path}")
            continue
        
        # Define target locations for OpenAPI spec in frontend projects
        target_locations = [
            frontend_path / "src" / "api" / "openapi.json",
            frontend_path / "api" / "openapi.json",
            frontend_path / "openapi.json"
        ]
        
        # Find the appropriate location
        target_path = None
        for location in target_locations:
            if location.parent.exists():
                target_path = location
                break
        
        if not target_path:
            # Create default location
            target_path = frontend_path / "src" / "api" / "openapi.json"
            target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the spec
        try:
            shutil.copy2(spec_path, target_path)
            print(f"✅ Synced to: {target_path}")
            
            # Create metadata file
            metadata_path = target_path.parent / "api-metadata.json"
            metadata = {
                "lastSync": datetime.utcnow().isoformat(),
                "version": spec_data.get("info", {}).get("version", "unknown"),
                "endpoints": len(spec_data.get("paths", {})),
                "schemas": len(spec_data.get("components", {}).get("schemas", {}))
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            synced_count += 1
            
        except Exception as e:
            print(f"❌ Error syncing to {frontend_path}: {e}")
    
    print(f"\n📊 Summary: Synced to {synced_count}/{len(frontend_dirs)} frontend projects")
    return synced_count > 0


def main():
    parser = argparse.ArgumentParser(description="Sync OpenAPI spec to frontend projects")
    parser.add_argument(
        "--spec",
        required=True,
        help="Path to the OpenAPI specification JSON file"
    )
    parser.add_argument(
        "--frontend-dirs",
        nargs="+",
        required=True,
        help="List of frontend directory paths"
    )
    
    args = parser.parse_args()
    
    spec_path = Path(args.spec)
    
    print("🔄 Syncing OpenAPI Specification to Frontend Projects")
    print("=" * 60)
    
    success = sync_openapi_spec(spec_path, args.frontend_dirs)
    
    if success:
        print("\n✅ Sync completed successfully!")
    else:
        print("\n❌ Sync failed!")
        exit(1)


if __name__ == "__main__":
    main()