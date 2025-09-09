from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def noop_forward(apps, schema_editor):
    # No data migration required initially
    pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0035_expense_cashback_amount'),
    ]

    operations = [
        migrations.CreateModel(
            name='Household',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
            ],
            options={
                'db_table': 'households',
                'verbose_name': 'Домохозяйство',
                'verbose_name_plural': 'Домохозяйства',
            },
        ),
        migrations.CreateModel(
            name='FamilyInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('household', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invites', to='expenses.household')),
                ('inviter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='family_invites', to='expenses.profile')),
            ],
            options={
                'db_table': 'family_invites',
                'verbose_name': 'Приглашение в сем. бюджет',
                'verbose_name_plural': 'Приглашения в сем. бюджет',
            },
        ),
        migrations.AddField(
            model_name='profile',
            name='household',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='profiles', to='expenses.household', verbose_name='Домохозяйство'),
        ),
        migrations.RunPython(noop_forward, noop_reverse),
    ]

