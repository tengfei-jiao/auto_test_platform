from django.contrib.admin import AdminSite


class TestPlatAdminSite(AdminSite):

    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_ordering = {
            '测试平台': 1,
            'Celery结果': 2,
            '周期性任务': 3,
            '认证和授权': 4,
            '内容类型': 5
        }
        app_dict = self._build_app_dict(request)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: app_ordering[x["name"]])

        model_ordering = {
            '测试项目': 1,
            '接口定义': 2,
            '接口执行履历': 3,
            '用例': 4,
            '用例执行履历': 5,
            '用例套件': 6,
            '用例套件执行履历': 7,
            '测试批次(报告)': 8,
            '用例接口': 9,
            '项目成员': 10,
            '部署环境': 11,
        }
        # Sort the models alphabetically within each app.
        for app in app_list:
            if app['name'] == '测试平台':
                app["models"].sort(key=lambda x: model_ordering[x["name"]])
            else:
                app["models"].sort(key=lambda x: x["name"])
        return app_list