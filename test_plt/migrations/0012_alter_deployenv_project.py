# Generated by Django 4.0.4 on 2022-07-24 17:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('test_plt', '0011_deployenv_dingtalk_web_hook_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deployenv',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='project_env', to='test_plt.project', verbose_name='测试项目'),
        ),
    ]
