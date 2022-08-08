from .celery import app as celery_app


# 这压根可以确保在Django启动时加载应用程序，以便@shared_task装饰器时使用它：
__all__ = ('celery_app', )