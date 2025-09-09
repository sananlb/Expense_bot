"""
Celery configuration for expense_bot
"""
import os
import platform
from celery import Celery
from kombu import Queue

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

# Create Celery app
app = Celery('expense_bot')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure platform-specific settings
system = platform.system()

if system == 'Windows':
    # Windows-specific configuration
    app.conf.update(
        worker_pool='threads',
        worker_max_tasks_per_child=1,
        task_always_eager=False,
        task_eager_propagates=True,
    )
elif system == 'Darwin':  # macOS
    # macOS-specific configuration
    app.conf.update(
        worker_pool='prefork',
        worker_max_tasks_per_child=1000,
        worker_prefetch_multiplier=2,  # Lower for macOS
        # Disable warnings about running as root on macOS
        worker_disable_rate_limits=True,
    )
else:  # Linux and other Unix systems
    # Linux/Unix configuration
    app.conf.update(
        worker_pool='prefork',
        worker_max_tasks_per_child=1000,
        worker_prefetch_multiplier=4,
    )

# Task routing configuration
app.conf.task_routes = {
    'expense_bot.celery_tasks.send_monthly_reports': {
        'queue': 'reports',
        'routing_key': 'report.monthly', 
        'priority': 5,
    },
    'expense_bot.celery_tasks.check_budget_limits': {
        'queue': 'notifications',
        'routing_key': 'notification.budget',
        'priority': 8,
    },
    'expense_bot.celery_tasks.cleanup_old_expenses': {
        'queue': 'maintenance',
        'routing_key': 'maintenance.cleanup',
        'priority': 3,
    },
    'expense_bot.celery_tasks.send_daily_admin_report': {
        'queue': 'reports',
        'routing_key': 'report.admin_daily',
        'priority': 6,
    },
    'expense_bot.celery_tasks.process_recurring_payments': {
        'queue': 'recurring',
        'routing_key': 'recurring.process',
        'priority': 8,
    },
    'expense_bot.celery_tasks.system_health_check': {
        'queue': 'monitoring',
        'routing_key': 'monitoring.health',
        'priority': 6,
    },
    'expense_bot.celery_tasks.collect_daily_analytics': {
        'queue': 'analytics',
        'routing_key': 'analytics.collect',
        'priority': 5,
    },
    'expenses.tasks.process_recurring_expenses': {
        'queue': 'recurring',
        'routing_key': 'recurring.process',
        'priority': 8,
    },
    'expenses.tasks.cleanup_old_exports': {
        'queue': 'maintenance',
        'routing_key': 'maintenance.cleanup',
        'priority': 3,
    },
    'expenses.tasks.send_broadcast_message': {
        'queue': 'notifications',
        'routing_key': 'notification.broadcast',
        'priority': 7,
    },
    'expenses.tasks.process_scheduled_broadcasts': {
        'queue': 'notifications',
        'routing_key': 'notification.scheduled',
        'priority': 6,
    },
    'expenses.tasks.cleanup_old_broadcasts': {
        'queue': 'maintenance',
        'routing_key': 'maintenance.broadcasts',
        'priority': 2,
    },
}

# Queue configuration
app.conf.task_queues = (
    Queue('default', routing_key='task.#'),
    Queue('reports', routing_key='report.#'),
    Queue('recurring', routing_key='recurring.#'),
    Queue('maintenance', routing_key='maintenance.#'),
    Queue('notifications', routing_key='notification.#'),
    Queue('monitoring', routing_key='monitoring.#'),
    Queue('analytics', routing_key='analytics.#'),
)

# Task execution configuration
app.conf.update(
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,      # 10 minutes
    task_acks_late=True,
    worker_hijack_root_logger=False,
    result_expires=3600,      # 1 hour
)

# Auto-discover tasks from Django apps
app.autodiscover_tasks()

# Explicitly import tasks to ensure they are registered
from . import celery_tasks  # noqa

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
