from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0037_familyinvite_used_at_familyinvite_used_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='view_scope',
            field=models.CharField(choices=[('personal', 'Личный'), ('household', 'Семья')], default='personal', max_length=20, verbose_name='Режим отображения'),
        ),
    ]

