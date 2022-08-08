# Generated by Django 4.0.4 on 2022-07-20 16:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('test_plt', '0002_remove_projectmember_role_projectmember_groups_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='queryparam',
            options={'permissions': [('run_apidef', '运行所选的接口')], 'verbose_name': '查询参数', 'verbose_name_plural': '查询参数'},
        ),
        migrations.AlterField(
            model_name='project',
            name='members',
            field=models.ManyToManyField(related_name='projects', through='test_plt.ProjectMember', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='projectmember',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_members', to=settings.AUTH_USER_MODEL, verbose_name='用户'),
        ),
    ]
