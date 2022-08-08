import ast
import json
import logging
import re
import time
import traceback
from datetime import datetime
from test_plt.utils import common

from django.utils import formats, timezone
from test_plt.models import Case, CaseRunLog, CaseSuiteRunLog, ApiDef, CaseApiDef
from test_plt.utils import resp, http, redis_
from test_plt.utils.resp import RespCheckException


def trunc_text(text, limit=100, padding='...'):
    if not text or len(text) <= limit:
        return text
    return text[:limit-len(padding)] + padding


def perform_case(case: Case, user, case_suite=None, case_suite_log=None, suite_ctx=None, proj_ctx=None, test_batch=None):
    """
    运行测试用例
    :param test_batch: 测试批次
    :param case_suite_log: 测试套件日志
    :param case_suite: 测试套件
    :param case: 从数据库获取的测试用例
    :param user: 从数据库获取的创建人，一般是 request.user
    :param proj_ctx: 项目变量
    :param suite_ctx: 测试套件变量
    :return: True/False
    """
    logger = logging.getLogger('test_plt')
    # 执行单个用例
    logger.info(f'[{case.name}] 执行开始')
    flag = True
    errmsg = None
    # 用例上下文
    case_ctx = {}
    case_log = push_case_run_log(case, case_suite, case_suite_log, user=user, test_batch=test_batch)
    for item in case.case_apidefs.order_by('reorder').all():  # type: CaseApiDef
        api: ApiDef = item.api
        try:
            # 前置处理
            exec_py_script(item.pre_proc, None, case_ctx, suite_ctx, proj_ctx)
            # 参数预处理(对用户名、密码、token、redis的输入做统一处理，让输入框最终只有 uuid 的值)
            proc_apidef_params(item, case_ctx, suite_ctx, proj_ctx)
            # 第一段：执行
            # 判断协议类型 http\redis\mysql?
            if api.protocol == 'http':
                query_params = item.get_query_params(case_ctx, suite_ctx, proj_ctx)
                http_headers = item.get_http_headers(case_ctx, suite_ctx, proj_ctx)
                request_body = item.get_request_body(case_ctx, suite_ctx, proj_ctx)
                result = http.perform_api(api, query_params, http_headers, request_body,
                                          item.auth_username, item.auth_password, item.bearer_token,
                                          user, case_log=case_log)
            elif api.protocol == 'redis':
                result = redis_.perform_api(api, item.redis_key, user, case_log=case_log)
            if not result.get('success') and item.abort_when_fail:  # 如果接口执行失败 且 用例勾选了'失败时终止'
                flag = False
                break
        except Exception as e:
            errmsg = str(e)
            logger.info(f'{e}\n {traceback.format_exc()}')
            if item.abort_when_fail:
                flag = False
                break
        # 第二段：始做校验
        try:
            # 判断协议类型 http\redis\mysql?
            if api.protocol == 'http':
                resp.check_case_apidef_http(item, result)
            elif api.protocol == 'redis':
                resp.check_case_apidef_redis(item, result)
            logger.info(f"[{api}] 校验成功")

            # 后置处理？？？todo
            exec_py_script(item.post_proc, result, case_ctx, suite_ctx, proj_ctx)
            logger.info(f"case_ctx=【{case_ctx}】\nsuite_ctx=【{suite_ctx}】\nproj_ctx=【{proj_ctx}】\n")
        except Exception as e:
            if isinstance(e, RespCheckException):
                error_msg = f"接口[{api}] 校验失败，原因{e}"
            else:
                error_msg = traceback.format_exc()
            logger.info(error_msg)
            if item.abort_when_fail:
                flag = False
                break

    # 更新测试用例执行的履历：将 用例执行的结果 更新到 数据库的用例执行履历表 CaseRunLog
    if not flag and case.abort_when_fail:
        msg = f"{case.name} 执行失败，原因：有用例接口执行失败且要求用例执行中止，参考：{errmsg}"
        push_case_run_log(case, case_run_log=case_log, passed=False, err_msg=msg)
    else:
        push_case_run_log(case, case_run_log=case_log, passed=True)

    logger.info(f'[{case.name}] 执行结束')
    return flag


def push_case_run_log(case, case_suite=None, case_suite_log=None, test_batch=None, case_run_log=None, user=None, passed=True,
                      err_msg=None):
    """

    :param err_msg:
    :param test_batch:
    :param case:
    :param case_suite:
    :param case_suite_log:
    :param case_run_log:
    :param user:
    :param passed:
    :return:
    """
    now = time.time()
    if case_run_log:
        case_run_log.finish_at = timezone.make_aware(datetime.fromtimestamp(now))
        case_run_log.duration = (now - case_run_log.temp_start_at) * 1000
        case_run_log.error_msg = err_msg
        case_run_log.passed = passed
        case_run_log.save()
        return None
    else:
        obj = CaseRunLog.objects.create(
            start_at=timezone.make_aware(datetime.fromtimestamp(now)),
            case=case,
            case_suite=case_suite,
            case_suite_run_log=case_suite_log,
            created_by=user,
            test_batch=test_batch
        )
        obj.temp_start_at = now
        return obj


def push_case_suite_run_log(case_suite, suite_log=None, user=None, passed=True, err_msg=None, test_batch=None):
    """
    推送用例执行履历
    :param test_batch:
    :param case_suite: 用例套件
    :param suite_log: 用例执行履历
    :param user: 当前用户
    :param passed: 是否通过
    :param err_msg: 错误消息
    :return: 用例执行履历或None
    """
    now = time.time()
    if suite_log:
        suite_log.finish_at = timezone.make_aware(datetime.fromtimestamp(now))
        suite_log.duration = (now - suite_log.temp_start_at) * 1000
        suite_log.error_msg = err_msg
        suite_log.passed = passed
        suite_log.save()
        return None
    else:
        obj = CaseSuiteRunLog.objects.create(
            start_at=timezone.make_aware(datetime.fromtimestamp(now)),
            case_suite=case_suite,
            created_by=user,
            test_batch=test_batch
        )
        obj.temp_start_at = now
        return obj


def fmt_cost_time(start_at, finish_at, duration=None, cal=True):
    if cal:
        delta = finish_at - start_at
        duration = int(delta.seconds * 1000 + delta.microseconds / 1000)
    start = fmt_local_datetime(start_at)
    finish = fmt_local_datetime(finish_at)
    return f'{start}~ {finish} (耗时：{duration}ms)' if duration else f"{start}~ {finish}"


def fmt_local_datetime(utc_dt, format='Y-m-d H:i:s'):
    """
    将UTC时间格式转化为本地时间
    :param utc_dt: UTC时间
    :param format: 日期时间格式
    :return: 格式化的本地时间
    """
    return formats.date_format(timezone.localtime(utc_dt), format)


def parse_json_like(input__, default=None):
    """
    将类似json的文本解析为python数据结构
    :param input__:
    :param default:
    :return:
    """
    if not input__:
        return default
    if isinstance(input__, list) or isinstance(input__, dict):
        return input__
    try:
        return json.loads(input__)  # 将str类型转换成dict类型
    except:
        pass
    try:
        return ast.literal_eval(input__)  # ast.literal_eval()只会执行合法的Python类型，从而大大降低系统的风险性
    except:
        pass
    return default


def exec_py_script(input_, result, case_ctx=None, suite_ctx=None, proj_ctx=None):  # todo 先后置处理，在考虑实现前置处理
    """
    # 应答体python脚本脚丫，利用python eval（）函数 注意规避安全漏洞
    :param item:
    :param result:
    :return:
    """
    if not input_:  # 如果输入没填写，不做任何处理
        return
    # 1、约定输入格式：#{script blabla...}
    ms = re.findall(r"#\{.+?\}", input_)
    if len(ms) == 0:
        raise Exception(f"您输入的内容不是系统支持的python表达式，请使用#{{}}来包含python表达式内容。")
    # 4、检查表达式的安全性
    if re.search(r"__.+__", input_):
        raise Exception(f"您输入的【python表达式】包含不合法字符")
    if re.search(r"imoprt[ \s]\w", input_):
        raise Exception(f"您输入的【python表达式】包含不合法字符")
    # 2、约定可提供的数据：仅限result，而不是所有的response，降低安全隐患
    # 3、约定可提供的功能（函数）：re、json、loads、ast.literal_eval
    local_params = {
        'result': result,
        're': re,
        'parse': common.parse_json_like,  # todo
        "case_ctx": case_ctx,
        "suite_ctx": suite_ctx,
        "proj_ctx": proj_ctx,
    }
    # 5、限制传递eval的上下文
    # 6、注意exec和eval的区别
    for exp in ms:
        exec(exp[2:-1], {}, local_params)


def proc_apidef_params(item: CaseApiDef, case_ctx=None, suite_ctx=None, proj_ctx=None):
    """
    处理用例接口的参数，主要用于参数中的 python 表达式
    :param proj_ctx:
    :param suite_ctx:
    :param item:
    :param case_ctx:
    :return:
    """
    for attr in ['redis_key', 'auth_username', 'auth_password', 'bearer_token']:
        val = getattr(item, attr)
        if not val:
            continue
        # 给 api 的属性 attr 赋新值，原来是我们界面输入的值，新值是处理的uuid的值
        setattr(item, attr, proc_param_expression(val, case_ctx, suite_ctx, proj_ctx))


def proc_param_expression(val, case_ctx=None, suite_ctx=None, proj_ctx=None):
    """
    处理用例接口参数中的 python 表达式，将表达式替换为其执行结果
    :param val:  界面输入的内容
    :param case_ctx:  上下文
    :return: 返回的是表达式的执行结果
    """
    ms = re.findall(r"#\{.+\}", val)
    if len(ms) == 0:
        return val
    local_params = {
        'case_ctx': case_ctx,
        're': re,
        'parse': common.parse_json_like,
        "suite_ctx": suite_ctx,
        "proj_ctx": proj_ctx,
    }

    def new_content(matched):
        s = matched.group()
        if re.search(r'__.+__', s):
            raise Exception(f"您输入的python表达式包含不允许的操作")
        return str(eval(s[2:-1], {}, local_params))
    # val是界面输入的原始字符串，按照第一个参数进行正则匹配，将匹配到的内容用函数 new_content 进行处理。最终输出 uuid的值
    return re.sub(r"#\{.+\}", new_content, val)





