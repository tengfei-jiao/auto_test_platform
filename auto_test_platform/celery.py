import os
from celery import Celery

# 设置Celery需要环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auto_test_platform.settings')

# 实例化Celery
app = Celery('auto_test_platform')

# 允许在Django配置文件中对Celery进行配置。
# namespace指定所有Celery配置必须以CELERY开头，避免冲突
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动从已注册到Django的app中发现任务，通常在单独的tasks.py模块中定义所有任务
app.autodiscover_tasks()

#
# # 一个测试任务
# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')
