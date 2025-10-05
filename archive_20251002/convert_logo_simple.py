#!/usr/bin/env python3
"""
Простая конвертация логотипа используя только стандартные библиотеки
"""
import os
import sys

# Проверяем наличие PIL
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  PIL (Pillow) не найден. Пытаюсь установить...")

# Если PIL не найден, пытаемся установить
if not PIL_AVAILABLE:
    import subprocess
    try:
        # Пробуем разные способы установки
        commands = [
            ['python3', '-m', 'pip', 'install', '--user', 'Pillow'],
            ['pip3', 'install', '--user', 'Pillow'],
            ['python', '-m', 'pip', 'install', '--user', 'Pillow'],
        ]

        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    print(f"✅ Pillow установлен через: {' '.join(cmd)}")
                    # Пытаемся импортировать снова
                    from PIL import Image
                    PIL_AVAILABLE = True
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    except Exception as e:
        print(f"❌ Не удалось установить Pillow: {e}")

if not PIL_AVAILABLE:
    print("\n" + "="*60)
    print("ОШИБКА: PIL (Pillow) недоступен")
    print("="*60)
    print("\nУстановите вручную:")
    print("  python3 -m pip install --user Pillow")
    print("\nИли используйте онлайн сервис:")
    print("  https://squoosh.app/")
    print("="*60)
    sys.exit(1)

# Теперь конвертируем
from PIL import Image

input_file = "landing/logo-v2.png"
output_webp = "landing/logo-v2.webp"
output_png_small = "landing/logo-v2-small.png"

if not os.path.exists(input_file):
    print(f"❌ Файл не найден: {input_file}")
    sys.exit(1)

print(f"📂 Открываю: {input_file}")
img = Image.open(input_file)
print(f"   Размер: {img.size}")
print(f"   Формат: {img.format}")
print(f"   Режим: {img.mode}")

# Изменяем размер до 200x200
target_size = (200, 200)
print(f"\n🔄 Изменяю размер до {target_size}...")
img_resized = img.resize(target_size, Image.Resampling.LANCZOS)

# Сохраняем в WebP
print(f"💾 Сохраняю WebP: {output_webp}")
img_resized.save(output_webp, "WEBP", quality=85, method=6)

# Сохраняем маленький PNG для fallback
print(f"💾 Сохраняю PNG: {output_png_small}")
img_resized.save(output_png_small, "PNG", optimize=True)

# Статистика
original_size = os.path.getsize(input_file) / 1024
webp_size = os.path.getsize(output_webp) / 1024
png_size = os.path.getsize(output_png_small) / 1024

print("\n" + "="*60)
print("РЕЗУЛЬТАТ:")
print("="*60)
print(f"Оригинал:    {original_size:>8.1f} KB")
print(f"WebP:        {webp_size:>8.1f} KB (экономия {(1-webp_size/original_size)*100:.1f}%)")
print(f"PNG (малый): {png_size:>8.1f} KB (экономия {(1-png_size/original_size)*100:.1f}%)")
print("="*60)
print(f"\n✅ Готово! Используйте: {output_webp}")
