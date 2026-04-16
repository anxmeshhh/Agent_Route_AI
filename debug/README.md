# debug/

This folder contains **development-only** utility scripts.

> ⚠️ These files are **NOT part of the production app**. They are safe to delete after use.

| Prefix | Purpose |
|--------|---------|
| `migrate_*.py` | One-time database schema migrations |
| `fix_*.py` | One-time bug fixes / data corrections |
| `patch_*.py` | UI/JS patching scripts (superseded by direct edits) |
| `test_*.py` | Manual API/backend test scripts |
| `verify_*.py` | Verification / health checks |
| `seed_*.py` | Database seeding (orgs, superadmin, sample data) |
| `health_check.py` | System health diagnostic |
| `check_refs.py` | Reference data verification |

## Usage

Run any script from the **project root** (not from inside `debug/`):

```bash
python debug/seed_superadmin.py
python debug/health_check.py
```
