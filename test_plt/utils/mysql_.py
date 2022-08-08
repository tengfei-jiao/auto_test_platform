# 使用python怎样连接MySQL
import logging
import time
import traceback
from datetime import datetime
import pymysql
from django.utils import timezone
from test_plt.models import ApiDef, ApiRunLog


def perform_api(api: ApiDef, mysql_key, user, case_log=None):
    logger = logging.getLogger('test_plt')
    start_at = time.time()
    runlog = ApiRunLog()
    runlog.api = api
    runlog.start_at = timezone.make_aware(datetime.fromtimestamp(start_at))
    runlog.mysql_key = mysql_key
    runlog.created_by = user
    runlog.case_run_log = case_log
    try:
        connect = pymysql.connect(
            host=api.deploy_env.hostname,
            port=api.deploy_env.port,
            user=api.db_username,
            password=api.db_password,
            db=api.db_name,
            # charset='utf8'
        )
        cur = connect.cursor()  # 打开游标

        # # 查询
        # error_list = ['delete', 'insert', 'create', 'update', '*']
        # if mysql_key in error_list:
        #     ValidationError("请输入正确的查询语句（仅支持查询）")
        # sql_queue = mysql_key

        cur.execute(mysql_key)  # 执行sql
        connect.commit()
        response_body = [i for i in cur.fetchall()]
        runlog.response_body = response_body  # 获取执行结果
        cur.close()  # 关闭游标、连接
        connect.close()
        runlog.success = True
        logger.info(f'{runlog.api}执行成功')

    except Exception as e:
        trace_msg = traceback.format_exc()
        runlog.success = False
        runlog.error_msg = f"{e}\n{trace_msg}"  # __str__
        logger.info(f'{runlog.api}执行失败：{runlog.error_msg}')

    finally:
        # 履历 -3记录接口执行的时间戳
        finish_at = time.time()
        # 履历 -4记录接口执行的耗时(单位是什么？秒/毫秒/微妙/纳秒？)
        duration = (finish_at - start_at)
        runlog.finish_at = timezone.make_aware(datetime.fromtimestamp(finish_at))
        runlog.duration = duration * 1000
        runlog.save()

    return {
        'runlog_id': runlog.id,
        'values': runlog.response_body,
        'duration': runlog.duration,
        'success': runlog.success
    }