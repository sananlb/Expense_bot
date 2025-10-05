#!/usr/bin/env python3
"""
Оптимизация нового логотипа v2
"""
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("ERROR: PIL (Pillow) не установлен. Установите: pip install Pillow")
    sys.exit(1)

# Пути к файлам
input_path = "landing/logo v2.png"
output_webp = "landing/logo-v2.webp"
output_png = "landing/logo-v2-optimized.png"

# Проверка существования файла
if not os.path.exists(input_path):
    print(f"ERROR: Файл {input_path} не найден!")
    sys.exit(1)

# Открываем изображение
print(f"Открываю {input_path}...")
img = Image.open(input_path)
print(f"  Оригинальный размер: {img.size}")
print(f"  Формат: {img.format}")
print(f"  Режим: {img.mode}")

# Оптимальный размер для логотипа на лендинге (200x200)
target_size = (200, 200)
print(f"\nИзменяю размер до {target_size}...")
img_resized = img.resize(target_size, Image.Resampling.LANCZOS)

# Сохраняем в WebP (лучшее сжатие)
print(f"Сохраняю в WebP формат: {output_webp}")
img_resized.save(output_webp, "WEBP", quality=85, method=6)

# Также сохраняем оптимизированный PNG как запасной вариант
print(f"Сохраняю оптимизированный PNG: {output_png}")
img_resized.save(output_png, "PNG", optimize=True)

# Проверяем размеры файлов
original_size = os.path.getsize(input_path) / 1024  # KB
webp_size = os.path.getsize(output_webp) / 1024
png_size = os.path.getsize(output_png) / 1024

print("\n" + "="*60)
print("РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ:")
print("="*60)
print(f"Оригинал (PNG):        {original_size:>8.1f} KB")
print(f"WebP (оптимизация):    {webp_size:>8.1f} KB ({webp_size/original_size*100:.1f}% от оригинала)")
print(f"PNG (оптимизация):     {png_size:>8.1f} KB ({png_size/original_size*100:.1f}% от оригинала)")
print(f"Экономия (WebP):       {original_size - webp_size:>8.1f} KB ({(1-webp_size/original_size)*100:.1f}%)")
print("="*60)
print(f"\n✅ Оптимизация завершена!")
print(f"   Используйте: {output_webp}")
