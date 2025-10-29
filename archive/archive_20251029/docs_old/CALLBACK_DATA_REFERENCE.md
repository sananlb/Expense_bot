# Complete Callback Data Reference Guide

**Total Unique Patterns:** 107
**Last Updated:** 2025-10-29

---

## Full List of All Callback Data Patterns (107 total)

### Navigation & Menu (14 patterns)
1. `close` - Close current dialog/menu
2. `close_menu` - Close main menu (alias for close)
3. `close_cashback_menu` - Close cashback menu specifically
4. `budget_menu` - Show budget management menu
5. `cashback_menu` - Show cashback management menu
6. `recurring_menu` - Show recurring payments menu
7. `categories_menu` - Main categories menu
8. `expense_categories_menu` - Expense category management
9. `income_categories_menu` - Income category management
10. `settings` - Settings menu
11. `start` - Main start/home button
12. `help_main` - Show help menu
13. `help_back` - Go back in help
14. `help_close` - Close help menu

### Category Management (30 patterns)

#### Basic Operations
15. `add_category` - Add new expense category
16. `add_income_category` - Add new income category
17. `delete_categories` - Delete expense category (menu)
18. `delete_income_categories` - Delete income category (menu)
19. `edit_categories` - Edit expense category (menu)
20. `edit_income_categories` - Edit income category (menu)

#### Category Icons
21. `custom_icon` - Upload custom category icon
22. `no_icon` - Skip icon selection
23. `set_icon_{icon_name}` - Select icon by name
24. `set_income_icon_{icon_name}` - Select income icon by name

#### Category ID-based Operations
25. `edit_cat_{cat_id}` - Edit specific category
26. `del_cat_{cat_id}` - Delete specific category
27. `edit_cat_name_{cat_id}` - Edit category name
28. `edit_cat_icon_{cat_id}` - Edit category icon
29. `edit_income_cat_{cat_id}|{category_id}` - Edit income category
30. `del_income_cat_{cat.id}` - Delete income category
31. `edit_income_name_{category_id}` - Edit income category name
32. `edit_income_icon_{category_id}` - Edit income category icon

#### Category Selection (bulk)
33. `budget_cat_{category.id}` - Select category for budget
34. `cashback_cat_{categories[i].id}` - Select category for cashback
35. `cashback_cat_all` - All categories for cashback
36. `expense_cat_{categories[i].id}` - Select expense category
37. `recurring_cat_{categories[i].id}` - Select recurring category

### Budget Management (6 patterns)
38. `add_budget` - Start adding budget
39. `delete_budget` - Delete budget (menu)
40. `budget_menu` - Budget management menu
41. `del_budget_{budget.id}` - Delete specific budget
42. `cancel_category` - Cancel category selection

### Cashback Management (20 patterns)

#### Core Operations
43. `cashback_add` - Start adding cashback
44. `cashback_edit` - Edit existing cashback
45. `cashback_remove` - Remove cashback (menu)
46. `cashback_remove_all` - Remove all cashbacks

#### Bank Selection
47. `cashback_bank_{banks[i]}` - Select bank
48. `edit_bank_{banks[i]}` - Edit bank selection

#### Cashback Details
49. `cashback_percent_{percent_value}` - Select percentage
50. `cashback_limit_1000` - 1000 spending limit
51. `cashback_limit_2000` - 2000 spending limit
52. `cashback_limit_3000` - 3000 spending limit
53. `cashback_limit_5000` - 5000 spending limit
54. `cashback_no_limit` - No spending limit
55. `cashback_month_{month}` - Select month

#### Cashback Editing
56. `edit_cb_{cb.id}` - Edit specific cashback
57. `remove_cb_{cb.id}` - Remove specific cashback
58. `confirm_remove_cb_{cashback_id}` - Confirm removal
59. `back_to_edit_list` - Return to edit list
60. `skip_edit_bank` - Skip bank editing
61. `skip_description` - Skip description input
62. `view_cb_month_{month}` - View by month
63. `confirm_remove_all` - Confirm remove all

### Expense/Income Management (21 patterns)

#### View Operations
64. `expenses_today` - Show today's expenses (used in multiple routers)
65. `expenses_month` - Show monthly expenses
66. `expenses_prev_month` - Previous month
67. `expenses_next_month` - Next month
68. `expenses_today_view` - Alternative today view

#### Editing Fields
69. `edit_expense_{expense.id}` - Edit specific expense
70. `edit_income_{income.id}` - Edit specific income
71. `edit_field_amount` - Select amount field to edit
72. `edit_field_description` - Select description field to edit
73. `edit_field_category` - Select category field to edit
74. `edit_cancel` - Cancel editing
75. `edit_done` - Complete editing
76. `edit_back_{expense_id}` - Return from edit

#### Category Selection During Edit
77. `expense_cat_{categories[i].id}` - Select category while editing

#### Deletion
78. `delete_expense_{expense.id}` - Delete expense
79. `delete_income_{income.id}` - Delete income

### Recurring Payments (15 patterns)

#### Basic Operations
80. `recurring_menu` - Recurring payments menu
81. `add_recurring` - Add recurring payment
82. `edit_recurring` - Edit recurring (menu)
83. `delete_recurring` - Delete recurring (menu)

#### Recurring Selection
84. `recurring_cat_{categories[i].id}` - Select category
85. `recurring_day_{day}` - Select day of month
86. `edit_recurring_{payment.id}|{payment_id}` - Edit specific payment

#### Field Editing
87. `edit_amount_{payment_id}` - Edit amount
88. `edit_description_{payment_id}` - Edit description
89. `edit_day_{payment_id}` - Edit day
90. `edit_category_{payment_id}` - Edit category
91. `set_category_{payment_id}_{category.id}` - Set specific category

#### Toggle & Delete
92. `toggle_recurring_{payment_id}` - Enable/disable recurring
93. `del_recurring_{payment.id}` - Delete specific recurring
94. `back_to_category_selection` - Return to category select

### PDF Reports (2 patterns)
95. `pdf_generate_current` - Generate current period PDF
96. `pdf_report_select_month` - Select month for PDF
97. `pdf_report_{month}` - Generate PDF for month

### Reports & Views (6 patterns)
98. `show_month_start` - Show month summary
99. `show_diary` - Show expense diary
100. `back_to_summary` - Return to summary
101. `month_{month_number}` - Navigate to month
102. `toggle_view_scope` - Toggle personal/family view
103. `toggle_view_scope_expenses` - Toggle expenses view scope

### Settings (9 patterns)
104. `change_language` - Language selection menu
105. `lang_{language_code}` - Select specific language
106. `change_timezone` - Timezone selection menu
107. `tz_{timezone}` - Select specific timezone
108. `change_currency` - Currency selection menu
109. `curr_{currency_code}` - Select specific currency
110. `toggle_cashback` - Enable/disable cashback feature
111. `privacy_accept` - Accept privacy policy
112. `privacy_decline` - Decline privacy policy

### Subscription (6 patterns)
113. `menu_subscription` - Subscription menu
114. `subscription_buy_month` - Buy 1-month subscription
115. `subscription_buy_six_months` - Buy 6-month subscription
116. `subscription_buy_month_promo` - Buy 1-month with promo
117. `subscription_buy_six_months_promo` - Buy 6-month with promo
118. `subscription_promo` - View promo offers
119. `offer_accept_{offer_id}` - Accept specific offer
120. `offer_decline` - Decline offer

### Family/Household (8 patterns)
121. `menu_family` - Family menu
122. `family_generate` - Generate family invite
123. `family_copy` - Copy family invite code
124. `family_accept:{token}` - Accept family invite (with token)
125. `household_budget` - Household budget view
126. `create_household` - Create household
127. `generate_invite` - Generate invite code
128. `show_members` - Show household members
129. `rename_household` - Rename household
130. `leave_household` - Leave household
131. `confirm_join:{household_id}` - Confirm join (with ID)
132. `confirm_leave` - Confirm leaving
133. `cancel_action` - Cancel action
134. `household_back` - Back from household

### Referral (3 patterns)
135. `menu_referral` - Referral menu
136. `referral_stats` - Show referral stats
137. `referral_rewards` - Show rewards

### Top 5 Expenses (2 patterns)
138. `top5_menu` - Top 5 menu
139. `t5:{custom_data}` - Top 5 with custom data

### Cashback Specific (removals)
140. `remove_cashback_{item_id}` - Remove specific cashback (alternative)

---

## Pattern Classification

### By Data Type (107 patterns)

#### Static/Literal (60 patterns)
No variables, direct string matching
- All "add_*", "delete_*", "menu", "close" patterns
- All "help_*", "settings", "start" patterns

#### Dynamic with Single ID (35 patterns)
Format: `{prefix}_{id}`
- `edit_cat_{cat_id}`
- `del_budget_{budget.id}`
- `remove_cb_{cb.id}`
- etc.

#### Dynamic with Multiple IDs (8 patterns)
Format: `{prefix}_{id1}_{id2}`
- `set_category_{payment_id}_{category.id}`
- `confirm_join:{household_id}`

#### Dynamic with Multiple Prefixes (4 patterns)
Format: `{prefix}_{value}`
- `lang_{language_code}`
- `tz_{timezone}`
- `curr_{currency_code}`
- `month_{month_number}`

---

## Router-to-Callback Mapping

### categories.py → 30 handlers
- Static: `add_category`, `add_income_category`, `delete_categories`, etc.
- Dynamic: `edit_cat_*`, `del_cat_*`, `edit_income_cat_*`, etc.

### cashback.py → 24 handlers
- Static: `cashback_menu`, `cashback_add`, `cashback_edit`
- Dynamic: `cashback_cat_*`, `cashback_bank_*`, `edit_cb_*`, `remove_cb_*`
- Numeric: `cashback_limit_1000`, `cashback_limit_2000`, etc.
- Time-based: `cashback_month_*`, `view_cb_month_*`

### expense.py → 21 handlers
- View: `expenses_today`, `expenses_month`, `expenses_prev_month`, `expenses_next_month`
- Edit: `edit_expense_*`, `edit_income_*`
- Fields: `edit_field_amount`, `edit_field_description`, `edit_field_category`
- Categories: `expense_cat_*`
- Delete: `delete_expense_*`, `delete_income_*`

### recurring.py → 15 handlers
- Core: `recurring_menu`, `add_recurring`, `edit_recurring`, `delete_recurring`
- Selection: `recurring_cat_*`, `recurring_day_*`
- Field edits: `edit_amount_*`, `edit_description_*`, `edit_day_*`, `edit_category_*`
- Control: `toggle_recurring_*`, `del_recurring_*`

### household.py → 10 handlers
- Core: `household_budget`, `create_household`, `generate_invite`
- Management: `show_members`, `rename_household`, `leave_household`
- Control: `confirm_join:*`, `confirm_leave`, `cancel_action`, `household_back`

### settings.py → 9 handlers
- Language: `change_language`, `lang_*`
- Timezone: `change_timezone`, `tz_*`
- Currency: `change_currency`, `curr_*`
- Toggles: `toggle_cashback`, `toggle_view_scope`

### start.py → 8 handlers
- Auth: `privacy_accept`, `privacy_decline`
- Navigation: `start`, `close`, `close_menu`
- Help: `help_main`, `help_back`, `help_close`

### Other routers (24 handlers total)
- budget.py (6): `add_budget`, `delete_budget`, `budget_menu`, `budget_cat_*`, `del_budget_*`
- subscription.py (6): `menu_subscription`, `subscription_buy_*`, `offer_accept_*`, `offer_decline`
- reports.py (6): `expenses_today`, `show_month_start`, `show_diary`, `month_*`, `toggle_view_scope_expenses`
- family.py (4): `menu_family`, `family_generate`, `family_copy`, `family_accept:*`
- referral.py (3): `menu_referral`, `referral_stats`, `referral_rewards`
- pdf_report.py (2): `pdf_report_select_month`, `pdf_report_*`
- top5.py (2): `top5_menu`, `t5:*`
- menu.py (2): duplicates from other routers

---

## Data Extraction Patterns

### Pattern 1: Underscore Separator
```python
callback_data = "edit_cat_42"
parts = callback_data.split("_")
cat_id = parts[-1]  # "42"

callback_data = "budget_cat_7"
parts = callback_data.split("_")
cat_id = parts[-1]  # "7"
```

### Pattern 2: Colon Separator
```python
callback_data = "family_accept:abc123token"
token = callback_data.split(":")[1]  # "abc123token"

callback_data = "confirm_join:household_456"
household_id = callback_data.split(":")[1]  # "household_456"
```

### Pattern 3: Multiple Segments
```python
callback_data = "set_category_15_42"
parts = callback_data.split("_")
payment_id = parts[2]      # "15"
category_id = parts[3]     # "42"
```

### Pattern 4: Prefix-only (no data)
```python
callback_data = "add_budget"
# Direct match - no extraction needed
# Use startswith("add_") to identify action type
```

### Pattern 5: Configuration Values
```python
callback_data = "lang_en"
lang_code = callback_data.split("_")[1]  # "en"

callback_data = "tz_Europe/Moscow"
timezone = callback_data.split("_", 1)[1]  # "Europe/Moscow"

callback_data = "curr_USD"
currency = callback_data.split("_")[1]  # "USD"
```

### Pattern 6: Numeric Suffixes
```python
callback_data = "cashback_limit_1000"
limit = callback_data.split("_")[-1]  # "1000"

callback_data = "subscription_buy_month"
product = callback_data.split("_")[2:]  # ["month"]
```

---

## FSM State Integration

These patterns are used with specific FSM states:

### CashbackForm states
- State: `waiting_for_category` → Match: `cashback_cat_*`
- State: `waiting_for_bank` → Match: `cashback_bank_*`
- State: `choosing_cashback_to_edit` → Match: `edit_cb_*`
- State: `editing_bank` → Match: `edit_bank_*` OR `skip_edit_bank`
- State: `editing_percent` → Match: `cashback_percent_*`
- State: `waiting_for_percent` → Match: `cashback_percent_*`
- State: `waiting_for_limit` → Match: `cashback_limit_*` OR `cashback_no_limit`
- State: `waiting_for_month` → Match: `cashback_month_*`
- State: `waiting_for_description` → Match: `skip_description`

### EditExpenseForm states
- State: `choosing_field` → Match: `edit_field_*` OR `edit_done`
- State: `editing_category` → Match: `expense_cat_*`

### Other FSM patterns
- BudgetStates.select_category → `budget_cat_*`
- BudgetStates.confirm_delete → `yes` OR `no`
- RecurringForm.waiting_for_category → `recurring_cat_*`
- RecurringForm.waiting_for_day → `recurring_day_*`
- SettingsStates.language → `lang_*`
- SettingsStates.timezone → `tz_*`
- SettingsStates.currency → `curr_*`
- IncomeCategoryForm.waiting_for_icon → `set_income_icon_*` OR `no_income_icon`
- IncomeCategoryForm.waiting_for_custom_icon → `set_income_icon_*`

---

## Migration Complexity by Group

### Level 1: Trivial (Copy-paste mapping)
- 60 static patterns
- Direct 1:1 replacement
- **Effort:** <1 hour

### Level 2: Simple (Extract ID from string)
- 35 patterns with single ID
- Parse with `.split()`
- **Effort:** 2-4 hours

### Level 3: Moderate (Multiple IDs or custom separators)
- 8-12 patterns with complex data
- Parse with custom logic
- **Effort:** 4-8 hours

### Level 4: Complex (FSM-dependent or multi-step)
- 5-10 patterns with state dependencies
- May require architectural changes
- **Effort:** 8-16 hours

**Total estimated migration time: 14-29 hours of development**

---

## Special Cases

### Callback Duplicates in Code
Some callbacks appear in multiple places for keyboard construction:
- `close` (used in ~10 different keyboards)
- `cashback_menu` (used in ~15 different keyboards)
- `categories_menu` (used in ~8 different keyboards)

These are **not** separate handlers - they route to the same handler function.

### Conditional Handler Matching
```python
# categories.py - Complex filter
@router.callback_query(lambda c: c.data.startswith("edit_cat_")
                       and not c.data.startswith("edit_cat_name_")
                       and not c.data.startswith("edit_cat_icon_"))

# Multiple prefix matching
@router.callback_query(F.data.startswith(("edit_expense_", "edit_income_")))
```

### Custom Format: t5: pattern
Top 5 uses custom format with colon:
```python
callback_data = "t5:category_id:period"  # Example format
```

---

## Checklist for Migration

- [ ] Extract all 107 callback_data patterns
- [ ] Create handler mapping for each pattern
- [ ] Implement ID extraction logic for dynamic patterns
- [ ] Test all 148 handlers with new system
- [ ] Verify FSM state routing still works
- [ ] Test error handling for malformed callback data
- [ ] Update documentation
- [ ] Deploy and monitor for issues

