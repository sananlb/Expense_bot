"""
Migration to add UNIQUE constraint on django_celery_beat_crontabschedule table.

This prevents duplicate schedule entries when changing task schedules.

Generated manually on 2026-01-11.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0002_broadcastmessage_language_filter'),
        ('django_celery_beat', '__latest__'),  # Ensure django-celery-beat migrations are applied
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Add UNIQUE constraint on CrontabSchedule
                -- This prevents duplicate schedules with same time parameters
                DO $$
                BEGIN
                    -- First check if constraint already exists
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'unique_crontab_schedule'
                    ) THEN
                        -- Add the constraint
                        ALTER TABLE django_celery_beat_crontabschedule
                        ADD CONSTRAINT unique_crontab_schedule
                        UNIQUE (minute, hour, day_of_week, day_of_month, month_of_year, timezone);
                    END IF;
                END $$;
            """,
            reverse_sql="""
                -- Remove UNIQUE constraint if rolling back
                ALTER TABLE django_celery_beat_crontabschedule
                DROP CONSTRAINT IF EXISTS unique_crontab_schedule;
            """,
        ),
    ]
