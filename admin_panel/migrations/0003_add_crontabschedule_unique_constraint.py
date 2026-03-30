"""
Migration to add UNIQUE constraint on django_celery_beat_crontabschedule table.

This prevents duplicate schedule entries when changing task schedules.

Generated manually on 2026-01-11.
"""
from django.db import migrations


def _dedupe_crontab_schedules(schema_editor):
    cursor = schema_editor.connection.cursor()

    cursor.execute(
        """
        SELECT minute, hour, day_of_week, day_of_month, month_of_year, timezone, MIN(id) AS keep_id
        FROM django_celery_beat_crontabschedule
        GROUP BY minute, hour, day_of_week, day_of_month, month_of_year, timezone
        HAVING COUNT(*) > 1
        """
    )
    duplicate_groups = cursor.fetchall()

    for minute, hour, day_of_week, day_of_month, month_of_year, timezone, keep_id in duplicate_groups:
        cursor.execute(
            """
            SELECT id
            FROM django_celery_beat_crontabschedule
            WHERE minute = %s AND hour = %s AND day_of_week = %s
              AND day_of_month = %s AND month_of_year = %s AND timezone = %s
              AND id <> %s
            """,
            [minute, hour, day_of_week, day_of_month, month_of_year, timezone, keep_id],
        )
        duplicate_ids = [row[0] for row in cursor.fetchall()]
        if not duplicate_ids:
            continue

        placeholders = ', '.join(['%s'] * len(duplicate_ids))

        cursor.execute(
            f"""
            UPDATE django_celery_beat_periodictask
            SET crontab_id = %s
            WHERE crontab_id IN ({placeholders})
            """,
            [keep_id, *duplicate_ids],
        )
        cursor.execute(
            f"DELETE FROM django_celery_beat_crontabschedule WHERE id IN ({placeholders})",
            duplicate_ids,
        )


def add_crontab_uniqueness(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    _dedupe_crontab_schedules(schema_editor)

    if vendor == 'postgresql':
        schema_editor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'unique_crontab_schedule'
                ) THEN
                    ALTER TABLE django_celery_beat_crontabschedule
                    ADD CONSTRAINT unique_crontab_schedule
                    UNIQUE (minute, hour, day_of_week, day_of_month, month_of_year, timezone);
                END IF;
            END $$;
            """
        )
        return

    if vendor == 'sqlite':
        schema_editor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS unique_crontab_schedule
            ON django_celery_beat_crontabschedule
            (minute, hour, day_of_week, day_of_month, month_of_year, timezone);
            """
        )


def remove_crontab_uniqueness(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == 'postgresql':
        schema_editor.execute(
            """
            ALTER TABLE django_celery_beat_crontabschedule
            DROP CONSTRAINT IF EXISTS unique_crontab_schedule;
            """
        )
        return

    if vendor == 'sqlite':
        schema_editor.execute(
            "DROP INDEX IF EXISTS unique_crontab_schedule;"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0002_broadcastmessage_language_filter'),
        ('django_celery_beat', '__latest__'),  # Ensure django-celery-beat migrations are applied
    ]

    operations = [
        migrations.RunPython(
            add_crontab_uniqueness,
            remove_crontab_uniqueness,
        ),
    ]
