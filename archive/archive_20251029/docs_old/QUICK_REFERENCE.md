# Quick Reference - Callback Query Analysis

## At a Glance

| Metric | Value |
|--------|-------|
| **Total Handlers** | 148 |
| **Unique Patterns** | 107 |
| **Files** | 15 routers |
| **Complexity** | Medium (well-structured) |
| **Est. Migration Time** | 14-29 hours |

---

## Handler Count by Router

```
categories.py     ████████████████████████████░░  30  (20%)
cashback.py       ████████████████░░░░░░░░░░░░░░░  24  (16%)
expense.py        ███████████████░░░░░░░░░░░░░░░░░  21  (14%)
recurring.py      ███████████░░░░░░░░░░░░░░░░░░░░░  15  (10%)
household.py      ██████░░░░░░░░░░░░░░░░░░░░░░░░░░  10  (7%)
settings.py       █████░░░░░░░░░░░░░░░░░░░░░░░░░░░  9   (6%)
start.py          █████░░░░░░░░░░░░░░░░░░░░░░░░░░░  8   (5%)
budget.py         ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  6   (4%)
subscription.py   ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  6   (4%)
reports.py        ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  6   (4%)
family.py         ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  4   (3%)
referral.py       █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  3   (2%)
top5.py           █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  2   (1%)
menu.py           █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  2   (1%)
pdf_report.py     █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  2   (1%)
                                          TOTAL: 148
```

---

## Callback Pattern Distribution

```
Static Literals (60 patterns)        ███████████░░░░░░░░░░░░░░░░  56%
Single ID (35 patterns)              ████████░░░░░░░░░░░░░░░░░░░░  33%
Multi ID (8 patterns)                ██░░░░░░░░░░░░░░░░░░░░░░░░░░  7%
Config Values (8 patterns)           ██░░░░░░░░░░░░░░░░░░░░░░░░░░  7%
                                              TOTAL: 107 unique
```

---

## Complexity by Handler Type

| Type | Count | Complexity | Time | Risk |
|------|-------|-----------|------|------|
| Static exact match | 60 | Trivial | <1h | Very Low |
| Single ID extraction | 35 | Simple | 2-4h | Low |
| Multi ID / Complex | 12 | Moderate | 4-8h | Medium |
| FSM state-dependent | 30 | Complex | 8-16h | High |
| Edge cases | 11 | Complex | 2-4h | Medium |

---

## Key Patterns at a Glance

### Navigation (14 patterns)
```
close, start, help_main, settings, budget_menu, etc.
↓
Complexity: TRIVIAL
Action: 1:1 mapping, no logic needed
```

### Category Operations (30 patterns)
```
edit_cat_{id}, del_cat_{id}, edit_cat_name_{id}, etc.
↓
Complexity: MODERATE
Action: ID extraction, careful filtering
Risk: Overlapping prefixes
```

### Cashback (24 patterns)
```
cashback_cat_*, cashback_bank_*, cashback_percent_*, etc.
↓
Complexity: COMPLEX
Action: Multi-step FSM with 9 states
Risk: State order critical
```

### Expense Editing (21 patterns)
```
edit_expense_{id}, edit_field_*, expense_cat_{id}, etc.
↓
Complexity: MODERATE
Action: State-based field editing
Risk: Multiple state transitions
```

### Recurring Payments (15 patterns)
```
recurring_cat_*, edit_amount_{id}, set_category_{id}_{id}, etc.
↓
Complexity: MODERATE
Action: ID extraction, state handling
Risk: Multi-ID patterns
```

### Settings (9 patterns)
```
lang_{code}, tz_{timezone}, curr_{code}, toggle_*
↓
Complexity: SIMPLE
Action: Configuration value extraction
Risk: Very Low
```

---

## Data Extraction Patterns (Quick Guide)

```python
# Pattern 1: Simple suffix
"edit_cat_42"  →  int(callback.data.split("_")[-1])  →  42

# Pattern 2: Known index
"lang_ru"  →  callback.data.split("_")[1]  →  "ru"

# Pattern 3: Multiple indices
"set_category_15_42"  →  parts = split("_"); [2]=15, [3]=42

# Pattern 4: Colon separator
"family_accept:token123"  →  callback.data.split(":")[1]  →  "token123"

# Pattern 5: Type conversion
"del_budget_999"  →  int(callback.data.split("_")[-1])  →  999
```

---

## Critical Routers (Focus Areas)

### 🔴 CRITICAL: categories.py (30 handlers)
```
Risk: MEDIUM (overlapping prefixes)
Patterns: edit_cat_*, del_cat_*, edit_cat_name_*, edit_cat_icon_*
Strategy: Order decorators carefully, test all variations
Note: Most complex filtering required
```

### 🔴 CRITICAL: cashback.py (24 handlers)
```
Risk: HIGH (9-state FSM)
Patterns: cashback_cat_*, cashback_bank_*, cashback_percent_*
Strategy: Map complete state flow, test all paths
Note: Must not allow out-of-order operations
```

### 🟡 HIGH: expense.py (21 handlers)
```
Risk: MEDIUM (core functionality)
Patterns: edit_expense_*, edit_field_*, expense_cat_*
Strategy: Test with real data, verify field editing logic
Note: High usage volume
```

### 🟡 HIGH: recurring.py (15 handlers)
```
Risk: MEDIUM (multi-ID patterns)
Patterns: set_category_{id}_{id}, edit_amount_{id}, etc.
Strategy: Careful ID extraction, boundary testing
Note: Payment scheduling critical
```

---

## Migration Phases

### Phase 1: Static Patterns (Low Risk)
```
✓ 60 patterns - direct 1:1 mapping
✓ No logic changes
✓ Time: < 1 hour
✓ Risk: Very Low
```

### Phase 2: Single-ID Patterns (Low-Medium Risk)
```
✓ 35 patterns - simple extraction
✓ split("_")[-1] logic
✓ Time: 2-4 hours
✓ Risk: Low
```

### Phase 3: Complex Patterns (Medium Risk)
```
⚠ 12 patterns - multi-ID, complex logic
⚠ Custom parsing, boundary checks
⚠ Time: 4-8 hours
⚠ Risk: Medium
```

### Phase 4: State Integration (High Risk)
```
⚠ 30+ handlers with FSM states
⚠ Complete state flow testing
⚠ Time: 8-16 hours
⚠ Risk: High
```

**Total: 14-29 hours + testing**

---

## Handler Matching Strategies

```python
# Strategy 1: Exact Match (40% of handlers)
@router.callback_query(F.data == "exact_value")

# Strategy 2: Prefix Match (35% of handlers)
@router.callback_query(F.data.startswith("prefix_"))

# Strategy 3: Multiple Prefixes (10% of handlers)
@router.callback_query(F.data.startswith(("p1_", "p2_")))

# Strategy 4: Complex Logic (15% of handlers)
@router.callback_query(lambda c: c.data.startswith("edit_cat_")
                      and not c.data.startswith("edit_cat_name_"))

# Strategy 5: State + Filter (5% of handlers)
@router.callback_query(FSMState, F.data.startswith("pattern_"))
```

---

## Top Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Complex filtering overlap | MEDIUM | Order decorators by specificity |
| FSM state chains | HIGH | Integration tests for each path |
| ID extraction errors | MEDIUM | Input validation, try-catch blocks |
| Pagination edge cases | LOW | Boundary checks (month 0-12, day 1-31) |
| Stale cache/database | LOW | Support both old and new formats |

---

## Testing Checklist

- [ ] **Unit Tests**: Each extraction pattern
- [ ] **State Tests**: All FSM state transitions
- [ ] **Integration Tests**: Complete workflows
- [ ] **Edge Cases**: Invalid data, boundary values
- [ ] **Load Tests**: Concurrent user handling
- [ ] **Regression Tests**: Ensure no breakage of existing features
- [ ] **Rollback Plan**: Ability to revert quickly

---

## Files Generated

1. **CALLBACK_QUERY_ANALYSIS.md** (18 KB)
   - Main comprehensive analysis
   - Patterns, routers, complexity assessment
   - Recommendations by phase

2. **CALLBACK_DATA_REFERENCE.md** (16 KB)
   - Complete reference of all 107 patterns
   - Pattern classification and extraction examples
   - FSM state integration guide

3. **CALLBACK_HANDLER_EXAMPLES.md** (20 KB)
   - Real code examples from project
   - Implementation patterns
   - Migration checklist template

4. **CALLBACK_ANALYSIS_SUMMARY.txt** (19 KB)
   - Executive summary
   - Key statistics and breakdown
   - Risk analysis and strategy

5. **QUICK_REFERENCE.md** (This file)
   - At-a-glance summary
   - Quick lookup tables
   - Decision trees

---

## Decision Tree: How to Migrate a Callback

```
START
  ↓
Is callback_data hardcoded without variables?
  ├─ YES → Phase 1: Static Pattern
  │         Effort: < 1 hour
  │         Risk: Very Low
  │         Action: 1:1 copy mapping
  │
  └─ NO → Does it have underscore separator with IDs?
           ├─ YES (single ID) → Phase 2: Single-ID Pattern
           │                     Effort: 2-4 hours
           │                     Risk: Low
           │                     Action: Extract with split("_")[-1]
           │
           └─ NO → Does it have multiple IDs or special separator?
                    ├─ YES → Phase 3: Complex Pattern
                    │         Effort: 4-8 hours
                    │         Risk: Medium
                    │         Action: Custom parsing logic
                    │
                    └─ NO → Is it tied to FSM state?
                             ├─ YES → Phase 4: State-Dependent
                             │         Effort: 8-16 hours
                             │         Risk: High
                             │         Action: Map state flow, test thoroughly
                             │
                             └─ NO → ERROR: Unknown pattern
                                     Action: Analyze code, document pattern
```

---

## Success Criteria

- [x] All 148 handlers mapped
- [x] All 107 patterns documented
- [x] Extraction logic defined
- [x] State flows understood
- [ ] Code migrated (in progress)
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Load tests pass
- [ ] Deployed to production
- [ ] Monitored for 24 hours
- [ ] Zero regressions

---

## Contact & Questions

For detailed information, refer to:
1. **CALLBACK_QUERY_ANALYSIS.md** - Full technical details
2. **CALLBACK_DATA_REFERENCE.md** - Complete pattern catalog
3. **CALLBACK_HANDLER_EXAMPLES.md** - Implementation examples
4. **CALLBACK_ANALYSIS_SUMMARY.txt** - Executive overview

Each file is self-contained and can be read independently.

---

**Analysis Date:** 2025-10-29
**Project:** Expense Bot
**Scope:** Complete callback_query survey (15 routers, 148 handlers)
