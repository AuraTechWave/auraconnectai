#!/usr/bin/env python3

"""
Sync OpenAPI specification to frontend projects.
Ensures frontend stays in sync with backend API changes.
"""

import json
import shutil
import sys
import os
from pathlib import Path
from datetime import datetime
import hashlib

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def sync_to_frontend(frontend_dirs: list, openapi_file: Path):
    """
    Sync OpenAPI spec to multiple frontend directories.
    
    Args:
        frontend_dirs: List of frontend project directories
        openapi_file: Path to the OpenAPI specification file
    """
    if not openapi_file.exists():
        print(f"❌ OpenAPI file not found: {openapi_file}")
        sys.exit(1)
    
    checksum = calculate_checksum(openapi_file)
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    for frontend_dir in frontend_dirs:
        frontend_path = Path(frontend_dir)
        if not frontend_path.exists():
            print(f"⚠️  Frontend directory not found: {frontend_path}")
            continue
        
        # Common locations for API specs in frontend projects
        possible_destinations = [
            frontend_path / "src" / "api" / "openapi.json",
            frontend_path / "src" / "services" / "openapi.json",
            frontend_path / "api" / "openapi.json",
            frontend_path / "openapi.json",
        ]
        
        # Find the first existing directory
        destination = None
        for dest in possible_destinations:
            if dest.parent.exists():
                destination = dest
                break
        
        if not destination:
            # Create default location
            destination = frontend_path / "src" / "api" / "openapi.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the file
        shutil.copy2(openapi_file, destination)
        print(f"✅ Copied to: {destination}")
        
        # Create metadata file
        metadata = {
            "source": str(openapi_file),
            "destination": str(destination),
            "timestamp": timestamp,
            "checksum": checksum,
            "version": app.version,
            "syncedBy": "sync_openapi_to_frontend.py"
        }
        
        metadata_file = destination.parent / "openapi-metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"   Created metadata: {metadata_file}")
        
        # Create TypeScript types generation script if it doesn't exist
        create_typescript_generator(destination.parent)


def create_typescript_generator(api_dir: Path):
    """Create a TypeScript types generator script."""
    generator_script = api_dir / "generate-types.ts"
    
    if not generator_script.exists():
        script_content = '''#!/usr/bin/env node

/**
 * Generate TypeScript types from OpenAPI specification
 * 
 * Usage: npx ts-node generate-types.ts
 */

import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

// You can use openapi-typescript or similar tools
// npm install -D openapi-typescript

async function generateTypes() {
  const openapiPath = join(__dirname, 'openapi.json');
  const outputPath = join(__dirname, 'types.ts');
  
  try {
    // Read OpenAPI spec
    const spec = JSON.parse(readFileSync(openapiPath, 'utf-8'));
    
    // Basic type generation (use a proper tool in production)
    let types = `// Auto-generated from OpenAPI spec
// Generated at: ${new Date().toISOString()}
// API Version: ${spec.info.version}

`;
    
    // Generate types from schemas
    const schemas = spec.components?.schemas || {};
    for (const [name, schema] of Object.entries(schemas)) {
      types += `export interface ${name} {\\n`;
      // Add properties (simplified - use proper generator)
      types += `  // TODO: Generate from schema\\n`;
      types += `}\\n\\n`;
    }
    
    writeFileSync(outputPath, types);
    console.log(`✅ Generated types at: ${outputPath}`);
    
  } catch (error) {
    console.error('❌ Error generating types:', error);
    process.exit(1);
  }
}

generateTypes();
'''
        
        with open(generator_script, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(generator_script, 0o755)
        print(f"   Created type generator: {generator_script}")


def create_api_client_config(api_dir: Path, openapi_spec: dict):
    """Create API client configuration for frontend."""
    config = {
        "baseURL": openapi_spec.get('x-frontend', {}).get('apiBaseUrl', '/api'),
        "version": openapi_spec['info']['version'],
        "auth": {
            "tokenHeader": "Authorization",
            "tokenPrefix": "Bearer",
            "refreshEndpoint": "/api/v1/auth/refresh",
            "loginEndpoint": "/api/v1/auth/login",
            "logoutEndpoint": "/api/v1/auth/logout"
        },
        "features": openapi_spec.get('x-frontend', {}).get('features', {}),
        "endpoints": {}
    }
    
    # Extract endpoint patterns
    for path, methods in openapi_spec.get('paths', {}).items():
        for method, operation in methods.items():
            if method in ['get', 'post', 'put', 'patch', 'delete']:
                operation_id = operation.get('operationId', f"{method}_{path}")
                config['endpoints'][operation_id] = {
                    "path": path,
                    "method": method.upper(),
                    "tags": operation.get('tags', [])
                }
    
    config_file = api_dir / "api-config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"   Created API config: {config_file}")


def main():
    """Main sync function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync OpenAPI spec to frontend projects"
    )
    parser.add_argument(
        "--spec",
        default="openapi.json",
        help="Path to OpenAPI specification file"
    )
    parser.add_argument(
        "--frontend-dirs",
        nargs="+",
        default=["../frontend", "../customer-web", "../mobile"],
        help="Frontend project directories"
    )
    parser.add_argument(
        "--generate-types",
        action="store_true",
        help="Generate TypeScript types"
    )
    
    args = parser.parse_args()
    
    # Generate fresh OpenAPI spec
    print("🔄 Generating OpenAPI specification...")
    os.system(f"python {backend_dir}/scripts/generate_openapi_spec.py -o {args.spec}")
    
    openapi_file = Path(args.spec)
    
    # Load the spec for additional processing
    with open(openapi_file, 'r') as f:
        openapi_spec = json.load(f)
    
    # Sync to frontend directories
    print("\n📤 Syncing to frontend projects...")
    sync_to_frontend(args.frontend_dirs, openapi_file)
    
    # Create API client configs
    for frontend_dir in args.frontend_dirs:
        frontend_path = Path(frontend_dir)
        if frontend_path.exists():
            api_dir = frontend_path / "src" / "api"
            if api_dir.exists():
                create_api_client_config(api_dir, openapi_spec)
    
    print("\n✅ Sync completed successfully!")
    print(f"   Version: {openapi_spec['info']['version']}")
    print(f"   Endpoints: {len(openapi_spec.get('paths', {}))}")
    print(f"   Schemas: {len(openapi_spec.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    main()