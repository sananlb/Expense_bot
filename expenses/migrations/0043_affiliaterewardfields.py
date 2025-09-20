from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('expenses', '0042_add_promocode_subscription_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='affiliatereferral',
            name='reward_granted',
            field=models.BooleanField(default=False, verbose_name='Бонус выдан'),
        ),
        migrations.AddField(
            model_name='affiliatereferral',
            name='reward_granted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата выдачи бонуса'),
        ),
        migrations.AddField(
            model_name='affiliatereferral',
            name='reward_months',
            field=models.IntegerField(default=0, verbose_name='Количество месяцев в бонусе'),
        ),
        migrations.AddField(
            model_name='affiliatereferral',
            name='reward_subscription',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='referral_rewards', to='expenses.subscription', verbose_name='Подписка-бонус'),
        ),
    ]
