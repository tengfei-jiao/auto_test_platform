import logging
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_celery_beat.models import PeriodicTask
import test_plt.utils as u


# 注意：只在value非空时才会触发这种validator!!!
def validate_ascii(value):
    if not value:
        return
    if isinstance(value, str) and value.isascii():
        return
    raise ValidationError('请输入ASCII字符！')


# Create your models here.
# 这里定义了app里面的model，test_plt相当于一个app
class Project(models.Model):
    """
    增加测试项目
    """
    # 产品类型列表
    PROJECT_TYPE = (
        (1, "web"),
        (2, "App"),
        (3, "微服务"),
    )
    # 自增字段，主键
    id = models.AutoField(primary_key=True)  # 自增字段：主键
    # 项目名称
    name = models.CharField(max_length=200, verbose_name="测试项目名称")  # 项目名称
    # 版本
    version = models.CharField(max_length=20, verbose_name="版本")
    # 项目类型
    type = models.IntegerField(verbose_name="产品类型", choices=PROJECT_TYPE)  # 32bit
    # 描述
    description = models.CharField(max_length=200, verbose_name="项目描述", blank=True, null=True)
    # 状态
    status = models.BooleanField(default=True, verbose_name="状态")
    # 创建人
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="创建人",
                                   db_column="created_by")
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    # 最后更新的时间
    updated_at = models.DateTimeField(auto_now=True, verbose_name="最近更新时间")
    # 项目成员（暂缓
    members = models.ManyToManyField(User, related_name="projects",
                                     through="ProjectMember",
                                     through_fields=('project', 'user'))

    # 默认显示
    def __str__(self):
        return self.name

    # 内部类 meta ，决定 project 这个model里面的内容显示
    class Meta:
        verbose_name = "测试项目"
        verbose_name_plural = verbose_name


class ProjectMember(models.Model):
    """
    增加项目成员
    """
    # MEMBER_ROLE = (
    #     (1, '测试人'),
    #     (2, '测试组长'),
    #     (3, '测试经理'),
    #     (4, '开发'),
    #     (5, '运维'),
    #     (6, '项目经理'),
    # )
    # 主键
    id = models.AutoField(primary_key=True)
    # 项目
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name="测试项目")
    # 用户
    user = models.ForeignKey(User, related_name='project_members', on_delete=models.SET_NULL, null=True, verbose_name="用户")
    # 加入日期
    join_date = models.DateTimeField(verbose_name="加入日期")
    # 角色
    # role = models.IntegerField(choices=MEMBER_ROLE, verbose_name='角色')
    groups = models.ManyToManyField(Group, related_name='member_belong_to', verbose_name='角色（组）')
    # 状态
    status = models.BooleanField(default=True, verbose_name="状态")
    # 退出日期
    quit_date = models.DateTimeField(null=True, blank=True, verbose_name="退出日期")
    # 备忘录
    memo = models.CharField(max_length=200, verbose_name="备忘录", blank=True, null=True)

    def __str__(self):
        if not self.user:
            return '-'
        else:
            # 张某某
            firstname = self.user.first_name if self.user.first_name else '-'
            username = self.user.username
            return f"{firstname}({username})"

    class Meta:
        verbose_name = "项目成员"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_project_member'


@receiver(m2m_changed, sender=ProjectMember.groups.through)
def member_groups_changed(sender, instance, **kwargs):
    pks = kwargs.get('pk_set')  # 当前被添加/删除的Group的PKs
    user = instance.user  # 当前被变更到User

    if kwargs.get('action') == 'post_add':  # 在项目成员中添加组的情况
        curr_gs = [g.pk for g in user.groups.all()]
        for pk in pks:
            if pk not in curr_gs:
                user.groups.add(Group.objects.get(pk=pk))

    if kwargs.get('action') == 'post_remove':  # 在项目成员中删除组的情况
        for member in user.project_members.all():
            in_prj_gs = [g.pk for g in member.groups.all()]
            for pk in pks:
                if pk not in in_prj_gs:  # 已经从当前项目删除，且不在其他项目，则删除
                    user.groups.remove(Group.objects.get(pk=pk))


class DeployEnv(models.Model):
    """
    部署环境
    """
    # 主键
    id = models.AutoField(primary_key=True)
    # 项目
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name="测试项目", related_name="project_env")
    # 名称
    name = models.CharField(max_length=50, verbose_name="环境名称")
    # 主机名 IP
    hostname = models.CharField(max_length=50, verbose_name="主机名", help_text="主机名（IP）")
    # 端口
    port = models.IntegerField(verbose_name="端口")
    # 状态
    status = models.BooleanField(default=True, verbose_name="状态")
    # 备忘录
    memo = models.CharField(max_length=200, verbose_name="备忘录", blank=True, null=True)
    # 钉钉群通知
    dingtalk_web_hook = models.CharField(max_length=200, verbose_name="钉钉群通知", blank=True, null=True)
    # 钉钉加签
    dingtalk_web_hook_sign = models.CharField(max_length=200, verbose_name="钉钉加签", blank=True, null=True)


    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "部署环境"
        verbose_name_plural = verbose_name


class ApiDef(models.Model):
    HTTP_SCHEMA_CHOICE = [
        ('http', 'HTTP'),
        ('https', 'HTTPS')
    ]
    HTTP_METHOD_CHOICE = [
        ('get', 'GET'),
        ('post', 'POST'),
        ('put', 'PUT'),
        ('delete', 'DELETE'),
        ('head', 'HEAD'),
        ('options', 'OPTIONS'),
    ]
    AUTHORIZATION_TYPE_CHOICE = [
        ('none', 'No Auth'),
        ('bearer', 'Bearer Token(JWT)'),
        ('basic', 'Basic Auth'),
    ]
    REQUEST_BODY_TYPE_CHOICE = [
        ('none', 'None'),
        ('form-urlencoded', 'x-www-form-urlencoded'),
        ('raw-json', 'JSON'),
        ('raw-xml', 'XML'),
        ('raw-text', 'Plain Text'),
    ]
    API_PROTOCOL = [
        ('http', 'HTTP'),
        ('redis', 'Redis'),
        ('mysql', 'MySQL'),
    ]
    # 协议类型
    protocol = models.CharField(max_length=8, verbose_name="协议", choices=API_PROTOCOL)
    # HTTP模式(http,https) fixme 要根据协议判断是否必须
    http_schema = models.CharField("HTTP模式", blank=True, null=True, max_length=5, choices=HTTP_SCHEMA_CHOICE)
    # 部署环境（外键）
    deploy_env = models.ForeignKey(DeployEnv, on_delete=models.RESTRICT, verbose_name='部署环境')
    # HTTP方法 fixme 要根据协议判断是否必须
    http_method = models.CharField('HTTP方法', blank=True, null=True, max_length=8, choices=HTTP_METHOD_CHOICE)
    # URI fixme 要根据协议判断是否必须
    uri = models.CharField(_('URI'), blank=True, null=True, max_length=256)
    # 认证方法 fixme 要根据协议判断是否必须
    auth_type = models.CharField('认证方法', blank=True, null=True, max_length=8, choices=AUTHORIZATION_TYPE_CHOICE)
    # 请求体类型 fixme 要根据协议判断是否必须
    body_type = models.CharField('请求类型', blank=True, null=True, max_length=16, choices=REQUEST_BODY_TYPE_CHOICE)
    # 主键
    id = models.AutoField(primary_key=True)
    # 测试项目（外键）
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name="测试项目")
    # 名称
    name = models.CharField("名称", max_length=50)
    # 状态
    status = models.BooleanField("状态", default=True)
    # 创建人
    created_by = models.ForeignKey(User,
                                   on_delete=models.SET_NULL,
                                   null=True,
                                   verbose_name="创建人",
                                   db_column="created_by")
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 最后更新的时间
    updated_at = models.DateTimeField("最近更新时间", auto_now=True)

    # 数据库（redis和mysql使用）
    db_name = models.CharField(blank=True, null=True, max_length=128, verbose_name="数据库名")
    # 用户名（mysql使用）
    db_username = models.CharField(blank=True, null=True, max_length=128, verbose_name="DB用户名")
    # 密码（redis和mysql使用）
    db_password = models.CharField(blank=True, null=True, max_length=128, verbose_name="DB密码")

    def clean(self):
        """
        根据协议给出用户提示，哪些表单内容是必填项
        :return:
        """
        if self.protocol != "http":
            return
        errors = {}
        if not self.http_schema:
            errors['http_schema'] = ValidationError('', code='required')
        if not self.http_method:
            errors['http_schema'] = ValidationError('', code='required')
        if not self.uri:
            errors['uri'] = ValidationError('', code='required')
        if not self.auth_type:
            errors['auth_type'] = ValidationError('', code='required')
        if not self.body_type:
            errors['body_type'] = ValidationError('', code='required')
        if len(errors) > 0:
            raise ValidationError(errors)

    def to_url(self):
        http_sch = self.http_schema
        host = self.deploy_env.hostname
        port = self.deploy_env.port
        uri = self.uri
        return f"{http_sch}://{host}{uri}" if port in (80, 443) else f"{http_sch}://{host}:{port}{uri}"

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = '接口定义'
        verbose_name_plural = verbose_name
        permissions = [
            ('run_apidef', '运行所选的接口')
        ]


class QueryParam(models.Model):
    id = models.AutoField(primary_key=True)
    # 接口定义
    api = models.ForeignKey(ApiDef, on_delete=models.CASCADE, verbose_name="接口定义", related_name='query_params')
    # 必须
    required = models.BooleanField("必须", default=False)
    # 参数名称
    param_name = models.CharField("参数名称", max_length=128)
    # 缺省值
    default_value = models.CharField("缺省值", max_length=128, blank=True, null=True)
    # 描述
    description = models.CharField("描述", max_length=40, blank=True, null=True)

    def __str__(self):
        return self.param_name

    class Meta:
        verbose_name = "查询参数"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_query_param'


class RequestHeader(models.Model):
    id = models.AutoField(primary_key=True)
    # 接口定义（realated_name外键的 related_name.xxx_set）
    api = models.ForeignKey(ApiDef, on_delete=models.CASCADE, verbose_name="接口定义", related_name='request_headers')
    # 必须
    required = models.BooleanField("必须", default=False)
    # 参数名称
    header_name = models.CharField("参数名称", max_length=128, validators=[validate_ascii])
    # 缺省值
    default_value = models.CharField("缺省值", max_length=128, blank=True, null=True, validators=[validate_ascii])
    # 描述
    description = models.CharField("描述", max_length=40, blank=True, null=True)

    def __str__(self):
        return self.header_name

    class Meta:
        verbose_name = "请求头"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_request_header'


class RequestBody(models.Model):
    id = models.AutoField(primary_key=True)
    # 接口定义
    api = models.ForeignKey(ApiDef, on_delete=models.CASCADE, verbose_name="接口定义", related_name='request_body')
    # 必须
    required = models.BooleanField("必须", default=False)
    # 参数名称
    param_name = models.CharField("参数名称", max_length=128)
    # 缺省值
    default_value = models.CharField("缺省值", max_length=128, blank=True, null=True)
    # 缺省raw数据
    default_raw = models.TextField("缺省raw数据", blank=True, null=True)
    # 描述
    description = models.CharField("名称", max_length=40, blank=True, null=True)

    def __str__(self):
        return self.param_name

    class Meta:
        verbose_name = "请求体"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_request_body'


class Case(models.Model):
    id = models.AutoField(primary_key=True)
    # 项目 FK
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name="测试项目")
    # 名称/标题 字段名称一般是128
    name = models.CharField(max_length=128, verbose_name="测试项目名称")
    # 描述
    description = models.TextField(verbose_name="项目描述", blank=True, null=True)
    # 状态
    status = models.BooleanField(default=True, verbose_name="状态")
    # 创建人
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="创建人",
                                   db_column="created_by")
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    # 更新时间
    updated_at = models.DateTimeField(auto_now=True, verbose_name="最近更新时间")
    # 执行顺序
    reorder = models.IntegerField(verbose_name="执行顺序")
    # 失败时终止
    abort_when_fail = models.BooleanField(default=True, verbose_name="失败时终止")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "用例"
        verbose_name_plural = verbose_name
        permissions = [
            ('run_case', '运行所选用例')
        ]


class CaseApiDef(models.Model):
    id = models.AutoField(primary_key=True)
    # 用例
    case = models.ForeignKey(Case, on_delete=models.PROTECT, verbose_name='用例', related_name='case_apidefs')
    # 接口
    api = models.ForeignKey(ApiDef, on_delete=models.PROTECT, verbose_name='接口')
    # 执行顺序
    reorder = models.IntegerField(verbose_name="执行顺序")
    # 失败时终止
    abort_when_fail = models.BooleanField(default=True, verbose_name="失败时终止")
    # Basic认证username
    auth_username = models.CharField(null=True, blank=True, max_length=128, verbose_name='认证用户名')
    # Basic认证password
    auth_password = models.CharField(null=True, blank=True, max_length=128, verbose_name='认证密码')
    # Bearer认证token
    bearer_token = models.TextField(null=True, blank=True, verbose_name='Bearer Token')
    # redis key
    redis_key = models.CharField(null=True, blank=True, max_length=128, verbose_name='Redis Key')
    # mysql的执行语句
    mysql_key = models.TextField(null=True, blank=True, verbose_name='Mysql 执行语句')
    # 是否校验
    verify = models.BooleanField(default=True, verbose_name='是否校验')
    # 状态码校验
    status_code = models.IntegerField(null=True, blank=True, verbose_name='状态码校验')
    # 响应时间校验
    response_time = models.IntegerField(null=True, blank=True, verbose_name='响应时间校验（s）')
    # HTTP响应头校验
    header_verify = models.TextField(null=True, blank=True, verbose_name='HTTP响应头校验')
    # 应答体JSON schema校验
    json_verify = models.TextField(null=True, blank=True, verbose_name='应答体JSON Schema校验')
    # 应答体正则表达式校验
    regex_verify = models.TextField(null=True, blank=True, verbose_name='应答体正则表达式校验')
    # 应答体python脚本校验
    python_verify = models.TextField(null=True, blank=True, verbose_name='应答体Python脚本校验')
    # 前置处理
    pre_proc = models.TextField(null=True, blank=True, verbose_name='前置处理')
    # 后置处理
    post_proc = models.TextField(null=True, blank=True, verbose_name='后置处理')

    def get_query_params(self, case_ctx=None, suite_ctx=None, proj_ctx=None):
        result = {}
        for p in self.query_params.all():  # type: CaseApiDefQueryParam
            param_name = u.common.proc_param_expression(p.param_name, case_ctx, suite_ctx, proj_ctx)
            param_value = u.common.proc_param_expression(p.param_value, case_ctx, suite_ctx, proj_ctx)
            result.update({param_name: param_value})
        return result

    def get_http_headers(self, case_ctx=None, suite_ctx=None, proj_ctx=None):
        result = {}
        for p in self.http_headers.all():  # type: CaseApiDefRequestHeader
            header_name = u.common.proc_param_expression(p.header_name, case_ctx, suite_ctx, proj_ctx)
            header_value = u.common.proc_param_expression(p.header_value, case_ctx, suite_ctx, proj_ctx)
            result.update({header_name: header_value})
        return result

    def get_request_body(self, case_ctx=None, suite_ctx=None, proj_ctx=None):
        result = {}
        for p in self.request_body.all():  # type: CaseApiDefRequestBody
            if self.api.body_type in ('raw-json', 'raw-xml', 'raw-text'):
                return u.common.proc_param_expression(p.raw_value, case_ctx, suite_ctx, proj_ctx)
            param_name = u.common.proc_param_expression(p.param_name, case_ctx, suite_ctx, proj_ctx)
            param_value = u.common.proc_param_expression(p.param_value, case_ctx, suite_ctx, proj_ctx)
            result.update({param_name: param_value})
        return result

    def __str__(self):
        return f"{self.api}({self.case})"

    class Meta:
        verbose_name = "用例接口"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_case_apidef'


class CaseApiDefQueryParam(models.Model):
    id = models.AutoField(primary_key=True)
    # 用例接口
    case_api = models.ForeignKey(CaseApiDef, on_delete=models.CASCADE, verbose_name='用例接口', related_name='query_params')
    # 参数名
    param_name = models.CharField(max_length=128, verbose_name='参数名称')
    # 参数值
    param_value = models.CharField(max_length=128, blank=True, null=True, verbose_name="值")

    def __str__(self):
        return self.param_name

    class Meta:
        verbose_name = "用例接口查询参数"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_case_apidef_query_param'


class CaseApiDefRequestHeader(models.Model):
    id = models.AutoField(primary_key=True)
    # 用例接口
    case_api = models.ForeignKey(CaseApiDef, on_delete=models.CASCADE, verbose_name='用例接口',
                                 related_name='http_headers')
    # header键
    header_name = models.CharField(max_length=128, verbose_name='头名称')
    # header值
    header_value = models.CharField(max_length=128, blank=True, null=True, verbose_name="值")

    def __str__(self):
        return self.header_name

    class Meta:
        verbose_name = "用例接口请求头"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_case_apidef_request_header'


class CaseApiDefRequestBody(models.Model):
    # todo 加一个validator，para_name和para_value必须有一个不能为空
    id = models.AutoField(primary_key=True)
    # 用例接口
    case_api = models.ForeignKey(CaseApiDef, on_delete=models.CASCADE, verbose_name='用例接口',
                                 related_name='request_body')
    # 参数名
    param_name = models.CharField(max_length=128, blank=True, null=True, verbose_name='参数名称')
    # 参数值
    param_value = models.CharField(max_length=256, blank=True, null=True, verbose_name="值")
    # RAW数据
    raw_value = models.TextField('RAW数据', blank=True, null=True)

    def __str__(self):
        return self.param_name if self.param_name else self.raw_value[0:20]

    class Meta:
        verbose_name = "用例接口请求体"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_case_apidef_request_body'


class CaseSuite(models.Model):
    """
    用例套件
    """
    id = models.AutoField(primary_key=True)
    # 项目 FK
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name="测试项目")
    # 名称/标题
    name = models.CharField(max_length=50, verbose_name="用例套件名称")
    # 描述
    description = models.TextField("用例套件描述", blank=True, null=True)
    # 状态
    status = models.BooleanField(default=True, verbose_name="状态")
    # 用例 manytomany
    cases = models.ManyToManyField(Case, related_name="case_belong_to", verbose_name="用例")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "用例套件"
        verbose_name_plural = verbose_name
        permissions = [
            ('run_case_suites', '运行所选的用例套件')
        ]


class TestBatch(models.Model):
    OBJ_TYPE_CASE = 1
    OBJ_TYPE_SUITE = 2
    OBJ_TYPE = [
        (OBJ_TYPE_CASE, '按照用例'),
        (OBJ_TYPE_SUITE, '按照套件')
    ]

    RUN_TYPE_QUEUE = 1
    RUN_TYPE_PERIODIC = 2
    RUN_TYPE = [
        (RUN_TYPE_QUEUE, '排队任务'),
        (RUN_TYPE_PERIODIC, '计划任务')
    ]

    STATUS_PENDING = 1
    STATUS_FINISHED = 2
    STATUS_FAILED = 3
    BATCH_STATUS = [
        (STATUS_PENDING, '排队中'),
        (STATUS_FINISHED, '执行完毕'),
        (STATUS_FAILED, '执行失败')
    ]
    id = models.AutoField(primary_key=True)
    # 测试项目
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='测试项目')
    # 开始时间
    start_at = models.DateTimeField(verbose_name='开始时间')
    # 结束时间
    finish_at = models.DateTimeField(blank=True, null=True, verbose_name='结束时间')
    # 任务类型（按用例、按套件）
    obj_type = models.IntegerField(choices=OBJ_TYPE, verbose_name='任务类型')
    # 运行方式（在页面上选择（排队）计划任务）
    run_type = models.IntegerField(choices=RUN_TYPE, verbose_name='运行方式')
    # 运行状态 （排队中、执行完毕 、执行失败）
    status = models.IntegerField(choices=BATCH_STATUS, default=1, verbose_name='运行状态')
    # 错误消息
    error_msg = models.TextField(blank=True, null=True, verbose_name='错误消息')
    # 计划任务（PeriodicTask ID）
    periodic_task = models.ForeignKey(PeriodicTask, blank=True, null=True, on_delete=models.SET_NULL,
                                      verbose_name='计划任务')
    # 创建人（统一用admin）
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, db_column='created_by',
                                   null=True, verbose_name='创建人')

    # 统计信息 接口 计划数量
    stat_api_plan = models.IntegerField(blank=True, null=True, verbose_name='接口数(计划)')
    # 统计信息 接口 实际数量
    stat_api_run = models.IntegerField(blank=True, null=True, verbose_name='接口数(实际)')
    # 统计信息 接口 实际成功
    stat_api_success = models.IntegerField(blank=True, null=True, verbose_name='接口数(成功)')
    # 统计信息 接口 成功率
    stat_api_success_rto = models.DecimalField(max_digits=5, decimal_places=2,
                                               blank=True, null=True, verbose_name='接口执行成功率(%)')
    # 统计信息 用例 计划数量
    stat_case_plan = models.IntegerField(blank=True, null=True, verbose_name='用例数(计划)')
    # 统计信息 用例 实际数量
    stat_case_run = models.IntegerField(blank=True, null=True, verbose_name='用例数(实际执行)')
    # 统计信息 用例 实际成功
    stat_case_success = models.IntegerField(blank=True, null=True, verbose_name='用例数(实际执行成功)')
    # 统计信息 用例 通过率
    stat_case_success_rto = models.DecimalField(max_digits=5, decimal_places=2,
                                                blank=True, null=True, verbose_name='用例执行通过率(%)')

    # 统计信息 套件 计划数量
    stat_suite_plan = models.IntegerField(blank=True, null=True, verbose_name='用例套件数(计划)')
    # 统计信息 套件 实际数量
    stat_suite_run = models.IntegerField(blank=True, null=True, verbose_name='用例套件数(实际执行)')
    # 统计信息 套件 实际成功
    stat_suite_success = models.IntegerField(blank=True, null=True, verbose_name='用例套件数(实际执行成功)')
    # 统计信息 套件 通过率
    stat_suite_success_rto = models.DecimalField(max_digits=5, decimal_places=2,
                                                 blank=True, null=True, verbose_name='用例套件执行通过率(%)')

    def stat(self):
        logger = logging.getLogger('test_plt')
        # 测试套件
        if self.obj_type == TestBatch.OBJ_TYPE_SUITE:
            self.stat_suite_plan = self.suites.count()  # 计划的套件数量
            self.stat_suite_run = self.suite_run_logs.count()
            self.stat_suite_success = self.suite_run_logs.filter(passed=True).count()
            self.stat_suite_success_rto = self.stat_suite_success / self.stat_suite_plan * 100
        # 用例
        if self.obj_type == TestBatch.OBJ_TYPE_CASE:  # 以 执行测试用例 的方式开展时，统计用例数据
            self.stat_case_plan = self.cases.count()
            self.stat_case_run = self.case_run_logs.count()
            logger.info(f'用例执行数量是{self.stat_case_run}')
            self.stat_case_success = self.case_run_logs.filter(passed=True).count()
            self.stat_case_success_rto = self.stat_case_success / self.stat_case_plan * 100
        else:  # 以执行测试套件的方式开展时，统计用例数据
            # 用例的计划数量
            cnt = 0
            for tb_suite in self.suites.all():
                cnt += tb_suite.case_suite.cases.count()
            self.stat_case_plan = cnt
            # 用例运行数量
            cnt = 0
            for slog in self.suite_run_logs.all():
                cnt += slog.case_run_logs.count()
            self.stat_case_run = cnt
            # 用例通过数量
            cnt = 0
            for slog in self.suite_run_logs.all():
                cnt += slog.case_run_logs.filter(passed=True).count()
            self.stat_case_success = cnt
            # 接口通过率
            self.stat_case_success_rto = self.stat_case_success / self.stat_case_plan * 100

        # 接口
        if self.obj_type == TestBatch.OBJ_TYPE_CASE:
            cnt = 0
            # 1.有几个用例 2.每个用例下有几个接口
            # 接口计划数量
            for tb_case in self.cases.all():
                cnt += tb_case.case.case_apidefs.count()
            self.stat_api_plan = cnt

            # 接口执行数量
            cnt = 0
            for clog in self.case_run_logs.all():
                cnt += clog.case_api_logs.count()
            self.stat_api_run = cnt
            # 接口成功数量
            cnt = 0
            for clog in self.case_run_logs.all():
                cnt += clog.case_api_logs.filter(success=True).count()  # #####
            self.stat_api_success = cnt
            # 接口成功率
            self.stat_api_success_rto = self.stat_api_success / self.stat_api_plan * 100

        else:  # 关联在套件里执行
            cnt = 0
            # 接口计划数量
            for tb_suite in self.suites.all():
                for case in tb_suite.case_suite.cases.all():
                    cnt += case.case_apidefs.count()
            self.stat_api_plan = cnt
            # 接口的运行数量
            cnt = 0
            for slog in self.suite_run_logs.all():
                for clog in slog.case_run_logs.all():  # ######
                    cnt += clog.case_api_logs.count()
            self.stat_api_run = cnt
            # 接口成功数量
            cnt = 0
            for slog in self.suite_run_logs.all():
                for clog in slog.case_run_logs.all():  # ####
                    cnt += clog.case_api_logs.filter(success=True).count()
            self.stat_api_success = cnt
            # 接口的运行成功率
            self.stat_api_success_rto = self.stat_api_success / self.stat_api_plan * 100

    def __repr__(self):
        # Django的魔术方法：get_xxx_display
        return f"测试批次(报告)：ID[{self.id}]: \n"\
               f"项目：{self.project}: \n"\
               f"开始结束时间：{u.common.fmt_cost_time(self.start_at, self.finish_at, cal=True)}； \n" \
               f"任务类型：{self.get_obj_type_display()}: 运行方式：{self.get_run_type_display()}； \n" \
               f"套件数：计划[{self.stat_suite_plan}] | 实际[{self.stat_suite_run}] | 通过[{self.stat_suite_success}] | 通过率[{self.stat_suite_success_rto}]； \n" \
               f"用例数：计划[{self.stat_case_plan}] | 实际[{self.stat_case_run}] | 通过[{self.stat_case_success}] | 通过率[{self.stat_case_success_rto}]； \n" \
               f"接口数：计划[{self.stat_api_plan}] | 实际[{self.stat_api_run}] | 成功[{self.stat_api_success}] | 成功率[{self.stat_api_success_rto}]； \n"

    def __str__(self):
        start = u.common.fmt_local_datetime(self.start_at)
        return f"{self.project} at {start}"

    class Meta:
        verbose_name = '测试批次(报告)'
        verbose_name_plural = verbose_name


class TestBatchCase(models.Model):
    id = models.AutoField(primary_key=True)
    test_batch = models.ForeignKey(TestBatch, on_delete=models.CASCADE, related_name='cases', verbose_name='测试批次')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, verbose_name='用例')

    def __str__(self):
        return f"{self.test_batch} at {self.case}"

    class Meta:
        verbose_name = '测试批次用例'
        verbose_name_plural = verbose_name
        db_table = 'test_plt_testbatch_case'


class TestBatchCaseSuite(models.Model):
    id = models.AutoField(primary_key=True)
    test_batch = models.ForeignKey(TestBatch, on_delete=models.CASCADE, related_name='suites', verbose_name='测试批次')
    case_suite = models.ForeignKey(CaseSuite, on_delete=models.CASCADE, verbose_name='用例套件')

    def __str__(self):
        return f"{self.test_batch} at {self.case_suite}"

    class Meta:
        verbose_name = '测试批次用例套件'
        verbose_name_plural = verbose_name
        db_table = 'test_plt_testbatch_casesuite'


class CaseSuiteRunLog(models.Model):
    id = models.AutoField(primary_key=True)
    # 用例套件 Fk
    case_suite = models.ForeignKey(CaseSuite, on_delete=models.PROTECT, verbose_name="用例套件")
    # 开始时间
    start_at = models.DateTimeField("开始时间", blank=True, null=True)
    # 结束时间
    finish_at = models.DateTimeField("结束时间", blank=True, null=True)
    # 耗时（ms）
    duration = models.IntegerField("耗时(ms)", blank=True, null=True)
    # 测试通过
    passed = models.BooleanField("执行成功", default=False)
    # 错误消息
    error_msg = models.TextField("错误消息", blank=True, null=True)
    # 创建人
    created_by = models.ForeignKey(User, verbose_name="创建人", on_delete=models.SET_NULL, db_column="created_by",
                                   null=True)
    # 测试批次
    test_batch = models.ForeignKey(TestBatch, on_delete=models.CASCADE, related_name='suite_run_logs',
                                   blank=True, null=True, verbose_name='测试批次')
    # 用例执行履历 1:N

    def __str__(self):
        start = u.common.fmt_local_datetime(self.start_at)
        return f"{self.case_suite}({start})"

    class Meta:
        verbose_name = "用例套件执行履历"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_casesuite_run_log'


class CaseRunLog(models.Model):
    """
    用例运行履历
    """
    id = models.AutoField(primary_key=True)
    # 用例FK
    case = models.ForeignKey(Case, on_delete=models.PROTECT, verbose_name="用例")
    # 开始时间
    start_at = models.DateTimeField("开始时间", blank=True, null=True)
    # 结束时间
    finish_at = models.DateTimeField("结束时间", blank=True, null=True)
    # 耗时（ms）
    duration = models.IntegerField("耗时(ms)", blank=True, null=True)
    # 测试通过
    passed = models.BooleanField("执行成功", default=False)
    # 错误消息
    error_msg = models.TextField("错误消息", blank=True, null=True)
    # 创建人
    created_by = models.ForeignKey(User, verbose_name="创建人",
                                   on_delete=models.SET_NULL, db_column="created_by", null=True)
    # 接口执行履历1：N  > 通过ApiRunLog的反向关系实现

    # 用例套件执行履历
    case_suite_run_log = models.ForeignKey(CaseSuiteRunLog,
                                           blank=True, null=True, on_delete=models.CASCADE, related_name='case_run_logs', verbose_name="用例套件执行履历")
    # 用例套件（冗余）
    case_suite = models.ForeignKey(CaseSuite,
                                   blank=True, null=True, on_delete=models.CASCADE, verbose_name="用例套件")
    # 测试批次
    test_batch = models.ForeignKey(TestBatch, on_delete=models.CASCADE, related_name='case_run_logs',
                                   blank=True, null=True, verbose_name='测试批次')

    def __str__(self):
        start = u.common.fmt_local_datetime(self.start_at)
        return f"{self.case}({start})"

    class Meta:
        verbose_name = "用例执行履历"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_case_run_log'


class ApiRunLog(models.Model):
    """
    接口运行履历
    """
    id = models.AutoField(primary_key=True)
    # 接口(models.cascade，删除 apidef的行记录，则删除该条记录对应的 apirunlog)
    api = models.ForeignKey(ApiDef, on_delete=models.CASCADE, )
    # 查询参数
    query_params = models.TextField("查询参数", blank=True, null=True)
    # 请求头
    request_headers = models.TextField("请求头", blank=True, null=True)
    # 请求体
    request_body = models.TextField("请求体", blank=True, null=True)
    # Basic认证username
    auth_username = models.CharField(null=True, blank=True, max_length=128, verbose_name='认证用户名')
    # Basic认证password
    auth_password = models.CharField(null=True, blank=True, max_length=128, verbose_name='认证密码')
    # Bearer认证token
    bearer_token = models.TextField(null=True, blank=True, verbose_name='Bearer Token')
    # 应答头
    response_headers = models.TextField("应答头", blank=True, null=True)
    # 应答体
    response_body = models.TextField("应答体", blank=True, null=True)
    # 状态码
    status_code = models.IntegerField("状态码", blank=True, null=True)
    # 状态码描述
    reason = models.CharField("状态码描述", blank=True, null=True, max_length=100)
    # 最终URL
    final_url = models.CharField("最终URL", blank=True, null=True, max_length=1024)
    # 开始时间
    start_at = models.DateTimeField("开始时间", blank=True, null=True)
    # 结束时间
    finish_at = models.DateTimeField("结束时间", blank=True, null=True)
    # 耗时（ms）
    duration = models.IntegerField("耗时(ms)", blank=True, null=True)
    # 是否执行成功
    success = models.BooleanField("执行成功", default=False)
    # 错误消息
    error_msg = models.TextField("错误消息", blank=True, null=True)
    # 创建人
    created_by = models.ForeignKey(User, verbose_name="创建人", on_delete=models.SET_NULL, db_column="created_by",
                                   null=True)
    # 用例执行履历
    case_run_log = models.ForeignKey(CaseRunLog, on_delete=models.CASCADE, null=True, related_name='case_api_logs', verbose_name="用例执行履历")

    # redis的key值
    redis_key = models.CharField(blank=True, null=True, max_length=128, verbose_name='Redis Key')

    # mysql的执行语句
    mysql_key = models.CharField(blank=True, null=True, max_length=128, verbose_name='Mysql 执行语句')

    def __str__(self):
        start = u.common.fmt_local_datetime(self.start_at)
        return f"{self.api} at {start}"

    class Meta:
        verbose_name = "接口执行履历"
        verbose_name_plural = verbose_name
        db_table = 'test_plt_api_run_log'










