from expenses.models import Profile, Expense, ExpenseCategory
from django.db.models import Count

print('=== ПРОВЕРКА ПРОФИЛЕЙ ===')
for p in Profile.objects.all().order_by('id'):
    expenses = Expense.objects.filter(profile=p).count()
    categories = ExpenseCategory.objects.filter(profile=p).count()
    print(f'ID={p.id}, telegram_id={p.telegram_id}, расходов={expenses}, категорий={categories}')

print('\n=== ПРОВЕРКА ДУБЛИКАТОВ ===')
duplicates = Profile.objects.values('telegram_id').annotate(count=Count('id')).filter(count__gt=1)
if duplicates:
    for d in duplicates:
        tid = d['telegram_id']
        cnt = d['count']
        print(f'telegram_id {tid} имеет {cnt} профилей')

        # Показываем детали дубликатов
        profiles = Profile.objects.filter(telegram_id=tid).order_by('id')
        for p in profiles:
            expense_count = Expense.objects.filter(profile=p).count()
            category_count = ExpenseCategory.objects.filter(profile=p).count()
            print(f'  - ID={p.id}: {expense_count} расходов, {category_count} категорий')
else:
    print('Дубликатов не найдено')

print('\n=== ПРОВЕРКА ПУСТЫХ ПРОФИЛЕЙ ===')
empty_profiles = []
for p in Profile.objects.all():
    expense_count = Expense.objects.filter(profile=p).count()
    category_count = ExpenseCategory.objects.filter(profile=p).count()
    if expense_count == 0 and category_count == 0:
        empty_profiles.append(p)
        print(f'Пустой профиль: id={p.id}, telegram_id={p.telegram_id}')

if empty_profiles:
    print(f'\nНайдено {len(empty_profiles)} пустых профилей')
    answer = input('Удалить пустые профили? (yes/no): ')
    if answer.lower() == 'yes':
        for p in empty_profiles:
            print(f'Удаляем профиль id={p.id}, telegram_id={p.telegram_id}')
            p.delete()
        print('Пустые профили удалены')
else:
    print('Пустых профилей не найдено')

print('\n=== ИТОГОВАЯ СТАТИСТИКА ===')
print(f'Всего профилей: {Profile.objects.count()}')
print(f'Всего расходов: {Expense.objects.count()}')
print(f'Всего категорий: {ExpenseCategory.objects.count()}')

# Показываем профили с данными
print('\nПрофили с данными:')
for p in Profile.objects.all().order_by('id'):
    expense_count = Expense.objects.filter(profile=p).count()
    if expense_count > 0:
        total = sum(e.amount for e in Expense.objects.filter(profile=p))
        print(f'  {p.telegram_id}: {expense_count} расходов на {total:.2f} руб')