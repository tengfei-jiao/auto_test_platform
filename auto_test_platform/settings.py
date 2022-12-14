"""
Django settings for auto_test_platform project.

Generated by 'django-admin startproject' using Django 3.2.9.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# django-envrion-2
env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)
env.smart_cast = False
env.read_env((BASE_DIR / '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-l&v%kas(^l!s1x4e6!^ph)8=xjrxaw+lv!1kfsjc@%x3dlwrd@'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = ['*']


# Application definition
INSTALLED_APPS = [
    # 'debug_toolbar',
    'simpleui',
    'nested_admin',
    'test_plt.apps.TestPltConfig',
    'django_celery_results',
    'django_celery_beat',
    # 'django.contrib.admin',
    'auto_test_platform.apps.TestPlatAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# 中间件
MIDDLEWARE = [
    # "debug_toolbar.middleware.DebugToolbarMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'test_plt.middlewares.EnsureProjectIdMiddleware',
]

ROOT_URLCONF = 'auto_test_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'auto_test_platform.wsgi.application'


# 数据库的设置*
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': env.db()
}


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# 语言代码设置，国际化、
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = True

USE_TZ = True  # 启用时区

LOCALE_PATHS = (BASE_DIR/"locale/",)


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
# 面向源代码（开发时候，将静态资源放到这里，runserver的debug运行时候会自动加载这里的静态资源）
STATICFILES_DIRS = [
    BASE_DIR / 'shared_static',
]
# 面向部署
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'


# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TEST_PLT_API_TIMEOUT = (
    env.float('TEST_PLT_API_TIMEOUT_CONNECT', default=3.1),
    env.float('TEST_PLT_API_TIMEOUT_RESP', default=30),

)

LIST_PER_PAGE = env.int('LIST_PER_PAGE', default=10)

# logging
LOG_DIR = Path(env.str('LOG_DIR', default='../logs'))
if not LOG_DIR.exists():
    LOG_DIR.mkdir()
ERROR_LOG_FILE = LOG_DIR / env.str('ERROR_LOG_FILE', default='error.log')
INFO_LOG_FILE = LOG_DIR / env.str('INFO_LOG_FILE', default='info.log')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file_test_plt': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': INFO_LOG_FILE,
            'encoding': 'utf-8',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose'
        },
        'file_django': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': ERROR_LOG_FILE,
            'encoding': 'utf-8',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose'
        },
        'console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file_django', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'test_plt': {
            'handlers': ['file_test_plt'],
            'level': env.str("LOG_TEST_PLT_LEVEL", default='info'),
            'propagate': False,
        },
    },
}

# ######### CELERY ################
# 最重要的配置，消息broker的连接方式，格式为：db://user:password@host:port/dbname
CELERY_BROKER_URL = env.str('CELERY_BROKER_URL')

# 时区设置
CELERY_TIMEZONE = TIME_ZONE

# 为Django_celery_results 存储celery任务执行结果设置后台
# 格式为：db+schema：//user:password@host/dbname
# 支持数据库django-db和缓存django-cache存储任务状态及结果
CELERY_RESULT_BACKEND = 'django-db'

# 为任务设置超时时间，单位秒，即超时中止，执行下个任务
CELERY_TASK_TIME_LIMIT = env.int('CELERY_TASK_TIME_LIMIT', default=600)  # 千万注意根据项目时间情况计算！！

# 为存储结果设置过期日期，默认你为1天。设置为0，存储结果不会过期
# 如果beat开启，celery每天会自动清除过期记录
CELERY_RESULT_EXPIRES = env.int('CELERY_RESULT_EXPIRES', default=259200)

# 为beat执行数据库计划表
# CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULER = 'auto_test_platform.schedulers:TestPltDatabaseScheduler'

INTERNAL_IPS = [
    "127.0.0.1",
]

# 钉钉群通知
DINGTALK_WEB_HOOK = 'https://oapi.dingtalk.com/robot/send?access_token=' + env.str('DINGTALK_WEB_HOOK_TOKEN')
# 加签
DINGTALK_WEB_HOOK_SIGN = env.str('DINGTALK_WEB_HOOK_SIGN')


# #######simpleui###### #
# 配置simpleui的logo图片
SIMPLEUI_LOGO = '/static/logo.jpg'
# simpleui首页的自带信息
SIMPLEUI_HOME_INFO = False
SIMPLEUI_ANALYSIS = False
# 默认主题
SIMPLEUI_DEFAULT_THEME = 'simpleui.css'
SIMPLEUI_HOME_QUICK = True
SIMPLEUI_HOME_ACTION = True

# # simpleui下采用了默认图标的方式，SIMPLEUI_CONFIG为Null
# SIMPLEUI_CONFIG = {
#     # 是否使用系统默认菜单，自定义菜单时建议关闭。
#     'system_keep': False,
#     # 用于菜单排序和过滤，不填此字段为默认排序和全部显示。空列表[] 为全部不显示。
#     'menu_display': ['测试平台', '后台任务结果', '周期性任务', '认证和授权'],
#     # 设置是否开启动态菜单，默认为False. 如果开启，则会在每次用户登录时刷新展示菜单内容。一般建议关闭。
#     'dynamic': False,
#     'menus': [
#         {
#             'app': 'test_plt',
#             'name': '测试平台',
#             'icon': 'fa fa-th-list',
#             'models': [
#                 {
#                     'name': '测试项目',
#                     'url': '/admin/test_plt/project/',
#                     'icon': 'fa fa-calendar-check'
#                 },
#                 {
#                     'name': '接口定义',
#                     'url': '/admin/test_plt/apidef/',
#                     'icon': 'fa fa-paper-plane'
#                 },
#                 {
#                     'name': '接口执行履历',
#                     'url': '/admin/test_plt/apirunlog/',
#                     'icon': 'fa fa-history'
#                 },
#                 {
#                     'name': '用例',
#                     'url': '/admin/test_plt/case/',
#                     'icon': 'fa fa-file'
#                 },
#                 {
#                     'name': '用例执行履历',
#                     'url': '/admin/test_plt/caserunlog/',
#                     'icon': 'fa fa-history'
#                 },
#                 {
#                     'name': '用例套件',
#                     'url': '/admin/test_plt/casesuite/',
#                     'icon': 'fa fa-suitcase'
#                 },
#                 {
#                     'name': '用例套件执行履历',
#                     'url': '/admin/test_plt/casesuiterunlog/',
#                     'icon': 'fa fa-history'
#                 },
#                 {
#                     'name': '测试批次(报告)',
#                     'url': '/admin/test_plt/testbatch/',
#                     'icon': 'fa fa-tasks'
#                 },
#                 {
#                     'name': '用例接口',
#                     'url': '/admin/test_plt/caseapidef/',
#                     'icon': 'fa fa-cogs'
#                 },
#                 {
#                     'name': '项目成员',
#                     'url': '/admin/test_plt/projectmember/',
#                     'icon': 'fa fa-comments'
#                 },
#                 {
#                     'name': '部署环境',
#                     'url': '/admin/test_plt/deployenv/',
#                     'icon': 'fa fa-server'
#                 },
#             ]
#         },
#         {
#             'app': 'django_celery_results',
#             'name': '后台任务结果',
#             'icon': 'fa fa-database',
#             'models': [
#                 {
#                     'name': '任务结果',
#                     'url': '/admin/django_celery_results/taskresult/',
#                     'icon': 'fa fa-file'
#                 }
#             ]
#         },
#         {
#             'app': 'django_celery_beat',
#             'name': '周期性任务',
#             'icon': 'fa fa-tasks',
#             'models': [
#                 {
#                     'name': '周期性任务',
#                     'url': '/admin/django_celery_beat/periodictask/',
#                     'icon': 'fa fa-tasks'
#                 },
#                 {
#                     'name': '定时',
#                     'url': '/admin/django_celery_beat/clockedschedule/',
#                     'icon': 'fa fa-clock'
#                 },
#                 {
#                     'name': 'Crontabs',
#                     'url': '/admin/django_celery_beat/crontabschedule/',
#                     'icon': 'fa fa-hourglass-half'
#                 },
#                 {
#                     'name': '间隔',
#                     'url': '/admin/django_celery_beat/intervalschedule/',
#                     'icon': 'el-icon-timer'
#                 },
#                 {
#                     'name': '太阳事件',
#                     'url': '/admin/django_celery_beat/solarschedule/',
#                     'icon': 'fa fa-sun'
#                 },
#             ]
#         },
#         {
#             'app': 'auth',
#             'name': '认证和授权',
#             'icon': 'fa fa-user-shield',
#             'models': [
#                 {
#                     'name': '用户',
#                     'url': 'auth/user/',
#                     'icon': 'fa fa-user'
#                 },
#                 {
#                     'name': '组',
#                     'url': 'auth/group/',
#                     'icon': 'fa fa-users'
#                 },
#                 {
#                     'name': '权限',
#                     'url': 'auth/permission/',
#                     'icon': 'fa fa-street-view'
#                 }
#             ]
#         },
#     ]
# }
# SIMPLEUI_CONFIG = None
SIMPLEUI_ICON = {
    '测试项目': 'fa fa-calendar-check',
    '接口定义': 'fa fa-paper-plane',
    '接口执行履历': 'fa fa-history',
    '用例': 'fa fa-file',
    '用例执行履历': 'fa fa-history',
    '用例套件': 'fa fa-suitcase',
    '用例套件执行履历': 'fa fa-history',
    '测试批次(报告)': 'fa fa-tasks',
    '用例接口': 'fa fa-cogs',
    '项目成员': 'fa fa-comments',
    '部署环境': 'fa fa-server',
    '认证和授权': 'fa fa-user-shield',
    '用户': 'fa fa-user',
    '组': 'fa fa-users',
    '权限': 'fa fa-street-view',
    '周期性任务': 'fa fa-tasks',
    '定时': 'fa fa-clock',
    'Crontabs': 'fa fa-hourglass-half',
    '间隔': 'el-icon-timer',
    '太阳事件': 'fa fa-sun',
}