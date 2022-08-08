from django.apps import AppConfig


class TestPltConfig(AppConfig):
    # default_auto_field = 'django.db.models.BigAutoField'
    # 面向程序的名称
    name = 'test_plt'
    # 面向人类的名称
    verbose_name = "测试平台"  # 将 test_plt 再次命名为 测试平台
