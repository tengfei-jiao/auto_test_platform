import ast
import json

from django import forms
from django.core.exceptions import ValidationError

from test_plt.models import ApiDef


FONT_MONO = 'font-family:monospace'  # 设置等宽字体


class RunApiForm(forms.Form):
    """
    form -- 页面表单
    form的属性 -- 表单的一个项
    定义了表单项、 数据的症状、检验、html渲染
    """
    # 一个 MultipleHiddenInput 部件，封装了一组隐藏的输入元素
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)

    query_params = forms.CharField(label='查询参数', required=False, widget=forms.Textarea(attrs={
        'rows': 6,
        'cols': 80,
        'style': FONT_MONO,
    }))
    http_headers = forms.CharField(label='请求头', required=False, widget=forms.Textarea(attrs={
        'rows': 6,
        'cols': 80,
        'style': FONT_MONO,
    }))
    request_body = forms.CharField(label='请求体', required=False, widget=forms.Textarea(attrs={
        'rows': 6,
        'cols': 80,
        'style': FONT_MONO,
    }))
    auth_username = forms.CharField(label="Basic认证用户名", required=False)
    auth_password = forms.CharField(label="Basic认证密码", required=False)
    bearer_token = forms.CharField(label='Bearer认证令牌', required=False, widget=forms.Textarea(attrs={
        'rows': 6,
        'cols': 80,
        'style': FONT_MONO,
    }))
    redis_key = forms.CharField(label="Redis key", required=False)
    mysql_key = forms.CharField(label='Mysql 语句', required=False, widget=forms.Textarea(attrs={
        'rows': 6,
        'cols': 80,
        'style': FONT_MONO,
    }))

    def chk_json(self, attr):
        """
        检查输入是不是json格式的内容
        :param attr: 界面控件在RunApiForm中的字段名，被用来获取用户在界面控件输入的内容
        :return:
        """
        val = self.cleaned_data.get(attr)  # 如果 attr=query_params，val 获取界面查询参数的输入内容
        if val:
            try:
                json.loads(val)
            except:
                raise ValidationError("请输入标准的json格式")
        return val

    def clean_query_params(self):
        """
        # 如过有 clear_xxx 开头的函数，则自动执行该代码，用来处理数据校验（自定义的业务上的校验）
        # （1）字面上（数值、字符串、日期、时间、email等）
        # （2）业务上（符合某种业务逻辑）
        :return: 用户在界面输入的 查询参数内容
        """
        return self.chk_json("query_params")

    def clean_http_headers(self):
        """
        :return: 用户在界面输入的 请求头内容
        """
        val = self.chk_json("http_headers")
        if not val.isascii():
            raise ValidationError("HTTP Header 只支持ASCII字符！")
        return val

    def clean_request_body(self):
        """
        :return: 用户在界面输入的 请求体内容
        """
        val = self.cleaned_data.get("request_body")
        if not val:
            return val
        api = self.get_apidef()
        if api.body_type in ('form-urlencoded', 'raw-json'):
            return self.chk_json('request_body')
        else:
            return val

    def clean_redis_key(self):
        api = self.get_apidef()
        if api.protocol == 'redis' and not self.cleaned_data.get('redis_key'):
            raise ValidationError("Redis Key是必须的！")

    def clean_sql_key(self):
        """
        校验redis不能为空，为空时给出错误提示
        :return:
        """
        api = self.get_apidef()
        val = self.cleaned_data.get('mysql_key')
        if val:
            return val
        if api.protocol == 'mysql' and not val:
            raise ValidationError("Mysql语句是必填项")

    def get_apidef(self) -> ApiDef:  # 定义返回的类型
        api_id = ast.literal_eval(self.cleaned_data.get("_selected_action"))[0]  # 将表面的列表转换为python的列表
        return ApiDef.objects.get(id=api_id)

























