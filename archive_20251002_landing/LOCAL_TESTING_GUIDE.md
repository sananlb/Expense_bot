# Локальное тестирование оптимизаций лендинга

## 🚀 Быстрый старт

### Вариант 1: Простой HTTP сервер (рекомендуется)

```bash
cd /mnt/c/Users/_batman_/Desktop/expense_bot
bash scripts/test_landing_local.sh
```

Откроется сервер на **http://localhost:8080**

### Вариант 2: Прямое открытие файлов

Открой в браузере:
```
file:///mnt/c/Users/_batman_/Desktop/expense_bot/landing/index.html
```

---

## 📊 Страницы для тестирования

| Страница | URL | Описание |
|----------|-----|----------|
| **Основная (RU)** | http://localhost:8080/index.html | Главная страница |
| **Основная (EN)** | http://localhost:8080/index_en.html | English version |
| **Тест оптимизации** | http://localhost:8080/test-optimization.html | Сравнение JPEG vs WebP |
| **Политика (RU)** | http://localhost:8080/privacy.html | Privacy Policy |
| **Политика (EN)** | http://localhost:8080/privacy_en.html | Privacy Policy EN |
| **Оферта (RU)** | http://localhost:8080/offer.html | Terms of Service |
| **Оферта (EN)** | http://localhost:8080/offer_en.html | Terms of Service EN |

---

## 🔍 Как проверить WebP оптимизацию

### Шаг 1: Открой DevTools
- **Windows/Linux:** Нажми `F12` или `Ctrl+Shift+I`
- **Mac:** Нажми `Cmd+Option+I`

### Шаг 2: Перейди на вкладку Network
1. Кликни на вкладку **Network** (Сеть)
2. Поставь галочку **Disable cache** (Отключить кеш)
3. Убедись что фильтр стоит на **All** или **Img**

### Шаг 3: Обновить страницу
- Нажми `Ctrl+F5` (Windows/Linux)
- Нажми `Cmd+Shift+R` (Mac)

### Шаг 4: Проверить загруженные файлы

**Что искать:**

✅ **Должны загружаться .webp файлы:**
```
Coins logo.webp                          19 KB
Screenshot_20250913_160127_трата.webp    219 KB
Screenshot_20250913_161019_pdf отчет.webp 294 KB
Screenshot_20250913_163017_M365 Copilot.webp 241 KB
```

❌ **НЕ должны загружаться .jpg файлы** (они fallback)

**Скриншот Network tab:**
```
Name                                    Status  Type    Size      Time
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
index.html                              200     html    132 KB    150ms
Coins logo.webp                         200     webp    19 KB     45ms
Screenshot_20250913_160127_трата.webp   200     webp    219 KB    120ms
Screenshot_20250913_161019_pdf отчет.webp 200   webp    294 KB    180ms
Screenshot_20250913_163017_M365 Copilot.webp 200 webp   241 KB    150ms
```

### Шаг 5: Проверить экономию

**Сравнение размеров:**
| Изображение | JPEG | WebP | Экономия |
|-------------|------|------|----------|
| Coins logo | 30 KB | 19 KB | 35.7% |
| Трата | 2.96 MB | 0.21 MB | **92.8%** |
| Фон | 0.24 MB | 0.10 MB | 58.0% |
| PDF отчет | 2.65 MB | 0.29 MB | **89.2%** |
| Copilot | 1.86 MB | 0.24 MB | **87.3%** |
| **ИТОГО** | **7.74 MB** | **0.88 MB** | **88%** |

---

## 🎨 Тест качества изображений

### Визуальное сравнение

Открой: **http://localhost:8080/test-optimization.html**

Эта страница показывает JPEG и WebP версии рядом для сравнения качества.

**Что проверить:**
- ✅ Качество изображений должно быть **идентичным**
- ✅ WebP версии должны загружаться **быстрее**
- ✅ Размер страницы должен быть **значительно меньше**

---

## 🌐 Тест совместимости браузеров

### Поддержка WebP

| Браузер | Версия | WebP Support |
|---------|--------|--------------|
| Chrome | 23+ | ✅ Да |
| Firefox | 65+ | ✅ Да |
| Safari | 14+ | ✅ Да |
| Edge | 18+ | ✅ Да |
| Opera | 12.1+ | ✅ Да |
| IE 11 | - | ❌ Нет (fallback JPEG) |

### Как проверить fallback

**1. Используя User Agent в DevTools:**
```
1. F12 → Console
2. Введи: navigator.userAgent
3. Эмулируй старый браузер через DevTools
```

**2. Через консоль браузера:**
```javascript
// Проверка поддержки WebP
const img = new Image();
img.onload = () => console.log('✅ WebP поддерживается');
img.onerror = () => console.log('❌ WebP НЕ поддерживается - используется JPEG');
img.src = 'data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA';
```

---

## 📱 Тест на мобильных устройствах

### Вариант 1: DevTools Mobile Emulation

1. **F12** → **Toggle device toolbar** (Ctrl+Shift+M)
2. Выбери устройство: iPhone 12, Galaxy S20, iPad и т.д.
3. Проверь что:
   - Изображения масштабируются корректно
   - WebP загружается на современных устройствах
   - Страница адаптивная

### Вариант 2: Локальная сеть

**Если хочешь протестировать на реальном телефоне:**

1. Узнай IP адрес компьютера:
```bash
# Windows (PowerShell)
ipconfig | findstr IPv4

# Linux/WSL
ip addr show | grep inet
```

2. Запусти сервер с доступом из сети:
```bash
cd /mnt/c/Users/_batman_/Desktop/expense_bot/landing
python3 -m http.server 8080 --bind 0.0.0.0
```

3. На телефоне открой:
```
http://[IP_АДРЕС]:8080/index.html
```

Пример: `http://192.168.1.100:8080/index.html`

---

## ⚡ Тест производительности

### Google Lighthouse

**Встроенный в Chrome:**

1. Открой страницу: http://localhost:8080/index.html
2. F12 → вкладка **Lighthouse**
3. Выбери категории:
   - ✅ Performance
   - ✅ Accessibility
   - ✅ Best Practices
   - ✅ SEO
4. Нажми **Analyze page load**

**Ожидаемые результаты (после оптимизации):**

| Метрика | До | После |
|---------|-----|-------|
| Performance Score | ~60 | ~90+ |
| First Contentful Paint | ~2.5s | ~0.8s |
| Largest Contentful Paint | ~4.5s | ~1.5s |
| Total Page Size | ~35 MB | ~8 MB |

### PageSpeed Insights (онлайн)

**После деплоя на сервер:**
1. Открой: https://pagespeed.web.dev/
2. Введи: https://www.coins-bot.ru
3. Нажми **Analyze**

---

## 🐛 Отладка проблем

### Проблема: WebP не загружается

**Проверка 1: Файлы существуют**
```bash
cd /mnt/c/Users/_batman_/Desktop/expense_bot/landing
ls -lh *.webp
```

Должно быть 5 файлов:
```
Coins logo.webp
Screenshot_20250913_160127_трата.webp
Screenshot_20250913_160819_фон.webp
Screenshot_20250913_161019_pdf отчет.webp
Screenshot_20250913_163017_M365 Copilot.webp
```

**Проверка 2: HTML содержит <picture> теги**
```bash
grep -n "<picture>" index.html
```

Должно найти 4 вхождения.

**Проверка 3: Браузер поддерживает WebP**

Консоль браузера (F12):
```javascript
document.createElement('canvas')
  .toDataURL('image/webp')
  .indexOf('data:image/webp') === 0
  ? console.log('✅ WebP поддерживается')
  : console.log('❌ WebP НЕ поддерживается');
```

### Проблема: Страница не открывается

**Проверка 1: Сервер запущен**
```bash
# Проверь что процесс Python работает
ps aux | grep python | grep http.server
```

**Проверка 2: Порт занят**
```bash
# Проверь какой процесс использует порт 8080
netstat -ano | findstr :8080

# Используй другой порт
python3 -m http.server 8081
```

**Проверка 3: Firewall блокирует**
```bash
# Разреши порт в Windows Firewall (PowerShell Admin)
New-NetFirewallRule -DisplayName "Python HTTP Server" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

### Проблема: Изображения не видны

**Проверка 1: Права доступа**
```bash
chmod 644 landing/*.webp
chmod 644 landing/*.jpg
```

**Проверка 2: Путь к файлам**

Убедись что пути в HTML правильные:
```html
<!-- Правильно (относительный путь) -->
<img src="Coins logo.webp">

<!-- Неправильно (абсолютный путь) -->
<img src="/mnt/c/Users/_batman_/Desktop/expense_bot/landing/Coins logo.webp">
```

---

## 📋 Чеклист перед деплоем на сервер

Перед обновлением на production сервере проверь:

- [ ] ✅ WebP файлы загружаются корректно
- [ ] ✅ JPEG fallback работает в старых браузерах
- [ ] ✅ Все 5 изображений конвертированы
- [ ] ✅ Качество изображений приемлемое
- [ ] ✅ Размер страницы уменьшился на ~88%
- [ ] ✅ Страница адаптивная на мобильных
- [ ] ✅ Все ссылки работают
- [ ] ✅ Нет ошибок в консоли браузера
- [ ] ✅ Lighthouse score > 90
- [ ] ✅ Git коммит создан

---

## 🚀 Команды для деплоя

**После успешного локального тестирования:**

```bash
# 1. Push в GitHub
git push origin master

# 2. Обновить на сервере
ssh batman@80.66.87.178
bash /home/batman/expense_bot/scripts/update_landing_optimized.sh
```

---

## 📊 Мониторинг после деплоя

**Проверить результаты на production:**

1. **PageSpeed Insights:**
   https://pagespeed.web.dev/

2. **GTmetrix:**
   https://gtmetrix.com/

3. **WebPageTest:**
   https://www.webpagetest.org/

4. **Проверка WebP через curl:**
```bash
curl -I https://www.coins-bot.ru/Coins%20logo.webp
```

Должно вернуть:
```
HTTP/2 200
content-type: image/webp
cache-control: public, immutable
expires: [1 год вперед]
```

---

## 💡 Дополнительные тесты

### Тест сжатия Gzip

```bash
# Проверка что Nginx отдает Gzip
curl -H "Accept-Encoding: gzip" -I https://www.coins-bot.ru/index.html | grep -i content-encoding
```

Ожидаем:
```
content-encoding: gzip
```

### Тест кеширования

```bash
# Первый запрос
curl -I https://www.coins-bot.ru/Coins%20logo.webp

# Второй запрос (должен вернуться из кеша)
curl -I https://www.coins-bot.ru/Coins%20logo.webp
```

Проверь заголовок `Cache-Control`:
```
cache-control: public, immutable
expires: [дата через 1 год]
```

---

## 📞 Поддержка

Если возникли проблемы:

1. Проверь логи в консоли браузера (F12 → Console)
2. Проверь Network tab на ошибки загрузки
3. Убедись что все файлы на месте
4. Проверь права доступа к файлам

**Rollback (откат изменений):**
```bash
git checkout HEAD~1 landing/index.html
```

---

## ✅ Итог

После успешного локального тестирования ты должен увидеть:

- 📉 Размер страницы уменьшен на **88%**
- ⚡ Скорость загрузки увеличена в **3-4 раза**
- 🎨 Качество изображений **без потерь**
- 📱 Корректная работа на всех устройствах
- 🌐 Совместимость со всеми современными браузерами

Готово к деплою на production! 🚀
