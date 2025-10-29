# Monthly Insights - Critical Fixes Applied

## Summary
Fixed critical issues in monthly insights AI generation feature based on code review feedback.

## 🔴 High Priority Issues - FIXED

### 1. Provider Switching Bug
**Problem:** `_initialize_ai()` always called `get_service('default')`, ignoring the `provider` parameter.

**Impact:** Fallback to OpenAI was impossible because the cached service always pointed to Google (default config).

**Fix:** `bot/services/monthly_insights.py:35-37`
```python
# Before
self.ai_service = get_service('default')  # Always uses default!

# After
self.ai_service = get_service(provider)   # Uses specified provider
self.ai_model = get_model(provider, provider)
```

### 2. OpenAI Fallback + Admin Alerts
**Problem:** No fallback mechanism when Google AI fails, no admin visibility into AI outages.

**Fix:** `bot/services/monthly_insights.py:428-459`
- Added try/catch with OpenAI fallback when Google fails
- Implemented throttled admin notifications (1 hour between notifications)
- Two notification types:
  - `_notify_admin_fallback()` - warns when fallback is used
  - `_notify_admin_failure()` - critical alert when both providers fail

**Throttling:** Global dictionaries `_last_fallback_notification` and `_last_failure_notification` prevent notification spam.

## 🟡 High Priority Issues - NOT FIXED (Localization)

### No Localization Support
**Problem:** All content hard-coded in Russian:
- Category names: `expense.category.get_display_name('ru')` (line 93)
- Month names: `months_ru` dictionary (line 159-163, 112-116 in notifications.py)
- Prompt text: Russian instructions (line 194-231)
- Caption text: Russian formatting (line 119-153 in notifications.py)

**Impact:** English-speaking users will receive Russian insights.

**Recommendation:** Add localization layer:
```python
# Proposed solution (not implemented)
def _get_month_names(lang: str) -> Dict[int, str]:
    if lang == 'en':
        return {1: 'January', 2: 'February', ...}
    return {1: 'января', 2: 'февраля', ...}

# Use profile.language (if available)
month_names = self._get_month_names(profile.language or 'ru')
```

**Why not fixed:** Requires:
1. Profile model to have `language` field
2. Translation of all strings
3. Bilingual prompts for AI
4. Testing with English-speaking users

## 🟢 Medium Priority - NOT IMPLEMENTED

### Lightweight Fallback Summary
**Question:** Should we generate a basic text summary when AI is completely down?

**Current behavior:** When both AI providers fail, user receives only generic caption:
```
📊 Ежемесячный отчет за Октябрь 2025
```

**Proposed alternative:** Generate template-based summary:
```
📊 Ежемесячный отчет за Октябрь 2025

💰 Расходы: 30,620 ₽
📊 Количество трат: 13

🏆 Топ категорий:
1. Прочие расходы: 18,400₽ (60%)
2. Жилье: 4,400₽ (14%)
3. Одежда: 3,400₽ (11%)
```

**Recommendation:** Implement lightweight fallback in `bot/services/notifications.py`:
```python
if not insight:
    # Generate basic summary from month_data
    basic_summary = self._format_basic_summary(month_data)
    caption = f"{caption}\n\n{basic_summary}"
```

**Why not implemented:**
- Requires additional logic in notifications.py
- Need to decide if template-based summary is valuable
- Current behavior (no insights) is acceptable since PDF contains all data

## Files Modified

### bot/services/monthly_insights.py
- Line 35-37: Fixed provider selection in `_initialize_ai()`
- Line 20-23: Added throttling globals
- Line 428-459: Added fallback logic and admin notifications
- Line 557-640: Added `_notify_admin_fallback()` and `_notify_admin_failure()` methods

### Dependencies
- Requires: `bot.services.admin_notifier.notify_admin()`
- Uses: `get_service(provider)` and `get_model(provider, provider)` from ai_selector

## Testing

### Manual Test
```bash
cd C:/Users/_batman_/Desktop/expense_bot
venv/Scripts/python.exe test_monthly_insights.py
```

### Expected Behavior
1. ✅ Provider switching works correctly
2. ✅ If Google fails, automatically falls back to OpenAI
3. ✅ Admin receives notification on fallback (max once per hour)
4. ✅ Admin receives critical alert if both providers fail (max once per hour)
5. ❌ Localization not tested (not implemented)

## Monitoring

### Logs to Watch
```bash
# Successful generation
INFO monthly_insights: Initialized AI service: google with model gemini-2.5-flash
INFO monthly_insights: Created new insight for 881292737 10/2025

# Fallback triggered
ERROR monthly_insights: Primary AI provider (google) failed: <error>
WARNING monthly_insights: Attempting fallback to OpenAI for user 881292737
INFO monthly_insights: Admin notified about fallback from google to openai

# Complete failure
ERROR monthly_insights: OpenAI fallback also failed: <error>
INFO monthly_insights: Admin notified about complete AI failure for 881292737 10/2025
```

### Sentry Alerts
- Both notification methods will appear in Sentry
- Filter by `monthly_insights` logger
- Look for ERROR and WARNING levels

## Open Questions

1. **Should we implement localization now or defer?**
   - Pros: Better UX for international users
   - Cons: Requires significant changes, testing

2. **Is lightweight fallback summary needed?**
   - Pros: Better than empty caption
   - Cons: Adds complexity, PDF already has full data

3. **Should throttling be configurable?**
   - Current: Hard-coded 1 hour
   - Alternative: Move to settings.py

## Recommendations for Production

1. ✅ Deploy with current fixes (provider switching + fallback + alerts)
2. ⚠️ Monitor admin notifications for first week
3. 📊 Collect metrics on fallback frequency
4. 🌍 Plan localization for Q1 2026 if international users grow
5. 💡 Revisit lightweight fallback if user feedback requests it
