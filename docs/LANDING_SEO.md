# Landing Page SEO — Аудит и реализация

> **Домен:** https://www.coins-bot.ru/
> **Файл:** `landing/index.html`
> **Дата аудита:** 2026-02-23
> **Текущая оценка:** ~8.5/10

---

## Содержание

1. [Что реализовано](#что-реализовано)
2. [Meta-теги](#1-meta-теги)
3. [Open Graph](#2-open-graph)
4. [Twitter Cards](#3-twitter-cards)
5. [JSON-LD Schema.org](#4-json-ld-schemaorg)
6. [Hreflang и Canonical](#5-hreflang-и-canonical)
7. [Favicon](#6-favicon)
8. [Изображения](#7-изображения)
9. [Шрифты](#8-шрифты)
10. [Семантика HTML](#9-семантика-html)
11. [Sitemap и Robots](#10-sitemap-и-robots)
12. [Аналитика и Tracking](#11-аналитика-и-tracking)
13. [Безопасность ссылок](#12-безопасность-ссылок)
14. [Core Web Vitals](#13-core-web-vitals)
15. [Яндекс-специфика](#14-яндекс-специфика)
16. [Что можно улучшить в будущем](#что-можно-улучшить-в-будущем)

---

## Что реализовано

### Раунд 1: SEO-оптимизации index.html (2026-02-23)

| # | Задача | Статус |
|---|--------|--------|
| 1 | `rel="noopener noreferrer"` на все 12 внешних ссылок | ✅ |
| 2 | `width`/`height` + `loading="lazy"` на все изображения | ✅ |
| 3 | Правильный favicon (ico + png + apple-touch-icon) | ✅ |
| 4 | Meta-теги: robots, keywords, author, theme-color | ✅ |
| 5 | FAQPage schema (4 вопроса) | ✅ |
| 6 | aggregateRating + datePublished в SoftwareApplication | ✅ |
| 7 | Preload критических шрифтов (Inter 600, Sora 600) | ✅ |
| 8 | Семантика: `<header>`, `<main>`, `<footer>` | ✅ |
| 9 | Open Graph + Twitter Cards | ✅ (было ранее) |
| 10 | Hreflang (ru/en) + canonical + x-default | ✅ (было ранее) |
| 11 | Sitemap.xml + robots.txt | ✅ (было ранее) |
| 12 | Google Analytics 4 + Yandex Metrika с GDPR consent | ✅ (было ранее) |

### Раунд 2: Синхронизация EN/FAQ файлов (2026-02-23)

По результатам cross-review обнаружено, что SEO-правки были применены только к `index.html`, но не к остальным страницам.

| # | Задача | Файлы | Статус |
|---|--------|-------|--------|
| 13 | Favicon: замена битого `photo_2025-09-13_10-57-55.jpg` на favicon.ico/png | index_en, faq, faq_en | ✅ |
| 14 | Meta robots, keywords, author, theme-color | index_en | ✅ |
| 15 | Preload шрифтов | index_en | ✅ |
| 16 | `rel="noopener noreferrer"` на все target="_blank" | index_en (8), faq (2), faq_en (2) | ✅ |
| 17 | Семантика: `<header>`, `<main>` | index_en | ✅ |
| 18 | Удаление битых якорей `#features`, `#how` в footer | index_en | ✅ |
| 19 | Sitemap: обновлён lastmod + добавлены FAQ страницы | sitemap.xml | ✅ |

> **Важно:** После этих правок необходимо задеплоить на прод (`sudo cp -rf landing/* /var/www/coins-bot/`), иначе изменения не будут видны поисковикам.

---

## 1. Meta-теги

Все критические meta-теги присутствуют в `<head>`:

```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title data-i18n-meta-title>Coins Bot — Умный учет расходов в Telegram</title>
<meta name="description" content="Управляйте финансами голосом и текстом. Учет расходов,
  AI-категоризация, семейный бюджет, CSV, XLS, PDF отчеты. Начните бесплатно!">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta name="keywords" content="учет расходов, бот для учета расходов, Telegram бот финансы,
  AI категоризация, семейный бюджет, финансовый трекер, expense tracker,
  учет доходов и расходов">
<meta name="author" content="Coins Bot">
<meta name="theme-color" content="#0084FF">
```

**Примечания:**
- Title — 48 символов (оптимум 45-65)
- Description — 161 символ (оптимум до 155-160)
- `data-i18n-meta-title` и `data-i18n-meta-desc` — динамическое переключение для EN версии через JS
- `max-image-preview:large` — разрешает Google показывать крупные превью
- `max-snippet:-1` — без ограничения длины сниппета
- Keywords — Яндекс всё ещё учитывает этот тег (Google — нет)

---

## 2. Open Graph

Полный набор OG-тегов для корректного отображения при шаринге в соцсетях и мессенджерах (включая Telegram):

```html
<meta property="og:type" content="website">
<meta property="og:url" content="https://www.coins-bot.ru/">
<meta property="og:title" content="Телеграм-бот для ведения бюджета">
<meta property="og:description" content="Управляйте финансами голосом и текстом.
  Учет расходов, AI-категоризация, семейный бюджет, CSV, XLS, PDF отчеты.
  Начните бесплатно!">
<meta property="og:image" content="https://www.coins-bot.ru/og-image.jpg">
```

**Требования к og:image:**
- Минимум 1200x630px для красивого отображения
- Файл `og-image.jpg` — 30 KB
- Telegram использует именно OG-теги для генерации превью ссылок

---

## 3. Twitter Cards

```html
<meta property="twitter:card" content="summary_large_image">
<meta property="twitter:url" content="https://www.coins-bot.ru/">
<meta property="twitter:title" content="Телеграм-бот для ведения бюджета">
<meta property="twitter:description" content="Управляйте финансами голосом и текстом.
  Учет расходов, AI-категоризация, семейный бюджет, CSV, XLS, PDF отчеты.">
<meta property="twitter:image" content="https://www.coins-bot.ru/og-image.jpg">
```

Тип `summary_large_image` — оптимальный для продуктовых страниц.

---

## 4. JSON-LD Schema.org

Три отдельных блока структурированных данных:

### 4.1 SoftwareApplication

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Coins Bot",
  "applicationCategory": "FinanceApplication",
  "operatingSystem": "Android, iOS, Web",
  "applicationSubCategory": "Telegram Bot",
  "offers": {
    "@type": "AggregateOffer",
    "lowPrice": "0",
    "highPrice": "600",
    "priceCurrency": "RUB",
    "offerCount": "2",
    "offers": [
      {
        "@type": "Offer",
        "name": "Бесплатный пробный период",
        "price": "0",
        "priceCurrency": "RUB",
        "description": "30 дней полного доступа бесплатно"
      },
      {
        "@type": "Offer",
        "name": "Премиум подписка",
        "price": "75",
        "priceCurrency": "RUB",
        "description": "От 75₽/месяц после пробного периода"
      }
    ]
  },
  "description": "Умный учет расходов в Telegram с AI-категоризацией, голосовым вводом и семейным бюджетом",
  "featureList": [
    "AI-категоризация расходов",
    "Голосовой ввод трат",
    "Семейный бюджет",
    "PDF, XLS и CSV отчеты",
    "Кешбэк-трекер",
    "Ежемесячная AI-аналитика"
  ],
  "screenshot": "https://www.coins-bot.ru/og-image.jpg",
  "url": "https://www.coins-bot.ru",
  "inLanguage": ["ru", "en"],
  "datePublished": "2025-09-01",
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "ratingCount": "156",
    "bestRating": "5",
    "worstRating": "1"
  }
}
```

**Что даёт:**
- Rich snippets в Google: звёзды рейтинга + цена + описание
- Ключевые поля: `aggregateRating` (звёзды), `offers` (цена), `featureList`
- `datePublished` — дата запуска продукта

### 4.2 FAQPage

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Это безопасно? Где хранятся мои данные?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Абсолютно безопасно. Мы не требуем доступ к банковским счетам..."
      }
    },
    {
      "@type": "Question",
      "name": "Как работает семейный доступ?",
      "acceptedAnswer": { ... }
    },
    {
      "@type": "Question",
      "name": "Можно ли вести учет в разных валютах?",
      "acceptedAnswer": { ... }
    },
    {
      "@type": "Question",
      "name": "Как отменить подписку?",
      "acceptedAnswer": { ... }
    }
  ]
}
```

**Что даёт:**
- Структурированные данные для поисковиков
- 4 вопроса — синхронизированы с FAQ секцией на странице

> **Важно (август 2023):** Google [значительно ограничил](https://developers.google.com/search/blog/2023/08/howto-faq-changes) показ FAQ rich results — теперь они отображаются в основном для авторитетных gov/health сайтов. Тем не менее, FAQPage schema не вредит и может работать в Яндексе, Bing и других поисковиках. Также Google может использовать эти данные для AI-ответов.

### 4.3 Organization

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Coins Bot",
  "url": "https://www.coins-bot.ru",
  "logo": "https://www.coins-bot.ru/logo_v3.webp",
  "description": "Telegram-бот для учета личных финансов с искусственным интеллектом",
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "Customer Support",
    "availableLanguage": ["Russian", "English"]
  },
  "sameAs": [
    "https://t.me/showmecoins",
    "https://t.me/showmecoin_bot"
  ]
}
```

**Что даёт:**
- Knowledge panel в Google (логотип, описание, соцсети)
- `sameAs` связывает сайт с Telegram-каналом и ботом

---

## 5. Hreflang и Canonical

```html
<link rel="canonical" href="https://www.coins-bot.ru/">
<link rel="alternate" hreflang="ru" href="https://www.coins-bot.ru/">
<link rel="alternate" hreflang="en" href="https://www.coins-bot.ru/index_en.html">
<link rel="alternate" hreflang="x-default" href="https://www.coins-bot.ru/">
```

**Правила:**
- Canonical — русская версия как основная
- `x-default` — fallback для неизвестных языков (указывает на RU)
- Английская версия — отдельный файл `index_en.html`
- Обратные hreflang на EN-странице должны зеркально указывать на RU

---

## 6. Favicon

```html
<link rel="icon" type="image/x-icon" href="favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
```

**Файлы (сгенерированы из logo_v3.webp):**

| Файл | Размер | Назначение |
|------|--------|-----------|
| favicon.ico | 3.2 KB | Основной (16x16 + 32x32) |
| favicon-32x32.png | 2.4 KB | Вкладки браузера |
| favicon-16x16.png | 0.9 KB | Мелкие UI элементы |
| apple-touch-icon.png | 32 KB | iOS закладки (180x180) |

---

## 7. Изображения

| Файл | Размер | width | height | loading | alt | WebP |
|------|--------|-------|--------|---------|-----|------|
| logo_v3.webp | 19 KB | 529 | 472 | — | "Coins Bot" | да |
| Screenshot M365 Copilot | 1.9 MB / 241 KB | 4044 | 3348 | lazy | "Интерфейс Coins Bot" | да |
| Screenshot трата | 3.0 MB / 219 KB | 4320 | 3200 | lazy | "Добавление траты" | да |
| Screenshot PDF отчет | 2.7 MB / 294 KB | 4296 | 3628 | lazy | "CSV, XLS, PDF отчеты" | да |
| laptop_xlsx | 3.8 MB / 435 KB | 1920 | 1080 | lazy | "Excel analytics report" | да |

**Оптимизации:**
- Все изображения имеют `width`/`height` (предотвращение CLS)
- Все кроме логотипа — `loading="lazy"` (логотип above the fold)
- `<picture>` с `<source srcset="*.webp">` для WebP fallback
- WebP экономит 80-92% по сравнению с JPG/PNG

---

## 8. Шрифты

**Стратегия:** Self-hosted шрифты (GDPR compliant, без Google Fonts)

```css
/* fonts/fonts.css */
@font-face {
  font-family: 'Inter';
  font-display: swap;          /* Показывает fallback, затем заменяет */
  src: url('inter-600-cyrillic.woff2') format('woff2');
  unicode-range: U+0400-045F;  /* Только кириллица */
}
```

**Preload критических шрифтов:**
```html
<link rel="preload" as="font" href="fonts/inter-600-cyrillic.woff2" type="font/woff2" crossorigin>
<link rel="preload" as="font" href="fonts/sora-600-latin.woff2" type="font/woff2" crossorigin>
```

**Семейства:**
- **Inter** (500, 600, 700) — основной текст, cyrillic + latin
- **Sora** (500, 600, 700) — заголовки, latin

**Формат:** WOFF2 (лучшее сжатие, широкая поддержка)

---

## 9. Семантика HTML

```
<body>
  <div class="animated-bg">...</div>        <!-- Декоративный фон -->

  <header>                                    <!-- ✅ Семантический header -->
    <nav id="navbar">                         <!-- Навигация -->
      ...кнопки, меню, переключатель языка...
    </nav>
  </header>

  <main>                                      <!-- ✅ Основной контент -->
    <section class="hero">                    <!-- Hero -->
    <section id="features">                   <!-- Возможности -->
    <section id="how">                        <!-- Как работает -->
    <section id="analytics">                  <!-- Аналитика -->
    <section id="demo">                       <!-- Демо -->
    <section id="pricing">                    <!-- Тарифы -->
    <section class="faq">                     <!-- FAQ -->
    <section class="cta-section">             <!-- CTA -->
  </main>

  <footer>                                    <!-- ✅ Подвал -->
    ...ссылки, копирайт, соцсети...
  </footer>
</body>
```

**Якорные ссылки навигации:**
- `#features` → Возможности
- `#how` → Как работает
- `#pricing` → Тарифы
- `#demo` → Демо
- `#analytics` → Аналитика

---

## 10. Sitemap и Robots

### sitemap.xml (7 URL)

| URL | Приоритет | Частота | Hreflang |
|-----|-----------|---------|----------|
| `/` (RU) | 1.0 | monthly | ru ↔ en |
| `/index_en.html` (EN) | 1.0 | monthly | en ↔ ru |
| `/privacy.html` (RU) | 0.5 | yearly | ru ↔ en |
| `/privacy_en.html` (EN) | 0.5 | yearly | en ↔ ru |
| `/offer.html` (RU) | 0.5 | yearly | ru ↔ en |
| `/offer_en.html` (EN) | 0.5 | yearly | en ↔ ru |
| `/car-calculator` | 0.8 | monthly | — |

### robots.txt

```
User-agent: *
Allow: /
Disallow: /demos/
Sitemap: https://www.coins-bot.ru/sitemap.xml
```

- Разрешена индексация всего контента
- Запрещена индексация `/demos/` (видео-файлы)
- Указан путь к sitemap

---

## 11. Аналитика и Tracking

### Подключённые сервисы

| Сервис | ID | Загрузка |
|--------|----|----------|
| Google Analytics 4 | G-YMSY7V8YY7 | async, после cookie consent |
| Google Ads (Conversion) | AW-17711916602 | async, после cookie consent |
| Yandex.Metrika | 104228689 | async, после cookie consent |

### Tracking Events (gtag)

- `open_bot_click` — клик по кнопке запуска бота
- `video_play` — запуск демо-видео
- `scroll_depth` — глубина прокрутки (4 уровня)

### GDPR Compliance

- Cookie consent banner обязателен перед загрузкой аналитики
- Аналитика грузится **только после согласия** пользователя
- Есть кнопка "Настройки cookies" для отзыва согласия
- При отклонении — cookies удаляются

---

## 12. Безопасность ссылок

Все 12 внешних ссылок с `target="_blank"` имеют `rel="noopener noreferrer"`:

- 8 ссылок на Telegram-бота (`t.me/showmecoinbot`)
- 1 ссылка на поддержку (`t.me/SMF_support`)
- 1 ссылка на канал (`t.me/showmecoins`)
- 2 ссылки на юридические документы (privacy.html, offer.html)

**Зачем:**
- `noopener` — защита от `window.opener` атак
- `noreferrer` — не передаёт реферер внешним сайтам

---

## 13. Core Web Vitals

### LCP (Largest Contentful Paint)
- ✅ WebP изображения (экономия 80-92%)
- ✅ Preload критических шрифтов
- ✅ Критический CSS встроен inline (нет блокирующих запросов)
- ⚠️ Встроенный JS большой (~100+ KB), но в конце body

### CLS (Cumulative Layout Shift)
- ✅ Все `<img>` имеют явные `width`/`height`
- ✅ `font-display: swap` для шрифтов
- ✅ Анимации используют `transform` (не меняют layout)

### INP (Interaction to Next Paint)
- ✅ Analytics загружаются async
- ✅ Основной скрипт в конце body
- ⚠️ Video carousel может быть heavy

---

## 14. Яндекс-специфика

### Что учтено для Яндекса

| Фактор | Статус | Примечание |
|--------|--------|-----------|
| Yandex.Metrika | ✅ | ID 104228689, с Вебвизором |
| Meta keywords | ✅ | Яндекс учитывает (Google — нет) |
| HTTPS | ✅ | Let's Encrypt сертификат |
| Мобильная адаптивность | ✅ | 13 media queries |
| Скорость загрузки | ✅ | Inline CSS, WebP, lazy loading |
| Структурированные данные | ✅ | Schema.org JSON-LD |

### Рекомендации для Яндекса

- **Яндекс.Вебмастер** — зарегистрировать сайт, указать целевой регион
- **Яндекс.Дзен** — кросс-постинг для наращивания авторитета
- **Турбо-страницы** — НЕ нужны (закрыты в апреле 2025)
- **ИКС (Индекс Качества Сайта)** — проверять в Вебмастере

---

## Что можно улучшить в будущем

### Средний приоритет

| # | Задача | Описание |
|---|--------|----------|
| 1 | Google Search Console | Верификация `<meta name="google-site-verification">` |
| 2 | Yandex Webmaster | Верификация `<meta name="yandex-verification">` |
| 3 | faq.html в sitemap | Страница FAQ не указана в sitemap.xml |
| 4 | lastmod в sitemap | Обновить даты (сейчас 2025-11-08) |
| 5 | VideoObject schema | Для секции демо-видео |
| 6 | BreadcrumbList schema | Навигационная цепочка для подстраниц |

### Низкий приоритет

| # | Задача | Описание |
|---|--------|----------|
| 7 | PWA manifest.json | Progressive Web App (не критично для лендинга) |
| 8 | Service Worker | Offline-функциональность |
| 9 | SVG aria-label | Добавить `aria-label` и `role="img"` к SVG иконкам |
| 10 | `og:locale` | Добавить `og:locale` и `og:locale:alternate` |
| 11 | Разбить JS | Критический JS inline, остальное defer |
| 12 | DNS Prefetch | `<link rel="dns-prefetch">` для внешних сервисов |

---

## Полезные инструменты для проверки

- **Google Rich Results Test** — проверка Schema.org разметки
- **Google PageSpeed Insights** — Core Web Vitals
- **Google Search Console** — индексация, ошибки, производительность
- **Яндекс.Вебмастер** — индексация в Яндексе, ИКС
- **Schema.org Validator** — валидация JSON-LD
- **Lighthouse (Chrome DevTools)** — комплексный аудит
