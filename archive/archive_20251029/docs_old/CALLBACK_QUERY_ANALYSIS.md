# Callback Query Handlers Analysis

**Date:** 2025-10-29
**Total Handlers:** 148
**Total Unique callback_data patterns:** 110+ (60 static + 50+ dynamic)
**Files with handlers:** 15

---

## 1. Summary by Router

| Router | Handlers | Priority | Notes |
|--------|----------|----------|-------|
| categories.py | 30 | CRITICAL | Most complex router, handles category CRUD operations |
| cashback.py | 24 | CRITICAL | Complex multi-step forms with state management |
| expense.py | 21 | CRITICAL | Core expense editing and deletion |
| recurring.py | 15 | HIGH | Recurring payment management |
| household.py | 10 | MEDIUM | Household/group features |
| settings.py | 9 | MEDIUM | User preferences and configurations |
| start.py | 8 | MEDIUM | Authentication and initial setup |
| budget.py | 6 | MEDIUM | Budget management |
| subscription.py | 6 | MEDIUM | Subscription handling |
| reports.py | 6 | MEDIUM | Report generation and viewing |
| family.py | 4 | LOW | Family expense sharing |
| referral.py | 3 | LOW | Referral system |
| menu.py | 2 | LOW | Main menu navigation |
| top5.py | 2 | LOW | Top expenses display |
| pdf_report.py | 2 | LOW | PDF report generation |
| **TOTAL** | **148** | — | — |

---

## 2. Callback Data Patterns

### 2.1 Pattern Categories

#### Menu/Navigation Patterns
```
- close
- close_menu
- close_cashback_menu
- budget_menu
- cashback_menu
- recurring_menu
- categories_menu
- expense_categories_menu
- income_categories_menu
- settings
- start
- help_main
- help_back
- help_close
```

#### Static Simple Actions
```
- add_budget
- add_category
- add_income_category
- add_recurring
- delete_budget
- delete_categories
- delete_income_categories
- delete_recurring
- edit_categories
- edit_income_categories
- edit_recurring
- cashback_add
- cashback_edit
- cashback_remove
- cashback_remove_all
- referral_stats
- referral_rewards
- family_generate
- family_copy
```

#### Dynamic ID-Based Patterns (with database IDs)
```
- budget_cat_{category.id}                  # Category selection for budget
- del_budget_{budget.id}                    # Delete specific budget
- del_cat_{cat_id}                          # Delete category
- del_income_cat_{cat.id}                   # Delete income category
- del_recurring_{payment.id}                # Delete recurring payment
- edit_cat_{cat_id}                         # Edit category
- edit_income_cat_{cat.id}                  # Edit income category
- edit_cat_name_{cat_id}                    # Edit category name
- edit_cat_icon_{cat_id}                    # Edit category icon
- edit_income_name_{category_id}            # Edit income category name
- edit_income_icon_{category_id}            # Edit income category icon
- edit_cb_{cb.id}                           # Edit cashback
- edit_expense_{expense.id}                 # Edit expense
- edit_income_{income.id}                   # Edit income
- edit_recurring_{payment.id}               # Edit recurring payment
```

#### Dynamic Selection/Navigation
```
- cashback_cat_{categories[i].id}           # Category selection
- cashback_bank_{banks[i]}                  # Bank selection
- expense_cat_{categories[i].id}            # Category for expense
- recurring_cat_{categories[i].id}          # Category for recurring
- edit_bank_{banks[i]}                      # Edit bank
```

#### Multi-Step Form Patterns (with prefix-based routing)
```
- cashback_percent_{percent_value}          # Cashback percentage
- cashback_limit_{amount}|cashback_no_limit # Spending limit
- cashback_month_{month}                    # Month selection
- view_cb_month_{month}                     # View by month
- recurring_day_{day}                       # Day of month
- set_category_{payment_id}_{category.id}   # Category assignment
```

#### State + Data Patterns (conditional forms)
```
- edit_amount_{payment_id}                  # Edit amount (in specific state)
- edit_description_{payment_id}             # Edit description
- edit_day_{payment_id}                     # Edit day
- edit_category_{payment_id}                # Edit category
- edit_field_amount                         # Field selection
- edit_field_description                    # Field selection
- edit_field_category                       # Field selection
```

#### Confirmation Patterns
```
- confirm_remove_cb_{cashback_id}           # Confirm delete cashback
- confirm_remove_all                        # Confirm delete all
- family_accept:{inv.token}                 # Accept family invite
- confirm_join:{household_id}               # Confirm household join
- offer_accept_{offer_id}                   # Accept subscription offer
- offer_decline
```

#### Settings/Configuration Patterns
```
- lang_{language_code}                      # Language selection
- tz_{timezone}                             # Timezone selection
- curr_{currency_code}                      # Currency selection
```

#### Report/Expense View Patterns
```
- expenses_month                            # Month view
- expenses_prev_month                       # Previous month
- expenses_next_month                       # Next month
- expenses_today
- show_month_start                          # Show month summary
- month_{month_number}                      # Navigate to month
```

#### Other Patterns
```
- custom_icon                               # Upload custom category icon
- no_icon                                   # No icon for category
- set_icon_{icon_name}                      # Set icon
- skip_description                          # Skip in form
- skip_edit_bank                            # Skip bank edit
- toggle_recurring_{payment_id}             # Toggle recurring on/off
- toggle_view_scope                         # Toggle personal/family view
- toggle_cashback                           # Toggle cashback feature
- pdf_generate_current                      # Generate PDF report
- pdf_report_select_month                   # Select PDF month
- pdf_report_{month}                        # Generate PDF for month
- household_budget                          # View household budget
- create_household                          # Create household
- generate_invite                           # Generate invite
- show_members                              # Show members
- rename_household                          # Rename household
- leave_household                           # Leave household
- subscription_buy_month                    # Buy 1 month subscription
- subscription_buy_six_months                # Buy 6 month subscription
- subscription_buy_month_promo              # Promo month
- subscription_buy_six_months_promo         # Promo 6 months
- subscription_promo                        # View promo
- t5:{data}                                 # Top 5 dynamic data
```

---

## 3. Naming Conventions & Patterns

### Prefix-Based Organization
```
cashback_*          → Cashback feature
category/*expense_* → Expense categories
income_*            → Income categories
recurring_*         → Recurring payments
edit_*              → Editing operations
del_*               → Deletion operations
confirm_*           → Confirmation dialogs
lang_*              → Language selection
tz_*                → Timezone selection
curr_*              → Currency selection
month_*             → Month navigation
family_*            → Family features
household_*         → Household features
subscription_*      → Subscription operations
pdf_*               → PDF report generation
t5:*                → Top 5 features (custom format)
```

### Pattern Rules
1. **Exact Match:** Simple callback like `"close"`, `"add_budget"`
2. **Prefix Match:** `c.data.startswith("cashback_")` for dynamic values
3. **Multiple Prefixes:** `c.data.startswith(("edit_expense_", "edit_income_"))`
4. **Complex Logic:** `c.data.startswith("cashback_percent_")` + FSM state
5. **Colon Separator:** `family_accept:{token}`, `family_accept:`, `confirm_join:{id}`
6. **Conditional:** `not c.data.startswith("edit_cat_name_")`

---

## 4. Dynamic vs Static Analysis

### Static Callback Data (60 unique values)
- Menu navigation buttons
- Simple action triggers
- Feature toggles
- Form field selections
- Confirmation actions

**Examples:**
```python
callback_data="close"
callback_data="cashback_menu"
callback_data="edit_categories"
callback_data="confirm_remove_all"
```

### Dynamic Callback Data (50+ patterns)
- Database record IDs (budgets, categories, expenses)
- User selections (banks, months, timezones)
- Navigation states (page numbers)
- Invitation tokens
- Configuration values

**Examples:**
```python
callback_data=f"edit_cat_{cat_id}"
callback_data=f"cashback_bank_{bank_name}"
callback_data=f"confirm_remove_cb_{cashback_id}"
callback_data=f"set_category_{payment_id}_{category.id}"
```

---

## 5. Critical Routers (by complexity)

### TIER 1: Ultra-Critical (30+ handlers)
#### categories.py (30 handlers)
- Manages expense and income categories
- Complex CRUD with icons and customization
- Edit/delete operations with confirmation
- Multi-step icon selection process
- Pattern: Mix of simple and ID-based dynamic callbacks

**Key callback patterns:**
```
categories_menu, expense_categories_menu, income_categories_menu,
add_category, add_income_category,
edit_cat_*, del_cat_*,
edit_income_cat_*, del_income_cat_*,
edit_cat_name_*, edit_cat_icon_*,
set_icon_*, custom_icon, no_icon
```

### TIER 2: Critical (20-29 handlers)
#### cashback.py (24 handlers)
- Complex multi-step cashback configuration
- Bank selection, percentage, limits, months
- Edit and removal operations with confirmation
- Heavy use of FSM states with callback routing

**Key callback patterns:**
```
cashback_menu, cashback_add, cashback_edit,
cashback_cat_*, cashback_bank_*,
cashback_percent_*, cashback_limit_*,
cashback_month_*, edit_cb_*, remove_cb_*,
confirm_remove_cb_*, confirm_remove_all
```

#### expense.py (21 handlers)
- Expense/income view and editing
- Multi-field editing with state management
- Category selection with pagination
- Deletion with confirmation
- PDF report generation

**Key callback patterns:**
```
expenses_month, expenses_prev_month, expenses_next_month,
edit_expense_*, edit_income_*,
edit_field_amount, edit_field_description, edit_field_category,
expense_cat_*, delete_expense_*, delete_income_*,
pdf_generate_current
```

### TIER 3: High Priority (10-19 handlers)
#### recurring.py (15 handlers)
- Recurring payment CRUD
- Category and day selection
- Amount and description editing
- Toggle and deletion operations

**Key callback patterns:**
```
recurring_menu, add_recurring,
recurring_cat_*, recurring_day_*,
edit_recurring_*, toggle_recurring_*,
edit_amount_*, edit_description_*, edit_day_*,
set_category_*, delete_recurring_*, del_recurring_*
```

#### household.py (10 handlers)
- Group expense management
- Household creation and member management
- Join/leave operations with confirmation
- Dynamic invite tokens

**Key callback patterns:**
```
household_budget, create_household, generate_invite,
show_members, rename_household, leave_household,
confirm_join:*, confirm_leave, cancel_action
```

### TIER 4: Medium Priority (5-9 handlers)
#### settings.py (9 handlers)
- Language, timezone, currency selection
- Conditional state-based routing
- Feature toggles (cashback, view scope)

**Key callback patterns:**
```
settings, change_language, change_timezone, change_currency,
lang_*, tz_*, curr_*,
toggle_view_scope, toggle_cashback
```

#### start.py (8 handlers)
- Initial setup and authentication
- Privacy policy acceptance
- Main menu and help navigation

**Key callback patterns:**
```
start, close, close_menu,
privacy_accept, privacy_decline,
help_main, help_back, help_close
```

#### budget.py (6 handlers)
- Budget CRUD operations
- Category selection
- Deletion with confirmation

**Key callback patterns:**
```
add_budget, delete_budget, budget_menu,
budget_cat_*, del_budget_*
```

#### subscription.py (6 handlers)
- Subscription purchasing
- Promo code handling
- Offer acceptance/decline

**Key callback patterns:**
```
menu_subscription, subscription_buy_month,
subscription_buy_six_months, subscription_buy_*_promo,
offer_accept_*, offer_decline, subscription_promo
```

#### reports.py (6 handlers)
- Expense summary views
- Month navigation
- Daily/monthly scope toggle

**Key callback patterns:**
```
expenses_today, show_month_start,
toggle_view_scope_expenses, show_diary,
month_*, back_to_summary
```

### TIER 5: Lower Priority (1-4 handlers)
#### family.py (4 handlers)
- Family group management
- Invitation tokens with colon separator

**Key callback patterns:**
```
menu_family, family_generate, family_copy,
family_accept:{token}
```

#### referral.py (3 handlers)
- Referral rewards display

**Key callback patterns:**
```
menu_referral, referral_stats, referral_rewards
```

#### top5.py (2 handlers)
- Top expenses display with custom format

**Key callback patterns:**
```
top5_menu, t5:{custom_data}
```

#### menu.py (2 handlers)
- Duplicate routing (already covered in other routers)

#### pdf_report.py (2 handlers)
- PDF report generation and month selection

**Key callback patterns:**
```
pdf_report_select_month, pdf_report_{month}
```

---

## 6. Handler Matching Strategies

### Strategy 1: Exact Equality (40% of handlers)
```python
@router.callback_query(F.data == "add_budget")
@router.callback_query(lambda c: c.data == "cashback_menu")
```

**Used for:** Static, single-action buttons

### Strategy 2: Prefix Match (35% of handlers)
```python
@router.callback_query(F.data.startswith("edit_cat_"))
@router.callback_query(lambda c: c.data.startswith("cashback_bank_"))
```

**Used for:** Dynamic ID-based callbacks, user selections

### Strategy 3: Complex Logic (15% of handlers)
```python
@router.callback_query(lambda c: c.data.startswith("edit_cat_")
                       and not c.data.startswith("edit_cat_name_"))
@router.callback_query(F.data.startswith("cashback_percent_")
                       | F.data == "cashback_no_limit")
```

**Used for:** Filtering between related handlers

### Strategy 4: Multiple Prefixes (10% of handlers)
```python
@router.callback_query(F.data.startswith(("edit_expense_", "edit_income_")))
@router.callback_query(F.data.startswith(("delete_expense_", "delete_income_")))
```

**Used for:** Handling similar operations for different types

### Strategy 5: State + Filter (5% of handlers)
```python
@router.callback_query(CashbackForm.waiting_for_category,
                      F.data.startswith("cashback_cat_"))
@router.callback_query(EditExpenseForm.choosing_field,
                      F.data == "edit_field_amount")
```

**Used for:** State machine routing with filtered data

---

## 7. Data Extraction Examples

### Simple Data
```python
# From callback_data="edit_cat_42"
category_id = callback.data.split("_")[-1]  # "42"

# From callback_data="lang_ru"
language = callback.data.split("_")[1]  # "ru"
```

### Complex Separation
```python
# From callback_data="set_category_15_42"
parts = callback.data.split("_")
payment_id = parts[2]      # "15"
category_id = parts[3]     # "42"

# From callback_data="family_accept:abc123def456"
token = callback.data.split(":")[1]  # "abc123def456"
```

---

## 8. Recommendations for Mapping Strategy

### Phase 1: Simple Migration (Low Risk)
- All 60 static callback_data values → direct 1:1 mapping
- No data extraction needed
- **Effort:** Low, **Risk:** Very Low

### Phase 2: Dynamic ID-based Migration (Medium Risk)
- All patterns with database IDs: `{prefix}_{id}`
- Requires parsing ID from callback_data
- Extract and pass as parameters
- **Effort:** Medium, **Risk:** Low

### Phase 3: Complex Multi-Parameter Migration (High Risk)
- Patterns like `set_category_{payment_id}_{category.id}`
- Custom separators (`:`, `_`)
- May need refactoring for clarity
- **Effort:** High, **Risk:** Medium

### Phase 4: State-Dependent Migration (Very High Risk)
- State + callback_data routing
- Requires understanding FSM context
- May need architectural changes
- **Effort:** Very High, **Risk:** High

---

## 9. Total Line Count Summary

- **Total callback_data assignments:** 216 (includes duplicates in keyboard creation)
- **Unique static patterns:** 60
- **Unique dynamic patterns:** 50+
- **Total handler decorators:** 148
- **Handler matching types:** 5 major strategies

---

## 10. Key Files for Reference

1. **Most complex routers:**
   - `/bot/routers/categories.py` (30 handlers)
   - `/bot/routers/cashback.py` (24 handlers)
   - `/bot/routers/expense.py` (21 handlers)

2. **State management examples:**
   - `/bot/routers/cashback.py` (CashbackForm FSM)
   - `/bot/routers/expense.py` (EditExpenseForm FSM)
   - `/bot/routers/recurring.py` (RecurringForm FSM)

3. **ID extraction patterns:**
   - Look for `.split()` operations in handlers
   - Most use `"_"` or `":"` as separators
   - Some use list indices like `categories[i].id`

---

## Conclusion

The project uses a **well-organized callback_data naming system** with:
- Clear prefix-based organization
- Consistent dynamic ID formatting
- State machine integration for complex workflows
- Mix of exact and prefix-based matching strategies

**Complexity Assessment:**
- Simple mapping: 60 static values
- Complex mapping: 50+ dynamic patterns
- Total scope: 148 handlers across 15 routers
- **Overall complexity:** Medium (well-structured, but comprehensive)
