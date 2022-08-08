import logging
import time
import traceback
from datetime import datetime
import redis
from django.utils import timezone
from test_plt.models import ApiRunLog, ApiDef


def perform_api(api: ApiDef, redis_key, user, case_log=None):
    logger = logging.getLogger('test_plt')
    start_at = time.time()
    runlog = ApiRunLog()
    runlog.api = api
    runlog.start_at = timezone.make_aware(datetime.fromtimestamp(start_at))
    runlog.redis_key = redis_key
    runlog.created_by = user
    runlog.case_run_log = case_log
    # 7 连接redis，获取响应的内容
    try:
        conn = redis.Redis(host=api.deploy_env.hostname,
                           port=api.deploy_env.port,
                           db=api.db_name,
                           password=api.db_password,
                           decode_responses=True)
        runlog.success = True
        runlog.response_body = conn.get(redis_key)
        logger.info(f'{runlog.api}执行成功')
    except Exception as e:
        trace_msg = traceback.format_exc()
        runlog.success = False
        runlog.error_msg = f"{e}\n{trace_msg}"  # __str__
        logger.info(f"[{runlog.api}] 执行失败： {runlog.error_msg}")  # 当成业务消息输出
    finally:
        # 记录接口执行的结束时间戳
        finish_at = time.time()
        runlog.finish_at = timezone.make_aware(datetime.fromtimestamp(finish_at))
        # 记录接口执行的耗时（耗时的单位？s、ms）
        runlog.duration = (finish_at - start_at) * 1000
        # 存入数据库
        runlog.save()
    return {
        "runlog_id": runlog.id,
        "values": runlog.response_body,
        "duration": runlog.duration,
        "success": runlog.success
    }


