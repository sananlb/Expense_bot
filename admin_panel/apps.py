from django.apps import AppConfig


def _safe_ensure_periodic_tasks():
    """Try to ensure periodic tasks; swallow import/DB errors at startup.
    Runs idempotently; real diagnostics will appear in logs of beat/web.
    """
    try:
        from .beat_setup import ensure_periodic_tasks
        ensure_periodic_tasks(startup=True)
    except Exception:
        # Avoid crashing app startup if DB isn't ready yet.
        pass


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_panel'
    
    def ready(self):
        # Run once at startup (idempotent)
        _safe_ensure_periodic_tasks()
        
        # Also attach to post_migrate to re-ensure after migrations
        try:
            from django.db.models.signals import post_migrate
            from .beat_setup import ensure_periodic_tasks

            def _handler(**kwargs):
                try:
                    ensure_periodic_tasks(startup=False)
                except Exception:
                    pass

            post_migrate.connect(_handler, sender=self)
        except Exception:
            pass
