from django.db import migrations, models


def set_max_members_to_5(apps, schema_editor):
    Household = apps.get_model('expenses', 'Household')
    # Reduce any households with limit > 5 down to 5
    Household.objects.filter(max_members__gt=5).update(max_members=5)


def noop_reverse(apps, schema_editor):
    # We don't automatically increase limits back on downgrade
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0038_usersettings_view_scope'),
    ]

    operations = [
        migrations.AlterField(
            model_name='household',
            name='max_members',
            field=models.IntegerField(default=5, verbose_name='Максимум участников'),
        ),
        migrations.RunPython(set_max_members_to_5, noop_reverse),
    ]

