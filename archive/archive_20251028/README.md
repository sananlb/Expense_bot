# Archive 2025-10-28

## Archived Deprecated Files

This directory contains files that were deprecated and removed from the production codebase during the category unification update.

### Files:

#### 1. `user.py` (from bot/services/)
**Reason for archiving:** DEPRECATED - Not used anywhere in production code

**Replacement:**
- Use `bot/utils/db_utils.py::get_or_create_user_profile_sync()` for user creation
- Use `bot/services/category.py::create_default_categories_sync()` for creating default categories

**Issue:** Contained OUTDATED category definitions (20 categories instead of the unified 16)

---

#### 2. `category_manager.py` (from bot/services/)
**Reason for archiving:** DEPRECATED - Never imported or used in the codebase

**Replacement:**
- Use `bot/services/category.py` for all category management operations
- Use `bot/services/category.py::create_default_categories_sync()` for creating default categories
- Use `bot/services/category.py::update_default_categories_language()` for language switching

**Issue:** Duplicated functionality from `bot/services/category.py` and was never used in production

---

## Category Unification Changes (2025-10-28)

**Summary:** Unified expense categories from 18-20 inconsistent categories to 16 unified categories across both languages (Russian and English).

**Removed categories:**
- ❌ АЗС (Gas Stations) - merged into "Автомобиль" (Car)
- ❌ Родственники (Relatives) - removed from defaults

**Key improvements:**
- Unified 16 categories for both RU and EN
- Fixed translation mappings (Products → Groceries, etc.)
- Fixed emoji preservation during language switching
- Updated all keyword dictionaries
- Deprecated unused helper files

**Updated files:**
- `expenses/models.py` - DEFAULT_CATEGORIES
- `bot/services/category.py` - category_mapping, create functions
- `bot/utils/language.py` - translation dictionaries
- `bot/utils/expense_categorizer.py` - keyword mappings
- `bot/utils/default_categories.py` - marked as MIGRATION ONLY

---

**Date archived:** 2025-10-28
**Archived by:** Claude Code (automated category unification)
