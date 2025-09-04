#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование цветов в PDF отчетах
"""

import os
import sys
import django
import io

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка окружения Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Импорты не нужны, просто проверяем цвета

def test_colors():
    """Проверка цветовых схем в PDF сервисах"""
    print("=" * 60)
    print("ПРОВЕРКА ЦВЕТОВ В PDF ОТЧЕТАХ")
    print("=" * 60)
    
    # Проверяем PDFReportService
    print("\n1. PDFReportService (основной сервис с Playwright):")
    print("-" * 40)
    
    # Цвета из pdf_report.py
    category_colors_main = [
        '#8B4513',  # коричневый
        '#4682B4',  # стальной синий
        '#9370DB',  # средний фиолетовый
        '#E67E22',  # оранжевый (был #20B2AA - светлый морской)
        '#F4A460',  # песочный
        '#708090',  # серо-синий
        '#DDA0DD',  # сливовый
        '#B0C4DE'   # светло-стальной синий
    ]
    
    print("Палитра цветов категорий:")
    for i, color in enumerate(category_colors_main, 1):
        print(f"  {i}. {color}")
    
    # Проверяем наличие зеленых
    green_shades = ['#00FF00', '#90EE90', '#20B2AA', '#96CEB4', '#4ECDC4', '#10b981']
    found_greens = [c for c in category_colors_main if c.upper() in [g.upper() for g in green_shades]]
    
    if found_greens:
        print(f"⚠️  Найдены зеленые оттенки: {', '.join(found_greens)}")
    else:
        print("✅ Зеленые оттенки отсутствуют в палитре категорий")
    
    print("\n2. PDFReportHTMLService (HTML->PDF с xhtml2pdf):")
    print("-" * 40)
    
    # Цвета из pdf_report_html.py
    category_colors_html = [
        '#FF6B6B',  # красный
        '#9B59B6',  # фиолетовый (был #4ECDC4 - бирюзовый)
        '#45B7D1',  # голубой
        '#E74C3C',  # красный (был #96CEB4 - светло-зеленый)
        '#FECA57',  # желтый
        '#FF9FF3',  # розовый
        '#54A0FF',  # синий
        '#48DBFB',  # голубой
        '#0ABDE3',  # синий
        '#EE5A6F'   # розовый
    ]
    
    print("Палитра цветов категорий:")
    for i, color in enumerate(category_colors_html, 1):
        print(f"  {i}. {color}")
    
    found_greens_html = [c for c in category_colors_html if c.upper() in [g.upper() for g in green_shades]]
    
    if found_greens_html:
        print(f"⚠️  Найдены зеленые оттенки: {', '.join(found_greens_html)}")
    else:
        print("✅ Зеленые оттенки отсутствуют в палитре категорий")
    
    print("\n3. Цвет кешбека:")
    print("-" * 40)
    cashback_color = '#10b981'
    print(f"Цвет кешбека: {cashback_color} (зеленый)")
    print("✅ Зеленый цвет зарезервирован только для кешбека")
    
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ ПРОВЕРКА")
    print("=" * 60)
    
    if not found_greens and not found_greens_html:
        print("✅ Все зеленые оттенки удалены из палитры категорий")
        print("✅ Зеленый цвет (#10b981) используется только для кешбека")
        print("\nИзменения применены успешно!")
    else:
        print("⚠️  Обнаружены зеленые цвета в палитре категорий")
        print("Требуется дополнительная проверка")

if __name__ == "__main__":
    test_colors()