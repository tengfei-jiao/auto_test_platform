import json
import re

from jsonschema.exceptions import SchemaError, ValidationError
from jsonschema.validators import validate

from test_plt.models import CaseApiDef
from test_plt.utils import common


class RespCheckException(Exception):
    def __init__(self, chk_type, reason):
        self.chk_type = chk_type
        self.reason = reason

    def __str__(self):
        return f"应答校验之[{self.chk_type}]失败：{self.reason}"


def check_case_apidef_http(item: CaseApiDef, result: dict):
    # 是否校验总开关
    if not item.verify:
        return True
    # 状态码校验 response.status_code
    if item.status_code and item.status_code != result.get('status_code'):
        raise RespCheckException("状态码", f"预期[{item.status_code}], 实际[{result.get('status_code')}]")

    # 响应时间校验
    check_duration(item, result.get("duration"))

    # HTTP 响应头校验 可以将响应头转为json字符串，使用正则表达式校验
    if item.header_verify and not re.search(item.header_verify, str(result.get("headers"))):
        raise RespCheckException("HTTP响应头", f"预期[{item.header_verify}], 实际[{result.get('headers')}]")

    # 应答体JSON Schema校验，使用json-schema包来做校验
    check_json_schema(item, result.get('text'))

    # 应答体正则表达式校验 使用正则表达式， response.text
    check_regex(item, result.get('text'))

    # 应答体python脚本脚丫，利用python eval（）函数 注意规避安全漏洞
    check_expression(item, result)
    return True


def check_case_apidef_redis(item: CaseApiDef, result: dict):
    # 是否校验总开关
    if not item.verify:
        return True
    # 响应时间校验
    check_duration(item, result.get("duration"))

    # 应答体JSON Schema校验，使用json-schema包来做校验
    check_json_schema(item, result.get('values'))

    # 应答体正则表达式校验 使用正则表达式， response.text
    check_regex(item, result.get('values'))

    # 应答体python脚本脚丫，利用python eval（）函数 注意规避安全漏洞
    check_expression(item, result)
    return True


def check_duration(item: CaseApiDef, duration):
    """
    响应时间校验
    :param item:
    :param duration:
    :return:
    """
    duration = duration / 1000
    if item.response_time and item.response_time <= duration:  # 界面上输入的时间 正常应该是大于 接口的实际运行时间
        raise RespCheckException("响应时间", f"预期[{item.response_time}], 实际[{duration}]")


def check_json_schema(item: CaseApiDef, text):
    """
    应答体JSON Schema校验，使用json-schema包来做校验
    :param item:
    :param text:
    :return:
    """
    if item.json_verify:  # todo 这里有个报错是异常的，需要老师定位
        try:
            validate(instance=json.loads(text), schema=json.loads(item.json_verify))
        except SchemaError as e:
            raise RespCheckException('JSON Schema', f"您输入的JSON Schema包含错误，参考{e}")
        except ValidationError as e:
            raise RespCheckException('JSON Schema', f"接口返回的应答体内容不符合指定的Json Schema要求，参考{e}")
        except Exception as e:
            raise RespCheckException('JSON Schema', f"发生了非预期的错误，参考{e}")


def check_regex(item: CaseApiDef, text):
    """
    应答体正则表达式校验 使用正则表达式， response.text
    :param item:
    :param text:
    :return:
    """
    if item.regex_verify and not re.search(item.regex_verify, text):
        raise RespCheckException('应答体正则表达式', f"预期[{item.regex_verify}], 实际[{text}]")


def check_expression(item: CaseApiDef, result):
    """
    # 应答体python脚本脚丫，利用python eval（）函数 注意规避安全漏洞
    :param item:
    :param result:
    :return:
    """
    if item.python_verify:
        # 1、约定输入格式：#{expression blabla...}
        m = re.match(r"#\{.+\}", item.python_verify)
        if not m:
            raise RespCheckException('应答体python脚本', f"您输入的内容不是系统支持的python表达式，请使用#{{}}来包含python表达式内容。[{item.python_verify}]")
        exp = m.group()  # 拿到#{}里面的内容
        # 4、检查用户输入的表达式的安全性
        if re.search(r'__.+__', item.python_verify):  # __import__ os
            raise RespCheckException('应答体python脚本', f"您输入的python表达式包含不允许的操作")
        # 2、约定可提供的数据：仅限result，而不是所有的response，降低安全隐患
        # 3、约定可提供的功能（函数）：re、json、loads、ast.literal_eval
        local_params = {
            'result': result,
            're': re,
            'parse': common.parse_json_like  # todo 需要总结输出
        }
        try:
            # 5、限制传递eval的上下文
            # 6、执行eval
            eval_ = eval(exp[2:-1], {}, local_params)
            if not eval_:
                raise RespCheckException('应答体python脚本', f"表达式执行结果为：[{eval_}]")
        except Exception as e:
            raise RespCheckException('应答体python脚本', f"表达式执行失败，请先修正再重新执行用例，参考：[{e}]")