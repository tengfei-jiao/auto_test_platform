# Generated by Django 4.0.4 on 2022-07-24 15:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('test_plt', '0006_alter_casesuite_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='apirunlog',
            name='mysql_key',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name='Mysql Key'),
        ),
    ]