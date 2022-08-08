from django_celery_beat import schedulers


class TestPltModelEntry(schedulers.ModelEntry):
    """
    继承并自定义ModelEntry，重写构造函数
    """
    def __init__(self, model, app=None):
        """
        向task传递 periodic_task_id，作为 keyword 作为命名参数
        :param model:
        :param app:
        """
        super().__init__(model, app)
        if model.task.endswith('_periodic'):
            self.kwargs['periodic_task_id'] = model.pk


class TestPltDatabaseScheduler(schedulers.DatabaseScheduler):
    """
    覆盖 DatabaseScheduler的 Entry
    """
    Entry = TestPltModelEntry