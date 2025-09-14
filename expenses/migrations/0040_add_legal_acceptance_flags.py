from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0039_set_household_max_members_5'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='accepted_privacy',
            field=models.BooleanField(default=False, verbose_name='Принято согласие на обработку ПДн'),
        ),
        migrations.AddField(
            model_name='profile',
            name='accepted_offer',
            field=models.BooleanField(default=False, verbose_name='Принята публичная оферта'),
        ),
    ]

