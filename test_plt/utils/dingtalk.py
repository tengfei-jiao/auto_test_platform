from dingtalkchatbot.chatbot import DingtalkChatbot
from django.conf import settings

DINGTALK_TEXT_TMPL_API_TASK = '【接口测试任务完成通知】\n%s'


def send_text(message, at_mobiles=[], tmpl=''):
    web_hook = settings.DINGTALK_WEB_HOOK
    sign = settings.DINGTALK_WEB_HOOK_SIGN
    if not web_hook:
        return

    # 初始化机器人
    chatbot = DingtalkChatbot(web_hook) if not sign else DingtalkChatbot(web_hook, secret=sign)

    # text消息@所有人
    msg = message if not tmpl else tmpl % message
    chatbot.send_text(msg=msg, at_mobiles=at_mobiles)

# def send_text(message, at_mobiles=[], tmpl='', web_hook=None, sign=None):
#     if not web_hook:
#         return
#
#     # 初始化机器人
#     chatbot = DingtalkChatbot(web_hook) if not sign else DingtalkChatbot(web_hook, secret=sign)
#
#     # text消息@所有人
#     msg = message if not tmpl else tmpl % message
#     chatbot.send_text(msg=msg, at_mobiles=at_mobiles)