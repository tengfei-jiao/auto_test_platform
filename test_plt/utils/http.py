import json
import logging
import re
import time
import traceback
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone

from test_plt.models import ApiRunLog, ApiDef


def perform_api(api: ApiDef, query_params, http_headers, request_body, auth_username, auth_password, bearer_token, user,
                case_log=None):
    """
    执行接口
    :param api: 要执行的接口
    :param query_params: 请求参数
    :param http_headers: 请求头
    :param request_body: 请求体
    :param auth_username: 账号
    :param auth_password: 密码
    :param bearer_token: token值
    :param user: 接口创建人
    :param case_log: 关联测试用例日志
    :return:
    """
    logger = logging.getLogger('test_plt')

    # query_params, http_headers, request_body 字典还是字符串？都兼容了
    # 参数预处理
    if isinstance(query_params, str):
        query_params = json.loads(query_params) if query_params else {}
    if isinstance(http_headers, str):
        http_headers = json.loads(http_headers) if http_headers else {}
    start_at = time.time()
    runlog = ApiRunLog()
    runlog.api = api
    runlog.start_at = timezone.make_aware(datetime.fromtimestamp(start_at))
    runlog.query_params = query_params
    runlog.request_headers = http_headers
    runlog.request_body = request_body
    runlog.created_by = user
    runlog.auth_username = auth_username
    runlog.auth_password = auth_password
    runlog.bearer_token = bearer_token
    runlog.case_run_log = case_log

    # 根据请求头的content-type 对请求体进行编码
    if isinstance(request_body, str):  # 如果是字典则及处理，不是字典则不处理继续运行后面代码
        request_body = request_body.encode(extract_header_charset(http_headers))

    # 处理 Bearer Token 认证
    if api.auth_type == "bearer":
        http_headers["Authorization"] = f"Bearer {bearer_token}"
    # 7 将http接口请求发送服务器
    try:
        options = {
            "params": query_params,
            "headers": http_headers,
            'auth': (auth_username, auth_password) if api.auth_type == 'basic' else None,
            'timeout': settings.TEST_PLT_API_TIMEOUT,
            'verify': False
        }
        # 根据请求体类型决定存入request的参数
        options.update({
            "json" if api.body_type == "raw-json" else "data": parse_request_body(api, request_body)
        })
        res = requests.request(api.http_method, api.to_url(), **options)
        # 8 获取并解析目标服务器的响应
        runlog.success = True
        runlog.response_body = res.text
        runlog.response_headers = res.headers
        runlog.status_code = res.status_code
        runlog.reason = res.reason
        runlog.final_url = res.url
        logger.info(f"[{runlog.api}] 执行成功")
    except Exception as e:
        trace_msg = traceback.format_exc()
        runlog.success = False
        runlog.error_msg = f"{e}\n{trace_msg}"  # __str__
        logger.info(f"[{runlog.api}] 执行失败： {runlog.error_msg}")  # 当成业务消息输出
    finally:
        # 记录接口执行的结束时间戳
        finish_at = time.time()
        # 记录接口执行的耗时（耗时的单位？s、ms）
        duration = finish_at - start_at
        runlog.finish_at = timezone.make_aware(datetime.fromtimestamp(finish_at))
        runlog.duration = duration * 1000
        # 这里做的是一些收尾工作
        runlog.save()
    return {
        "runlog_id": runlog.id,
        "status_code": runlog.status_code,
        "text": runlog.response_body,
        "headers": runlog.response_headers,
        "duration": runlog.duration,
        "success": runlog.success
    }


def parse_request_body(api: ApiDef, request_body):
    """
    解析请求体为JSON或普通文本
    :param api: ApiDef
    :param request_body: 请求体文本
    :return: 普通文本或字典
    """
    if isinstance(request_body, dict):
        return request_body
    if api.body_type in ('form-urlencoded', 'raw-json'):
        return json.loads(request_body) if request_body else {}
    else:
        return request_body


def extract_header_charset(http_headers, default_charset="utf-8"):
    """
    处理请求头的 content-type 中提取 charset
    :param http_headers: 请求头
    :param default_charset: 缺省字符集
    :return: content-type 定义的 charset
    """
    if not http_headers:
        return default_charset
    headers = http_headers if isinstance(http_headers, dict) else json.loads(http_headers)
    content_type = headers.get('content-Type', '')
    charset = re.findall('charset=([^;$]+)', content_type)
    if len(charset) == 0:
        return default_charset
    return charset[0]


