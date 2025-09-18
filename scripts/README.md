# Scripts Directory – AuraConnect

This directory contains helper scripts for development, deployment, and module scaffolding.

## 🛠️ Available Scripts

### `migrate_staff.sh`
Executes Alembic migrations specifically for the Staff Management module. Useful for applying or reverting schema changes quickly.

### `scaffold_staff_module.sh`
Bootstraps the Staff Management module with pre-defined folder structure, basic API endpoints, and DB schema files.

### `scaffold_shift_attendance.sh`
Creates boilerplate files and structure for the Shift Scheduling & Attendance system, part of the Staff Management flow.

### `create_github_issues.py`
Bulk-creates GitHub issues from a YAML backlog using the GitHub CLI. Pass a spec file (see `project_management/backlog/phase1_foundations.yaml`) and the script will call `gh issue create` for each entry. Supports a `--dry-run` flag to preview commands.

---

> 💡 Tip: Run these scripts from the project root directory.
