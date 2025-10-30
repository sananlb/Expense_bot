"""
Django settings for expense_bot project.
"""

from pathlib import Path
import os
import logging
# import dj_database_url  # TODO: Install dj-database-url
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-expense-bot-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# CSRF trusted origins for admin panel
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if os.getenv('CSRF_TRUSTED_ORIGINS') else []

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
    'expenses',
    'admin_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'expense_bot.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'expense_bot.wsgi.application'

# Async settings
DJANGO_ALLOW_ASYNC_UNSAFE = True

# Fix для Windows и multiprocessing
if os.name == 'nt':  # Windows
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)

# Database
if os.getenv('DB_HOST'):
    # Production database settings for Docker
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'expense_bot'),
            'USER': os.getenv('DB_USER', 'expense_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'expense_password'),
            'HOST': os.getenv('DB_HOST', 'db'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    # Development database settings (SQLite)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'expense_bot.db',
            'OPTIONS': {
                'check_same_thread': False,
            }
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/panel/'
LOGOUT_REDIRECT_URL = '/admin/'

# Celery Configuration
# Redis connection settings for Docker
if os.getenv('REDIS_HOST'):
    # Docker environment
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'redis_password')
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}"
else:
    # Local development
    REDIS_URL = 'redis://localhost:6379'

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', f'{REDIS_URL}/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', f'{REDIS_URL}/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Allow switching between DB scheduler and in-code schedule via env
USE_DB_BEAT = os.getenv('USE_DB_BEAT', 'true').lower() == 'true'
if USE_DB_BEAT:
    CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL + '/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        }
    }
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'expense_bot.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'stream': 'ext://sys.stdout',
        },
        'callback_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'callback_tracking.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'expenses': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'audit': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'callback_tracking': {
            'handlers': ['callback_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# Admin monitoring configuration
MONITORING_BOT_TOKEN = os.getenv('MONITORING_BOT_TOKEN')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID')

# AI Configuration
# Единичные ключи для обратной совместимости
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Множественные API ключи для ротации
OPENAI_API_KEYS = []
GOOGLE_API_KEYS = []

# Загружаем OpenAI ключи (OPENAI_API_KEY_1, OPENAI_API_KEY_2, ...)
for i in range(1, 10):
    key = os.getenv(f'OPENAI_API_KEY_{i}')
    if key:
        OPENAI_API_KEYS.append(key)

# Если нет множественных ключей, используем единичный
if not OPENAI_API_KEYS and OPENAI_API_KEY:
    OPENAI_API_KEYS = [OPENAI_API_KEY]

# Загружаем Google ключи (GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ...)
for i in range(1, 10):
    key = os.getenv(f'GOOGLE_API_KEY_{i}')
    if key:
        GOOGLE_API_KEYS.append(key)

# Если нет множественных ключей, используем единичный
if not GOOGLE_API_KEYS and GOOGLE_API_KEY:
    GOOGLE_API_KEYS = [GOOGLE_API_KEY]

print(f"[SETTINGS] Загружено OpenAI ключей: {len(OPENAI_API_KEYS)}")
print(f"[SETTINGS] Загружено Google API ключей: {len(GOOGLE_API_KEYS)}")

# Currency and locale
DEFAULT_CURRENCY = os.getenv('DEFAULT_CURRENCY', 'RUB')
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', 'Europe/Moscow')

# Rate limiting
RATE_LIMIT_MESSAGES_PER_MINUTE = int(os.getenv('RATE_LIMIT_MESSAGES_PER_MINUTE', '60'))

# File size limits
MAX_VOICE_DURATION_SECONDS = 60
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '10'))

# PDF Generation
PDF_RETENTION_DAYS = int(os.getenv('PDF_RETENTION_DAYS', '30'))

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Celery Beat Schedule
try:
    from celery.schedules import crontab
    
    CELERY_BEAT_SCHEDULE = {
    # Daily reports removed per user request
    # 'send-daily-reports': {
    #     'task': 'expense_bot.celery_tasks.send_daily_reports',
    #     'schedule': crontab(hour=20, minute=0),  # 8 PM daily
    #     'options': {'queue': 'reports'}
    # },
    'generate-monthly-insights': {
        'task': 'expense_bot.celery_tasks.generate_monthly_insights',
        'schedule': crontab(day_of_month=1, hour=9, minute=0),  # First day of month at 09:00
        'options': {'queue': 'reports'}
    },
    'send-monthly-reports': {
        'task': 'expense_bot.celery_tasks.send_monthly_reports',
        'schedule': crontab(day_of_month=1, hour=10, minute=0),  # First day of month at 10:00
        'options': {'queue': 'reports'}
    },
    # Отключено 30.10.2025 - функционал бюджетов удален
    # 'check-budget-limits': {
    #     'task': 'expense_bot.celery_tasks.check_budget_limits',
    #     'schedule': crontab(minute='*/30'),  # Every 30 minutes
    #     'options': {'queue': 'notifications'}
    # },
    'cleanup-old-expenses': {
        'task': 'expense_bot.celery_tasks.cleanup_old_expenses',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Sunday 3 AM
        'options': {'queue': 'maintenance'}
    },
    'process-recurring-payments': {
        'task': 'expense_bot.celery_tasks.process_recurring_payments',
        'schedule': crontab(hour=12, minute=0),  # 12 PM daily
        # Route to existing queue name to avoid missing queue issues
        'options': {'queue': 'recurring'}
    },
    'send-daily-admin-report': {
        'task': 'expense_bot.celery_tasks.send_daily_admin_report',
        'schedule': crontab(hour=10, minute=0),  # 10 AM daily
        'options': {'queue': 'reports'}
    },
    'process-affiliate-commissions': {
        'task': 'expenses.tasks.process_affiliate_commissions',
        'schedule': crontab(hour=2, minute=0),  # 02:00 daily
        'options': {'queue': 'maintenance'}
    },
    'check-subscription-refunds': {
        'task': 'expenses.tasks.check_subscription_refunds',
        'schedule': crontab(hour=3, minute=0),  # Daily at 03:00
        'options': {'queue': 'maintenance'}
    },
    # Отключено 30.10.2025 - требует psutil, не критично для работы
    # 'system-health-check': {
    #     'task': 'expense_bot.celery_tasks.system_health_check',
    #     'schedule': crontab(minute='*/15'),  # Every 15 minutes
    #     'options': {'queue': 'monitoring'}
    # },
    'collect-daily-analytics': {
        'task': 'expense_bot.celery_tasks.collect_daily_analytics',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'options': {'queue': 'analytics'}
    }
}
except ImportError:
    CELERY_BEAT_SCHEDULE = {}

# Security Settings
# Rate limiting
BOT_RATE_LIMIT_MESSAGES_PER_MINUTE = int(os.getenv('BOT_RATE_LIMIT_MESSAGES_PER_MINUTE', '60'))
BOT_RATE_LIMIT_MESSAGES_PER_HOUR = int(os.getenv('BOT_RATE_LIMIT_MESSAGES_PER_HOUR', '500'))

# Content validation
BOT_MAX_MESSAGE_LENGTH = int(os.getenv('BOT_MAX_MESSAGE_LENGTH', '4096'))
SECURITY_MAX_FAILED_ATTEMPTS = int(os.getenv('SECURITY_MAX_FAILED_ATTEMPTS', '5'))

