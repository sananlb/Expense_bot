# Callback Query Handler Examples & Patterns

**Purpose:** Practical examples of how callbacks are currently handled, patterns to follow for migration

---

## 1. Simple Static Callback Handlers

### Example 1: Menu Navigation
```python
# From start.py
@router.callback_query(F.data == "close")
async def close_menu(callback: CallbackQuery, state: FSMContext):
    """Close current menu/dialog"""
    await callback.message.delete()
    await state.clear()

@router.callback_query(F.data == "start")
async def start_callback(callback: CallbackQuery):
    """Main menu button"""
    await callback.answer()
    await show_main_menu(callback.message)
```

**Migration Pattern:**
```python
# Current: callback_data="close"
# Key: "close"
# Handler: Matches F.data == "close"
# Data extraction: None needed
# Complexity: Trivial
```

### Example 2: Feature Toggle
```python
# From settings.py
@router.callback_query(F.data == "toggle_cashback")
async def toggle_cashback(callback: CallbackQuery):
    """Enable/disable cashback feature"""
    user = get_user_from_db(callback.from_user.id)
    user.cashback_enabled = not user.cashback_enabled
    user.save()
    await callback.answer("Кэшбэк отключен" if not user.cashback_enabled else "Кэшбэк включен")
```

**Migration Pattern:**
```python
# Current: callback_data="toggle_cashback"
# Key: "toggle_cashback"
# No data extraction needed
# Simple toggle operation
```

---

## 2. Dynamic Single-ID Callbacks

### Example 3: Edit with ID Extraction
```python
# From categories.py
@router.callback_query(lambda c: c.data.startswith("edit_cat_"))
async def edit_category(callback: CallbackQuery, state: FSMContext):
    """Edit specific category"""
    # Extract category ID
    cat_id = int(callback.data.split("_")[-1])
    category = Category.objects.get(id=cat_id)

    # Show edit options
    await callback.message.edit_text(
        f"Редактирование: {category.name}",
        reply_markup=get_category_edit_keyboard(category)
    )
    await state.set_state(CategoryForm.editing)
```

**Migration Pattern:**
```python
# Current: callback_data=f"edit_cat_{cat_id}"
# Key pattern: "edit_cat_"
# Data extraction: Split by "_", take last element
# Example: "edit_cat_42" → cat_id = 42
# Complexity: Simple (single ID)

# Handler decorator:
@router.callback_query(F.data.startswith("edit_cat_"))
# OR with state:
@router.callback_query(CategoriesForm.waiting, F.data.startswith("edit_cat_"))
```

### Example 4: Multiple Occurrences with Loop
```python
# From categories.py (simplified)
for category in editable_categories:
    # Each creates unique callback_data with category.id
    row.append(InlineKeyboardButton(
        text=get_category_display_name(category, lang),
        callback_data=f"edit_cat_{category.id}"
    ))

# Handler remains same - receives category.id in callback_data
@router.callback_query(lambda c: c.data.startswith("edit_cat_"))
async def edit_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[-1])
    # ... handle edit
```

**Migration Pattern:**
```python
# Even though there are many buttons with different IDs,
# they all go to same handler with pattern matching
# Handler extracts actual ID from callback_data
# Example IDs: 1, 42, 100, etc.
```

---

## 3. Dynamic Multi-ID Callbacks

### Example 5: Two-Parameter Extraction
```python
# From recurring.py
# Creating callback with payment_id and category_id
for category in categories:
    button = InlineKeyboardButton(
        text=get_category_display_name(category, lang),
        callback_data=f"set_category_{payment_id}_{category.id}"
    )

# Handler extracting both IDs
@router.callback_query(lambda c: c.data.startswith("set_category_"))
async def set_category(callback: CallbackQuery):
    """Set category for recurring payment"""
    parts = callback.data.split("_")
    payment_id = int(parts[2])      # "set_category_15_42" → 15
    category_id = int(parts[3])     # "set_category_15_42" → 42

    payment = RecurringPayment.objects.get(id=payment_id)
    payment.category_id = category_id
    payment.save()
```

**Migration Pattern:**
```python
# Current: callback_data=f"set_category_{payment_id}_{category_id}"
# Format: prefix_param1_param2
# Extraction: Split by "_", indices [2] and [3]
# Example: "set_category_15_42" → payment_id=15, category_id=42
# Complexity: Moderate (careful index handling)
```

---

## 4. Custom Separator Callbacks (Colon)

### Example 6: Token-Based Callback
```python
# From family.py
# Creating callback with token
invite = FamilyInvitation.objects.create(...)
button = InlineKeyboardButton(
    text="Принять приглашение",
    callback_data=f"family_accept:{invite.token}"
)

# Handler extracting token
@router.callback_query(F.data.startswith("family_accept:"))
async def accept_family_invite(callback: CallbackQuery):
    """Accept family group invitation"""
    token = callback.data.split(":")[1]

    invite = FamilyInvitation.objects.get(token=token)
    invite.accept(callback.from_user.id)

    await callback.answer("Приглашение принято!")
```

**Migration Pattern:**
```python
# Current: callback_data=f"family_accept:{invite.token}"
# Separator: Colon ":"
# Extraction: Split by ":", take [1]
# Example: "family_accept:abc123token456" → token = "abc123token456"
# Complexity: Simple (single parameter, clear separator)
```

### Example 7: Household Confirmation with ID
```python
# From household.py
# Creating callback with household_id
button = InlineKeyboardButton(
    text="Подтвердить присоединение",
    callback_data=f"confirm_join:{household_id}"
)

# Handler
@router.callback_query(F.data.startswith("confirm_join:"))
async def confirm_join_household(callback: CallbackQuery):
    """Confirm joining household"""
    household_id = callback.data.split(":")[1]

    household = Household.objects.get(id=household_id)
    # ... add user to household
```

**Migration Pattern:**
```python
# Colon-separated for IDs
# Good for: tokens, UUIDs, or any ID that might contain underscores
```

---

## 5. Configuration/Selection Callbacks

### Example 8: Language Selection
```python
# From settings.py
# Creating keyboard with language options
languages = ["en", "ru", "es", "de"]
for lang_code in languages:
    button = InlineKeyboardButton(
        text=f"🌐 {language_names[lang_code]}",
        callback_data=f"lang_{lang_code}"
    )

# Handler
@router.callback_query(SettingsStates.language, F.data.startswith("lang_"))
async def select_language(callback: CallbackQuery, state: FSMContext):
    """Change user language"""
    lang_code = callback.data.split("_")[1]

    user = User.objects.get(id=callback.from_user.id)
    user.language = lang_code
    user.save()

    await state.clear()
    await callback.answer(f"Язык изменен на {language_names[lang_code]}")
```

**Migration Pattern:**
```python
# Current: callback_data=f"lang_{lang_code}"
# Format: prefix_value
# Extraction: Split by "_", take [1]
# Example: "lang_ru" → lang_code = "ru"
# FSM State: SettingsStates.language required
# Complexity: Simple
```

### Example 9: Category + Limit Combinations
```python
# From cashback.py
# Creating buttons for spending limits
limits = ["1000", "2000", "3000", "5000", "no_limit"]
for limit in limits:
    if limit == "no_limit":
        cb_data = "cashback_no_limit"
    else:
        cb_data = f"cashback_limit_{limit}"

    button = InlineKeyboardButton(text=f"₽{limit}", callback_data=cb_data)

# Handler (single handler for both patterns)
@router.callback_query(lambda c: c.data.startswith("cashback_limit_")
                      or c.data == "cashback_no_limit",
                      CashbackForm.waiting_for_limit)
async def select_cashback_limit(callback: CallbackQuery, state: FSMContext):
    """Select cashback spending limit"""
    if callback.data == "cashback_no_limit":
        limit = None
    else:
        limit = int(callback.data.split("_")[-1])

    # ... save limit
```

**Migration Pattern:**
```python
# Mixed: regular prefix pattern + exception
# Requires conditional logic in handler
# Pattern 1: "cashback_limit_1000" → extract "1000"
# Pattern 2: "cashback_no_limit" → special case
# Complexity: Moderate (conditional extraction)
```

---

## 6. FSM State + Callback Combinations

### Example 10: State-Dependent Routing
```python
# From expense.py
# Handler 1: Choose which field to edit
@router.callback_query(EditExpenseForm.choosing_field, F.data == "edit_field_amount")
async def edit_amount(callback: CallbackQuery, state: FSMContext):
    """User chose to edit amount"""
    await callback.message.edit_text("Введите новую сумму:")
    await state.set_state(EditExpenseForm.editing_amount)

# Handler 2: Choose which field to edit
@router.callback_query(EditExpenseForm.choosing_field, F.data == "edit_field_category")
async def edit_category(callback: CallbackQuery, state: FSMContext):
    """User chose to edit category"""
    categories = get_categories(callback.from_user.id)
    keyboard = build_category_keyboard(categories)
    await callback.message.edit_text("Выберите категорию:", reply_markup=keyboard)
    await state.set_state(EditExpenseForm.editing_category)

# Handler 3: Category selection (only valid in certain state)
@router.callback_query(EditExpenseForm.editing_category, F.data.startswith("expense_cat_"))
async def process_category(callback: CallbackQuery, state: FSMContext):
    """Category selected while in editing_category state"""
    cat_id = int(callback.data.split("_")[-1])
    # ... save category
```

**Migration Pattern:**
```python
# FSM State is PRIMARY filter, callback_data is SECONDARY
# Order matters in decorator:
#   1. State filter (must be in correct state)
#   2. Data filter (matches specific callback pattern)
# Both must be true to execute handler
# Complexity: Complex (state-dependent routing)
```

### Example 11: State Chain Example
```python
# From cashback.py - multi-step form

# Step 1: Show banks (first state)
@router.callback_query(lambda c: c.data == "cashback_add")
async def add_cashback(callback: CallbackQuery, state: FSMContext):
    banks = get_banks()
    keyboard = build_bank_keyboard(banks)
    await callback.message.edit_text("Выберите банк:", reply_markup=keyboard)
    await state.set_state(CashbackForm.waiting_for_bank)

# Step 2: Bank selected, show categories (second state)
@router.callback_query(lambda c: c.data.startswith("cashback_bank_"),
                      CashbackForm.waiting_for_bank)
async def select_bank(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.split("_")[-1]
    data = await state.get_data()
    data['bank'] = bank
    await state.update_data(data)

    categories = get_categories()
    keyboard = build_category_keyboard(categories)
    await callback.message.edit_text("Выберите категорию:", reply_markup=keyboard)
    await state.set_state(CashbackForm.waiting_for_category)

# Step 3: Category selected, show percentage (third state)
@router.callback_query(lambda c: c.data.startswith("cashback_cat_"),
                      CashbackForm.waiting_for_category)
async def select_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    data['category_id'] = cat_id
    await state.update_data(data)

    percentages = ["1%", "2%", "3%", "5%"]
    keyboard = build_percentage_keyboard(percentages)
    await callback.message.edit_text("Выберите % кэшбэка:", reply_markup=keyboard)
    await state.set_state(CashbackForm.waiting_for_percent)
```

**Migration Pattern:**
```python
# State machine flow:
#   State 1: waiting_for_bank
#     ↓ (on "cashbank_bank_*")
#   State 2: waiting_for_category
#     ↓ (on "cashback_cat_*")
#   State 3: waiting_for_percent
#     ↓ (on "cashback_percent_*")
#   State 4: waiting_for_limit
#     ↓ (on "cashback_limit_*")
#   State 5: Complete
#
# Each state only accepts specific callbacks
# This prevents out-of-order operations
```

---

## 7. Complex Filtering Patterns

### Example 12: Negative Conditions (Exclusion)
```python
# From categories.py
# This handler matches "edit_cat_*" but NOT "edit_cat_name_*" and NOT "edit_cat_icon_*"
@router.callback_query(
    lambda c: c.data.startswith("edit_cat_")
    and not c.data.startswith("edit_cat_name_")
    and not c.data.startswith("edit_cat_icon_")
)
async def edit_category(callback: CallbackQuery, state: FSMContext):
    """Edit category (but not name or icon specifically)"""
    cat_id = int(callback.data.split("_")[-1])
    # ... show general edit menu
```

**Migration Pattern:**
```python
# Pattern: prefix MATCH + prefix NOT MATCH
# Use case: Similar handlers with overlapping prefixes
# Must list all exclusions explicitly
# Complexity: Moderate (filter logic)
# Problem: Brittle if new similar patterns added
```

### Example 13: Multiple Prefix Matching
```python
# From expense.py
@router.callback_query(lambda c: c.data.startswith(("edit_expense_", "edit_income_")))
async def edit_expense_or_income(callback: CallbackQuery, state: FSMContext):
    """Handle both expense and income editing"""
    if callback.data.startswith("edit_expense_"):
        item_id = int(callback.data.split("_")[-1])
        item = Expense.objects.get(id=item_id)
    else:  # edit_income_
        item_id = int(callback.data.split("_")[-1])
        item = Income.objects.get(id=item_id)

    # ... show edit menu for both types
```

**Migration Pattern:**
```python
# Multiple prefixes in tuple: startswith(("prefix1_", "prefix2_"))
# Allows consolidating similar handlers
# Must determine type from callback_data itself
# Complexity: Simple (duplicate logic)
```

---

## 8. Data Structure in Callbacks

### Pattern: Category List Buttons
```python
# From categories.py (simplified iteration)
categories = Category.objects.filter(user=user)
editable_categories = [cat for cat in categories if can_edit(cat, user)]

for i in range(0, len(editable_categories), 2):
    row = [InlineKeyboardButton(
        text=get_category_display_name(editable_categories[i], lang),
        callback_data=f"edit_cat_{editable_categories[i].id}"
    )]

    if i + 1 < len(editable_categories):
        row.append(InlineKeyboardButton(
            text=get_category_display_name(editable_categories[i + 1], lang),
            callback_data=f"edit_cat_{editable_categories[i + 1].id}"
        ))

# Note: Multiple buttons created with different IDs
# All route to same handler which extracts the ID
```

**Migration Pattern:**
```python
# Dynamic list generation
# IDs from database (not hardcoded)
# Handler must parse ID from callback_data
# Different IDs = different data, same logic
# Common pattern: loop through items, create buttons
```

---

## 9. Pagination & Navigation

### Example 14: Month Navigation
```python
# From reports.py
@router.callback_query(lambda c: c.data.startswith("month_"))
async def navigate_month(callback: CallbackQuery):
    """Navigate to different month"""
    month_num = int(callback.data.split("_")[1])

    expenses = get_expenses_for_month(callback.from_user.id, month_num)
    text = format_monthly_report(expenses)

    # Build navigation buttons for next/prev month
    keyboard = [
        [InlineKeyboardButton(text="← Prev", callback_data=f"month_{month_num - 1}"),
         InlineKeyboardButton(text="Next →", callback_data=f"month_{month_num + 1}")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_summary")]
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
```

**Migration Pattern:**
```python
# Navigation callbacks often form chains
# month_1 → month_2 → month_3, etc.
# Infinite possibilities (not hardcoded)
# Handler must safely handle edge cases
```

---

## 10. Special Patterns & Edge Cases

### Example 15: Custom Separator (Colon)
```python
# Top 5 expenses (from top5.py)
# Uses custom format with multiple colons
@router.callback_query(F.data.startswith("t5:"))
async def handle_top5(callback: CallbackQuery):
    """Handle top 5 custom format"""
    # Format might be: "t5:category:period"
    parts = callback.data.split(":")
    if len(parts) == 3:
        category = parts[1]
        period = parts[2]
    # ... handle accordingly
```

**Migration Pattern:**
```python
# Non-standard format
# Uses colon as separator
# May contain multiple values
# Parsing requires understanding the format
```

### Example 16: No Parameter Variation
```python
# Close button (appears everywhere but does same thing)
@router.callback_query(F.data == "close")
async def close_dialog(callback: CallbackQuery, state: FSMContext):
    """Universal close button"""
    await callback.message.delete()
    await state.clear()

# This same handler handles "close" from ANY keyboard
# It's the same operation regardless of context
```

**Migration Pattern:**
```python
# Universal buttons (close, back, cancel)
# Same logic regardless of origin
# No data extraction needed
# Simplest case for migration
```

---

## Summary Table: Handler Complexity by Type

| Pattern | Count | Complexity | Example | Extraction |
|---------|-------|-----------|---------|-----------|
| Static exact match | 60 | Trivial | `close` | None |
| Single ID | 35 | Simple | `edit_cat_{id}` | `split("_")[-1]` |
| Multiple IDs | 8 | Moderate | `set_category_{id1}_{id2}` | Multiple indices |
| Colon separator | 5 | Simple | `family_accept:{token}` | `split(":")[1]` |
| Configuration | 8 | Simple | `lang_{code}` | `split("_")[1]` |
| Complex logic | 5-10 | Complex | Multiple conditions | Custom parsing |
| **Total** | **148** | — | — | — |

---

## Migration Checklist Template

For each handler type:

```markdown
## [Handler Name]
- [ ] Location: `/bot/routers/[file].py`
- [ ] Current decorator: `@router.callback_query(...)`
- [ ] Callback data pattern: `"pattern_*"`
- [ ] Data extraction: None / `split("_")` / Custom
- [ ] FSM state required: None / [State]
- [ ] Related handlers: [other callbacks]
- [ ] Migration approach: [Trivial / Simple / Moderate / Complex]
- [ ] Tests needed: [specific test scenarios]
- [ ] Risk level: [Very Low / Low / Medium / High]
```

Example:
```markdown
## Edit Category Handler
- [ ] Location: `/bot/routers/categories.py`
- [ ] Current decorator: `@router.callback_query(lambda c: c.data.startswith("edit_cat_"))`
- [ ] Callback data pattern: `"edit_cat_{cat_id}"`
- [ ] Data extraction: `int(callback.data.split("_")[-1])`
- [ ] FSM state required: None
- [ ] Related handlers: `del_cat_`, `edit_cat_name_`, `edit_cat_icon_`
- [ ] Migration approach: Simple
- [ ] Tests needed: Various category IDs, edge cases
- [ ] Risk level: Low
```

