# Generated by Django 4.0.4 on 2022-07-24 16:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('test_plt', '0007_apirunlog_mysql_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseapidef',
            name='mysql_key',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='Mysql 执行语句'),
        ),
    ]
