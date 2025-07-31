# Payroll Migration Scripts

This directory contains scripts for migrating from legacy payroll systems to AuraConnect.

## Directory Structure

```
migration/
├── core/               # Core migration utilities
│   ├── extract.py     # Data extraction framework
│   ├── transform.py   # Data transformation utilities
│   ├── load.py        # Data loading framework
│   └── validate.py    # Validation utilities
├── systems/           # System-specific migration scripts
│   ├── adp/          # ADP migration
│   ├── paychex/      # Paychex migration
│   ├── quickbooks/   # QuickBooks migration
│   └── workday/      # Workday migration
├── validation/        # Validation and reconciliation
│   ├── pre_migration.py
│   ├── post_migration.py
│   └── reconciliation.py
├── cutover/          # Cutover execution scripts
│   ├── pre_cutover.sh
│   ├── execute_cutover.py
│   └── post_cutover.sh
└── rollback/         # Rollback procedures
    ├── prepare_rollback.sh
    ├── execute_rollback.py
    └── verify_rollback.py
```

## Quick Start

### 1. Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit configuration
vim .env
```

### 2. Test Connection

```bash
python core/test_connections.py
```

### 3. Run Migration

```bash
# Dry run
python migrate.py --system adp --mode dry-run

# Full migration
python migrate.py --system adp --mode full
```

## Core Scripts

### Extract Framework

See [core/extract.py](core/extract.py) for the base extraction framework that all system-specific extractors inherit from.

### Transform Utilities

See [core/transform.py](core/transform.py) for common transformation functions like:
- Date formatting
- Name cleaning
- SSN encryption
- Status mapping

### Validation Framework

See [core/validate.py](core/validate.py) for validation utilities including:
- Required field checks
- Data type validation
- Business rule validation
- Referential integrity

## System-Specific Scripts

Each system has its own directory with:
- `extractor.py` - System-specific data extraction
- `mapper.py` - Field mapping configuration
- `transformer.py` - Custom transformations
- `README.md` - System-specific documentation

## Usage Examples

### ADP Migration

```bash
cd systems/adp
python migrate_adp.py --config production.yaml
```

### Validation Only

```bash
python validation/pre_migration.py --system adp --report-only
```

### Rollback

```bash
# Prepare rollback
./rollback/prepare_rollback.sh

# Execute if needed
python rollback/execute_rollback.py --confirm
```

## Configuration

All scripts use YAML configuration files. See `config/template.yaml` for structure.

## Logging

Logs are written to:
- `logs/migration_YYYYMMDD.log` - General logs
- `logs/errors_YYYYMMDD.log` - Error logs
- `logs/validation_YYYYMMDD.log` - Validation results

## Support

For issues or questions:
- Check system-specific README files
- Review logs for detailed error messages
- Contact migration-support@auraconnect.com