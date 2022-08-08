from django.http import HttpRequest
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.http import urlencode


class EnsureProjectIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        pi = request.path_info
        prj_id = request.session.get('default_project_id', default=None)
        while True:
            if not request.user.is_authenticated:  # 未登录
                break
            if prj_id:  # 已经选择默认项目
                break
            if '/admin/test_plt/' not in pi and \
               '/admin/django_celery_results/' not in pi and \
               '/admin/django_celery_beat/' not in pi:
                break
            if '/admin/test_plt/project/' in pi:
                break

            messages.warning(request, '请您先指定一个默认项目！')
            request.session['test_plt_redirect_url'] = request.path
            return redirect('/admin/test_plt/project/')

        response = self.get_response(request)
        return response