import json
import logging
import time
import traceback
from datetime import datetime, timedelta

from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import QuerySet
from django.forms import TextInput, Textarea
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from nested_admin.nested import NestedModelAdmin, NestedTabularInline, NestedStackedInline

from auto_test_platform import settings
from forms import RunApiForm, FONT_MONO
from . import tasks
from .models import DeployEnv, TestBatch
from .models import Project, ApiDef, QueryParam, RequestHeader, RequestBody, ApiRunLog, Case, CaseRunLog, CaseSuite, \
    CaseSuiteRunLog, CaseApiDef, CaseApiDefQueryParam, CaseApiDefRequestHeader, CaseApiDefRequestBody
from .models import ProjectMember
from .utils import common, http, redis_, mysql_
from .utils.common import trunc_text


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    # 添加额外2个备用行
    extra = 4


class DeployEnvInline(admin.TabularInline):
    model = DeployEnv
    extra = 3


class QueryParamInline(admin.TabularInline):
    model = QueryParam
    extra = 2


class RequestHeaderInline(admin.TabularInline):
    model = RequestHeader
    extra = 2


class RequestBodyInline(admin.TabularInline):
    model = RequestBody
    extra = 2
    # 定义界面 text 文本的布局，调整界面元素尺寸
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': 20})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 30})},
    }


# 自定义一个继承类，供内联使用
class InlineIdLinkMixin:
    # 实现id的超链接跳转
    @admin.display(description='ID')  # 代替了 id_link.short_description = 'ID'
    def id_link(self, obj: ApiRunLog):
        # 通过继承方的model，去拿到源数据
        opts = self.model._meta
        uri = reverse(f'admin:{opts.app_label}_{opts.object_name.lower()}_change', args=[obj.pk])
        # mark_safe()告诉django，这一段是安全代码
        # target="_blank" 跳转后是打开一个新的窗口
        return mark_safe(f'<a href="{uri}" target="_blank">{obj.pk}</a>')


class CaseApiDefQueryParamInline(NestedTabularInline):
    model = CaseApiDefQueryParam
    extra = 0
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': 20, 'style': FONT_MONO})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 30, 'style': FONT_MONO})},
    }


class CaseApiDefRequestHeaderInline(NestedTabularInline):
    model = CaseApiDefRequestHeader
    extra = 0
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': 20, 'style': FONT_MONO})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 30, 'style': FONT_MONO})},
    }


class CaseApiDefRequestBodyInline(NestedTabularInline):
    model = CaseApiDefRequestBody
    extra = 0
    # 定义界面 text 文本的布局，调整界面元素尺寸
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': 20, 'style': FONT_MONO})},
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 30, 'style': FONT_MONO})},
    }


class CaseApiDefInline(NestedStackedInline):
    model = CaseApiDef
    extra = 0
    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size': 20, 'style': FONT_MONO})},
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 80, 'style': FONT_MONO})},
    }
    fields = (
        ('api', 'reorder', 'abort_when_fail'), ('auth_username', 'auth_password'),
        'bearer_token', 'redis_key', 'mysql_key', 'pre_proc', 'post_proc',
        ('verify', 'status_code', 'response_time'),
        'header_verify', 'json_verify', 'regex_verify', 'python_verify'
    )
    inlines = [CaseApiDefQueryParamInline, CaseApiDefRequestHeaderInline, CaseApiDefRequestBodyInline]


class ApiRunLogInline(InlineIdLinkMixin, admin.TabularInline):
    # model = ApiRunLog
    # extra = 0
    # fields = (
    #     'id', 'api', 'start_at', 'status_code', 'final_url', 'query_params', 'request_headers', 'request_body', 'response_headers',
    #     'response_body', 'success', 'error_msg'
    # )
    model = ApiRunLog
    extra = 0

    @admin.display(description='请求头')
    def req_headers(self, obj):
        return trunc_text(obj.request_headers)

    @admin.display(description='请求体')
    def req_body(self, obj):
        return trunc_text(obj.request_body)

    @admin.display(description='应答头')
    def res_headers(self, obj):
        return trunc_text(obj.response_headers)

    @admin.display(description='应答体')
    def res_body(self, obj):
        return trunc_text(obj.response_body)
    readonly_fields = ('id_link', 'req_headers', 'req_body', 'res_headers', 'res_body',)
    fields = ('id_link', 'api', 'start_at', 'status_code', 'final_url', 'query_params',
              'req_headers', 'req_body', 'res_headers', 'res_body',
              'success', 'error_msg')


class CaseRunLogInline(InlineIdLinkMixin, admin.TabularInline):  # 关联到了caserunlog里面的数据
    model = CaseRunLog
    extra = 0
    fields = ('id_link', 'case', 'start_at', 'finish_at', 'duration', 'passed', 'error_msg', 'created_by')
    readonly_fields = ('id_link', )


class ApiRunLogDefNestedInline(InlineIdLinkMixin, NestedTabularInline):
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
    model = ApiRunLog
    extra = 0
    readonly_fields = ('id_link', )
    fields = ('id_link', 'start_at', 'status_code', 'api', 'duration', 'status_code', 'success', 'error_msg')


class CaseRunLogNestedInline(InlineIdLinkMixin, NestedTabularInline):
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    model = CaseRunLog
    extra = 0
    fields = ('id_link', 'finish_at', 'duration', 'case', 'passed', 'error_msg')
    inlines = [ApiRunLogDefNestedInline]
    readonly_fields = ('id_link',)


class CaseSuiteRunLogNestedInline(InlineIdLinkMixin, NestedTabularInline):
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
    model = CaseSuiteRunLog
    extra = 0
    fields = (
        'id_link', 'start_at', 'duration', 'case_suite', 'passed', 'error_msg'
    )
    inlines = [CaseRunLogNestedInline]
    readonly_fields = ('id_link',)


# 第一步：创建modeladmin的继承类，admin应用有很多现成的功能模块，所以这里先直接引用了
@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    """创建项目管理列表类
    """
    # 第二步：指定要显示的列
    list_display = ["id", "name", "type", "status", "created_by", "created_at"]
    list_display_links = ["id", "name"]
    # 第三步：指定可过滤的列
    list_filter = ["created_at", "type"]
    # 第四步：指定可查询的列
    search_fields = ["name"]
    # 内联的model:测试成员表
    inlines = [ProjectMemberInline, DeployEnvInline]
    # 字段在界面的排列
    # fields = ('name', ('version', 'type'), ('created_by', 'status'), 'description')
    fieldsets = (
        # 基础信息模块
        ('基础信息', {
            'fields': (('name', 'status'), ('version', 'type'), 'created_by')
        }),
        # 拓展信息模块
        ('拓展信息', {
            # 隐藏这个小模块
            'classes': ('collapse',),
            'fields': ('description',)
        }),
    )

    actions = ['select_project']

    def get_queryset(self, request):
        """
        过滤测试项目的界面展示，只展示用户添加的项目
        """
        qs: QuerySet = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(members__id=request.user.id)

    def select_project(self, request, queryset):
        proj = queryset.first()  # model的实例
        # 缺省项目保存到哪里
        request.session['default_project_id'] = proj.id
        self.message_user(request, f"已经将默认项目设置为【{proj}】，后续操作都将基于此项目，同时您可以随时切换此项目",
                          level=messages.INFO)
        redirect_url = request.session.get('test_plt_redirect_url', default=None)
        if redirect_url:
            del request.session['test_plt_redirect_url']
            return redirect(redirect_url)

    select_project.short_description = '将选择的项目设置为默认项目'


@admin.register(ProjectMember)
class ProjectMemberAdmin(ModelAdmin):
    """项目成员管理列表类
    """
    list_display = ["id", "project", "__str__", "join_date", "roles", "status"]  # 我们可以再这里直接使用model里定义的函数
    list_display_links = ["__str__"]
    list_filter = ["join_date", "groups", "status"]
    search_fields = ["user__first_name", "user__username"]
    filter_horizontal = ['groups', ]
    list_per_page = settings.LIST_PER_PAGE

    @admin.display(description="组（角色）")
    def roles(self, obj: ProjectMember):
        return [g.name for g in obj.groups.all()]

    def get_queryset(self, request):
        """
        定制 项目成员界面表单
        :param request:
        :return: 继承原来的基础上添加字段过滤
        """
        qs: QuerySet = super().get_queryset(request)

        proj_id = request.session.get('default_project_id', default=None)

        return qs.filter(project__id=proj_id) if proj_id else qs

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        定制 项目成员 > 添加项目成员界面表单
        :param request:
        :param obj:
        :param change:
        :param kwargs:
        :return:
        """
        form = super().get_form(request, obj, **kwargs)

        # 进入测试项目界面，点击添加。开始定制增加项目成员的页面。
        proj_id = request.session.get('default_project_id', default=None)
        if proj_id:
            # 定制1：测试项目字段的下拉框只显示 "yshop后台测试"
            form.base_fields['project'].queryset = Project.objects.filter(id=proj_id)
            if not obj:
                # 定制2：设置测试项目字段下拉框的默认值为 "yshop后台测试"
                form.base_fields['project'].initial = Project.objects.get(id=proj_id)

        return form


@admin.register(DeployEnv)
class DeployEnvAdmin(ModelAdmin):
    """环境部署管理列表类
    """
    list_display = ["id", "project", "name", "hostname", "port", "status"]  # 我们可以再这里直接使用model里定义的函数
    list_display_links = ["name"]
    list_filter = ["status"]
    search_fields = ["name", "hostname", "memo"]
    list_per_page = settings.LIST_PER_PAGE

    def get_queryset(self, request):
        """
        定制 部署环境页面表单
        :param request:
        :return: 继承原来的基础上添加字段过滤
        """
        qs: QuerySet = super().get_queryset(request)

        proj_id = request.session.get('default_project_id', default=None)

        return qs.filter(project__id=proj_id) if proj_id else qs

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        定制 部署环境 > 添加环境界面表单
        :param request:
        :param obj:
        :param change:
        :param kwargs:
        :return:
        """
        form = super().get_form(request, obj, **kwargs)

        # 进入测试项目界面，点击添加。开始定制增加项目成员的页面。
        proj_id = request.session.get('default_project_id', default=None)
        if proj_id:
            # 定制1：测试项目字段的下拉框只显示 "yshop后台测试"
            form.base_fields['project'].queryset = Project.objects.filter(id=proj_id)
            if not obj:
                # 定制2：设置测试项目字段下拉框的默认值为 "yshop后台测试"
                form.base_fields['project'].initial = Project.objects.get(id=proj_id)

        return form


@admin.register(ApiDef)
class ApiDefAdmin(ModelAdmin):
    """接口定义的界面布局
    """
    list_display = ["id", "project", "protocol", "name", "http_schema", "http_method", "deploy_env", 'uri',
                    'status']  # 我们可以再这里直接使用model里定义的函数
    list_display_links = ["name"]
    list_filter = ["status", "http_schema", "http_method"]
    search_fields = ["name", "uri"]
    # 以下是点击name后，超链接进去的内容
    inlines = [QueryParamInline, RequestHeaderInline, RequestBodyInline, ]
    fieldsets = (
        # 基础信息模块
        ('基础信息', {
            'fields': (
                'project',
                'protocol',
                ('name', 'status'),
                'deploy_env',
                'created_by',)
        }),
        ('HTTP信息', {
            'fields': (
                ('http_schema', 'http_method'),
                'uri',
                ('auth_type', 'body_type'))
        }),
        ('其他信息', {
            'fields': (
                ('db_name', 'db_username', 'db_password'),)
        }),
    )

    def get_queryset(self, request):
        """
        定制 接口定义页面表单
        :param request:
        :return: 继承原来的基础上添加字段过滤
        """
        qs: QuerySet = super().get_queryset(request).only(*self.list_display)

        proj_id = request.session.get('default_project_id', default=None)

        return qs.filter(project__id=proj_id) if proj_id else qs

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        定制 接口定义 > 添加接口界面表单
        :param request:
        :param obj:
        :param change:
        :param kwargs:
        :return:
        """
        form = super().get_form(request, obj, **kwargs)

        # 定制1：创建人_下拉框 值默认为 "当前用户"
        form.base_fields['created_by'].initial = request.user
        # 定制 添加接口界面表单
        proj_id = request.session.get('default_project_id', default=None)
        if proj_id:
            # 定制2：测试项目 下拉框只显示 "项目名称"
            form.base_fields['project'].queryset = Project.objects.filter(id=proj_id)
            # 定制3：部署环境 下拉框只显示 "跟项目有关的部署环境表信息"。跨关系查询，__相当于where子句
            form.base_fields['deploy_env'].queryset = DeployEnv.objects.filter(project__id=proj_id)
            if not obj:
                # 定制4：测试项目 下拉框默认显示 "项目名称"
                form.base_fields['project'].initial = Project.objects.get(id=proj_id)

        return form

    actions = ["run_api"]

    def run_api(self, request, queryset):
        """
        运行所选的接口
        :param request: 代表当前HTTP的请求信息，django自动提供
        :param queryset: 代表当前也买你选中的数据，django自动提供
        :return:
        """
        # 自定义权限
        global form, result
        has_perm = request.user.has_perm('test_plt.run_apidef')
        if not has_perm:
            # raise Exception(f"您没有权限，请管理员为用户添加相应权限！")
            self.message_user(request, f'您没有权限运行接口，请管理员为用户添加相应权限！',
                              level=messages.WARNING)
        else:
            # 1 获取页面上选择的记录
            api: ApiDef = queryset.first()
            # 如果页面发送的请求中包含字符串 "run"，则获取页面参数并运行接口
            if "run" in request.POST:
                form = RunApiForm(request.POST)  # 2 获取接口运行所需要的各种参数
                # 符合条件，表单才会有干净的数据，否则：'RunApiForm' object has no attribute 'cleaned_data'
                if form.is_valid():  # 表单校验（可能产生错误的消息）
                    # 5 接收用户提交的表单，获取里面的数据
                    if api.protocol == "http":
                        # 如果是http协议，则继承之前的
                        query_params = form.cleaned_data['query_params']
                        http_headers = form.cleaned_data['http_headers']
                        request_body = form.cleaned_data['request_body']
                        auth_username = form.cleaned_data['auth_username']
                        auth_password = form.cleaned_data['auth_password']
                        bearer_token = form.cleaned_data['bearer_token']
                        # 6 根据用户提交的数据构造一个HTTP请求
                        result = http.perform_api(api, query_params, http_headers, request_body,
                                                  auth_username, auth_password, bearer_token,
                                                  request.user)
                    # 如果是redis协议，则新定义一个请求redis的接口
                    elif api.protocol == "redis":
                        result = redis_.perform_api(api, form.cleaned_data['redis_key'], request.user)
                    elif api.protocol == "mysql":
                        result = mysql_.perform_api(api, form.cleaned_data['mysql_key'], request.user)
                    self.message_user(request, f"接口已经运行,{api}")
                    # 9 处理响应数据，将结果反馈给用户
                    return HttpResponseRedirect(f"/admin/test_plt/apirunlog/{result.get('runlog_id')}")  # 跳转到接口执行履历
            else:
                ps = {}
                for p in api.query_params.all():  # type: QueryParam
                    ps.update({p.param_name: p.default_value})
                hs = {}
                for p in api.request_headers.all():  # type: RequestHeader
                    hs.update({p.header_name: p.default_value})
                bs = {}
                for p in api.request_body.all():  # type: RequestBody
                    if api.body_type == "form-urlencoded":
                        bs.update({p.param_name: p.default_value})
                    else:
                        bs = p.default_raw
                data = {}
                data.update(request.POST)
                if ps: data["query_params"] = json.dumps(ps, indent=2, ensure_ascii=False)
                if hs: data["http_headers"] = json.dumps(hs, indent=2, ensure_ascii=False)
                if bs: data["request_body"] = json.dumps(bs, indent=2, ensure_ascii=False) if isinstance(bs, dict) else bs
                form = RunApiForm(initial=data)
            # 4 将表单渲染到 一个 中间页面
            return render(request, 'admin/run_api.html', context={'api': api, "form": form})

    run_api.short_description = '运行所选的 接口定义（只支持单选）'


@admin.register(ApiRunLog)
class ApiRunLogAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    list_display = ["id", "api", "start_at", "duration", 'status_code', 'reason', 'success']  # 我们可以再这里直接使用model里定义的函数
    list_display_links = ["id", "start_at"]
    list_filter = ["status_code", "success", "start_at"]
    search_fields = ["api__name"]
    list_per_page = 20

    list_select_related = ('api',)

    def cost_time(self, obj: ApiRunLog):
        start = common.fmt_local_datetime(obj.start_at)
        finish = common.fmt_local_datetime(obj.finish_at)
        return f"{start} ~ {finish} (耗时：{obj.duration}ms)"

    cost_time.short_description = '执行时间'

    fieldsets = (
        # 基础信息模块
        ('基础信息', {
            'fields': (('id', 'success'), 'api', 'cost_time', 'error_msg', 'created_by')
        }),
        ('请求信息', {
            'fields': (
                'query_params', 'request_headers', 'request_body', 'auth_username', 'auth_password', 'bearer_token', 'redis_key', "mysql_key")
        }),
        ('响应信息', {
            'fields': ('response_headers', 'response_body', 'status_code', 'reason', 'final_url')
        }),
    )

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(api__project__id=proj_id) if proj_id else qs


@admin.register(Case)
class CaseAdmin(NestedModelAdmin):
    list_display = ["id", "project", "name", "reorder", 'abort_when_fail', 'created_by', 'status']
    list_display_links = ["name"]
    list_filter = ["created_at", "status", "abort_when_fail"]
    search_fields = ["name", "description"]
    inlines = [CaseApiDefInline]
    fieldsets = (
        # 基础信息模块
        ('基础信息', {
            'fields': (('project', 'status'), ('name', 'reorder', 'abort_when_fail'), 'created_by', 'description')
        }),
    )
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 80, 'style': FONT_MONO})},
    }

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(project__id=proj_id) if proj_id else qs

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        获取基类创建好的form，做一些细节调整
        :param request: 代表请求
        :param obj: 当前对象
        :param change:
        :param kwargs: 其他参数
        :return:
        """
        form = super().get_form(request, obj, **kwargs)

        form.base_fields['created_by'].initial = request.user
        proj_id = request.session.get('default_project_id', default=None)
        if proj_id:
            form.base_fields['project'].queryset = Project.objects.filter(id=proj_id)
            if not obj:
                form.base_fields['project'].initial = Project.objects.get(id=proj_id)

        return form

    actions = ['run_cases_q']

    # def run_cases(self, request, queryset):
    #     logger = logging.getLogger('test_plt')
    #     suite_ctx = {}
    #     # 获取所选的用例
    #     cases = queryset.order_by('reorder').all()
    #     for case in cases:  # type: Case
    #         # 执行单个用例
    #         flag = common.perform_case(case, request.user, suite_ctx=suite_ctx)
    #         if not flag and case.abort_when_fail:
    #             logger.info(f"[{case.name}] 执行失败，原因：有用例接口执行失败且要求用例执行中止")
    #             break
    #     self.message_user(request, f"用例执行完毕，结果：{'成功' if flag else '失败'}")
    #     return HttpResponseRedirect(f"/admin/test_plt/caserunlog/")
    #
    # run_cases.short_description = '执行选择的用例'

    def run_cases_q(self, request, queryset):

        # 自定义权限
        global bat
        has_perm = request.user.has_perm('test_plt.run_case')
        if not has_perm:
            # raise Exception(f"您没有权限，请管理员为用户添加相应权限！")
            self.message_user(request, f'您没有权限运行用例，请管理员为用户添加相应权限！',
                              level=messages.WARNING)
        else:
            # 获取所选的用例
            cases = queryset.order_by('reorder').all()
            case_ids = [case.id for case in cases]
            bat = TestBatch.objects.create(
                project=cases[0].project,
                created_by=request.user,
                start_at=timezone.now(),
                run_type=TestBatch.RUN_TYPE_QUEUE,
                obj_type=TestBatch.OBJ_TYPE_CASE,
                status=TestBatch.STATUS_PENDING,
            )
            for case in cases:
                bat.cases.create(case=case, test_batch=bat)
            tasks.run_cases_queue.delay(case_ids, request.user.id, bat.id)
            self.message_user(request, f"用例执行任务已排队，批次ID：{bat.id}")
            return HttpResponseRedirect(f"/admin/test_plt/testbatch/{bat.id}/")

    run_cases_q.short_description = '执行选择的用例(异步)'


@admin.register(CaseRunLog)
class CaseRunLogAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    list_display = ["id", "case", "start_at", "duration", 'created_by', 'passed']
    list_display_links = ["id", "start_at"]
    list_filter = ["start_at", "passed"]
    search_fields = ["case__name", "case__duration"]

    def cost_time(self, obj: ApiRunLog):
        return common.fmt_cost_time(obj.start_at, obj.finish_at, obj.duration)
    cost_time.short_description = '执行时间'

    fields = (("id", "created_by"), "case", "cost_time", "passed", "error_msg")

    list_per_page = settings.LIST_PER_PAGE  # 每一页展示100条记录
    inlines = [ApiRunLogInline]

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(case__project__id=proj_id) if proj_id else qs


@admin.register(CaseSuite)
class CaseSuiteAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "name", 'status']
    list_display_links = ["name"]
    list_filter = ["status"]
    search_fields = ["name", "description"]
    filter_horizontal = ('cases',)  # 多对多内容展示
    inlines = []
    fieldsets = (
        # 基础信息模块
        ('基础信息', {
            'fields': (('project', 'status'), 'name',)
        }),
        ('扩展信息', {
            'fields': ('description', "cases",)
        }),
    )

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(project__id=proj_id) if proj_id else qs

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        获取基类创建好的form，做一些细节调整
        :param request: 代表请求
        :param obj: 当前对象
        :param change:
        :param kwargs: 其他参数
        :return:
        """
        form = super().get_form(request, obj, **kwargs)
        proj_id = request.session.get('default_project_id', default=None)
        if proj_id:
            form.base_fields['project'].queryset = Project.objects.filter(id=proj_id)
            if not obj:
                form.base_fields['project'].initial = Project.objects.get(id=proj_id)

        return form

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        多对多的关系使用 formfield_for_manytomany 来进行过滤
        :param db_field:
        :param request:
        :param kwargs:
        :return:
        """
        proj_id = request.session.get('default_project_id', default=None)
        if proj_id and db_field.name == 'cases':
            kwargs['queryset'] = Case.objects.filter(project__id=proj_id)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    actions = ['run_suites_q']

    # def run_suites(self, request, queryset):
    #     logger = logging.getLogger('test_plt')
    #     suites = queryset.all()
    #     proj_ctx = {}
    #     for suite in suites:
    #         suite_ctx = {}
    #         logger.info(f'[{suite.name}] 执行开始')
    #         suite_log = common.push_case_suite_run_log(suite, user=request.user)
    #         for case in suite.cases.order_by("reorder"):  # type: Case
    #             flag = common.perform_case(case, request.user, case_suite=suite, case_suite_log=suite_log, suite_ctx=suite_ctx, proj_ctx=proj_ctx)
    #             if not flag and case.abort_when_fail:
    #                 # 用例失败后，返回具体失败的用例名字
    #                 errmsg = f"[{case.name}] 执行失败，有勇力接口执行失败且要求用例执行中止"
    #                 logger.info(errmsg)
    #                 common.push_case_suite_run_log(suite, suite_log=suite_log, passed=False, err_msg=errmsg)
    #                 break
    #         common.push_case_suite_run_log(suite, suite_log=suite_log, passed=True)
    #         logger.info(f'[{suite.name}] 执行结束')
    #
    #     self.message_user(request, f"用例套件执行完毕！")
    #     return HttpResponseRedirect("/admin/test_plt/casesuiterunlog/")
    #
    # run_suites.short_description = '执行选择的 用例套件'

    def run_suites_q(self, request, queryset):
        # 自定义权限
        global bat
        has_perm = request.user.has_perm('test_plt.run_case_suites')
        if not has_perm:
            # raise Exception(f"您没有权限，请管理员为用户添加相应权限！")
            self.message_user(request, f'您没有权限运行用例套件，请管理员为用户添加相应权限！',
                              level=messages.WARNING)
        else:
            suites = queryset.all()
            suite_ids = [suite.id for suite in suites]
            bat = TestBatch.objects.create(
                project=suites[0].project,
                created_by=request.user,
                start_at=timezone.now(),
                run_type=TestBatch.RUN_TYPE_QUEUE,
                obj_type=TestBatch.OBJ_TYPE_SUITE,
                status=TestBatch.STATUS_PENDING,
            )
            for suite in suites:
                bat.suites.create(case_suite=suite, test_batch=bat)
            tasks.run_suites_queue.delay(suite_ids, request.user.id, bat.id)
            self.message_user(request, f"用例执行任务已排队，批次ID：{bat.id}")
            return HttpResponseRedirect(f"/admin/test_plt/testbatch/{bat.id}")

    run_suites_q.short_description = '执行选择的 用例套件(排队)'


@admin.register(CaseSuiteRunLog)
class CaseSuiteRunLogAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    list_display = ["id", "case_suite", "start_at", "duration", 'created_by', 'passed']
    list_display_links = ["id", "start_at"]
    list_filter = ["start_at", "passed"]
    search_fields = ["case__name", "case__duration"]

    def cost_time(self, obj):
        return common.fmt_cost_time(obj.start_at, obj.finish_at, obj.duration)
    cost_time.short_description = '执行时间'
    fields = (("id", "created_by"), "case_suite", "cost_time", "passed", "error_msg")

    list_per_page = settings.LIST_PER_PAGE  # 每一页展示100条记录
    inlines = [CaseRunLogInline]

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(case_suite__project__id=proj_id) if proj_id else qs


@admin.register(CaseApiDef)
class CaseApiDefAdmin(admin.ModelAdmin):
    list_display = ["id", "case", "api", 'reorder', 'abort_when_fail', 'verify']
    list_display_links = ['id']
    list_filter = ["abort_when_fail", 'verify']
    search_fields = ["case__name", "case__description", 'api__name']
    inlines = [CaseApiDefQueryParamInline, CaseApiDefRequestHeaderInline, CaseApiDefRequestBodyInline]
    # 定义界面 text 文本的布局，调整界面元素尺寸
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 80})},
    }

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(case__project__id=proj_id) if proj_id else qs


@admin.register(TestBatch)
class TestBatchAdmin(NestedModelAdmin):
    # 以报告的形式依次展示出来
    # 记录由谁创建
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    list_display = ['id', 'project', 'start_at', 'finish_at', 'obj_type', 'run_type', 'periodic_task', 'status',
                    'created_by']
    list_display_links = ['id', 'start_at']
    list_filter = ['obj_type', 'run_type', 'status']
    search_fields = []
    list_per_page = 20

    inlines = [CaseSuiteRunLogNestedInline, CaseRunLogNestedInline]

    fieldsets = (
        ('基础信息', {
            'fields': (('id', 'project'), ('status', 'created_by'), ('obj_type', 'run_type', 'periodic_task'),
                       'cost_time', 'error_msg')
        }),
        ('统计信息', {
            'fields': (
                ('stat_suite_plan', 'stat_suite_run', 'stat_suite_success', 'stat_suite_success_rto'),
                ('stat_case_plan', 'stat_case_run', 'stat_case_success', 'stat_case_success_rto'),
                ('stat_api_plan', 'stat_api_run', 'stat_api_success', 'stat_api_success_rto'))
        })
    )

    def cost_time(self, obj):
        if obj.finish_at:
            return common.fmt_cost_time(obj.start_at, obj.finish_at, cal=True)
        else:
            return common.fmt_local_datetime(obj.start_at)
    cost_time.short_description = "执行时间"

    def get_inline_instances(self, request, obj: TestBatch = None):
        if obj.obj_type == TestBatch.OBJ_TYPE_CASE:
            self.inlines = [CaseRunLogNestedInline]
        else:
            self.inlines = [CaseSuiteRunLogNestedInline]
        return super(TestBatchAdmin, self).get_inline_instances(request, obj)

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        proj_id = request.session.get('default_project_id', default=None)
        return qs.filter(project__id=proj_id) if proj_id else qs


# 注册 permission model
admin.site.register(Permission)
# admin.site.register(ContentType)
admin.site.site_header = "自动化测试平台后台管理"
admin.site.site_title = "测试平台后台"
