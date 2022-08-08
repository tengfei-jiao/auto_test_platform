from django.contrib.admin.apps import AdminConfig


class TestPlatAdminConfig(AdminConfig):
    default_site = "auto_test_platform.admin.TestPlatAdminSite"
