# Generated by Django 4.0.4 on 2022-07-24 13:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('test_plt', '0005_alter_case_options_alter_casesuite_options'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='casesuite',
            options={'permissions': [('run_case_suites', '运行所选的用例套件')], 'verbose_name': '用例套件', 'verbose_name_plural': '用例套件'},
        ),
    ]
