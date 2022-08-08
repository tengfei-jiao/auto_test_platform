# 一个测试任务
import logging
from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from test_plt.models import Case, CaseSuite, TestBatch
from test_plt.utils import common, dingtalk


# @shared_task()
# def task_plus(a, b):
#     return a+b


def run_cases(case_ids, user_id, bat_id):
    logger = logging.getLogger('test_plt')
    logger.info(f"run_cases task start: case_ids={case_ids}; bat_id={bat_id}; user_id={user_id}")
    suite_ctx = {}
    task_flag = False
    # 获取所选的用例
    # 实例化一个用例执行履历
    bat: TestBatch = TestBatch.objects.get(id=bat_id)
    try:
        for case_id in case_ids:  # type:Case
            case = Case.objects.get(id=case_id)
            user = User.objects.get(id=user_id)
            case_flag = common.perform_case(case, user, suite_ctx=suite_ctx, test_batch=bat)
            if not case_flag and case.abort_when_fail:
                logger.info(f"【{case.name}】执行失败，原因：有用例接口执行失败且要求用例执行终止.")
                break
        bat.status = TestBatch.STATUS_FINISHED
        bat.stat()
    except Exception as e:
        bat.status = TestBatch.STATUS_FAILED
        bat.error_msg = str(e)
        task_flag = False
    bat.finish_at = timezone.now()
    bat.save()
    logger.info(f"run_cases task finished.")
    dingtalk.send_text(repr(bat), tmpl=dingtalk.DINGTALK_TEXT_TMPL_API_TASK)
    return task_flag

# def run_cases(case_ids, user_id, bat_id):
#     logger = logging.getLogger('test_plt')
#     logger.info(f"run_cases task start: case_ids={case_ids}; bat_id={bat_id}; user_id={user_id}")
#     suite_ctx = {}
#     task_flag = False
#     # 获取所选的用例
#     # 实例化一个用例执行履历
#     bat: TestBatch = TestBatch.objects.get(id=bat_id)
#     try:
#         for case_id in case_ids:  # type:Case
#             case = Case.objects.get(id=case_id)
#             user = User.objects.get(id=user_id)
#             case_flag = common.perform_case(case, user, suite_ctx=suite_ctx, test_batch=bat)
#             if not case_flag and case.abort_when_fail:
#                 logger.info(f"【{case.name}】执行失败，原因：有用例接口执行失败且要求用例执行终止.")
#                 break
#         bat.status = TestBatch.STATUS_FINISHED
#         bat.stat()
#     except Exception as e:
#         bat.status = TestBatch.STATUS_FAILED
#         bat.error_msg = str(e)
#         task_flag = False
#     bat.finish_at = timezone.now()
#     bat.save()
#     logger.info(f"run_cases task finished.")
#     dingtalk.send_text(repr(bat), tmpl=dingtalk.DINGTALK_TEXT_TMPL_API_TASK,
#                        web_hook=bat.project.project_env.dingtalk_web_hook,
#                        sign=bat.project.project_env.dingtalk_web_hook_sign, )
#     return task_flag


@shared_task()
def run_cases_queue(case_ids, user_id, bat_id):
    return run_cases(case_ids, user_id, bat_id)


@shared_task()
def run_case_periodic(case_ids, user_id, periodic_task_id=None):
    """
    异步执行 计划任务 的函数
    :param case_ids: 测试用例的id值
    :param user_id: 用例执行者的id值
    :param periodic_task_id: 计划任务的 id 值
    :return:
    """
    # cases = [Case.objects.get(id=cid) for cid in case_ids]  # 思考题：效率？太低了
    case = Case.objects.get(id=case_ids[0])
    bat = TestBatch.objects.create(
        project=case.project,
        created_by_id=user_id,
        start_at=timezone.now(),
        run_type=TestBatch.RUN_TYPE_PERIODIC,
        obj_type=TestBatch.OBJ_TYPE_CASE,
        status=TestBatch.STATUS_PENDING,
        periodic_task_id=periodic_task_id
    )
    for cid in case_ids:
        bat.cases.create(case_id=cid, test_batch=bat)
    return run_cases(case_ids, user_id, bat.id)


def run_suites(suites_id, user_id, bat_id):
    logger = logging.getLogger('test_plt')
    proj_ctx = {}
    task_flag = True
    bat: TestBatch = TestBatch.objects.get(id=bat_id)
    try:
        for suite_id in suites_id:
            suit_flag = True
            suite_ctx = {}
            suite = CaseSuite.objects.get(id=suite_id)
            user = User.objects.get(id=user_id)
            logger.info(f'[{suite.name}] 执行开始')
            suite_log = common.push_case_suite_run_log(suite, user=user, test_batch=bat)
            for case in suite.cases.order_by("reorder"):  # type: Case
                case_flag = common.perform_case(case, user, case_suite=suite, case_suite_log=suite_log,
                                                suite_ctx=suite_ctx, proj_ctx=proj_ctx, test_batch=bat)
                if not case_flag and case.abort_when_fail:
                    # 用例失败后，返回具体失败的用例名字
                    errmsg = f"[{case.name}] 执行失败，有用例接口执行失败且要求用例执行中止"
                    logger.info(errmsg)
                    common.push_case_suite_run_log(suite, suite_log=suite_log, passed=False, err_msg=errmsg)
                    suit_flag = False
                    break
            if suit_flag:
                common.push_case_suite_run_log(suite, suite_log=suite_log, passed=True)
            logger.info(f'[{suite.name}] 执行结束')

        bat.status = TestBatch.STATUS_FINISHED
        bat.stat()
    except Exception as e:
        bat.status = TestBatch.STATUS_FAILED
        bat.error_msg = str(e)
        task_flag = False

    bat.finish_at = timezone.now()
    bat.save()
    logger.info(f"run_suites task finished.")
    dingtalk.send_text(repr(bat), tmpl=dingtalk.DINGTALK_TEXT_TMPL_API_TASK)
    return task_flag


@shared_task()
def run_suites_queue(suite_ids, user_id, bat_id):
    return run_suites(suite_ids, user_id, bat_id)


@shared_task()
def run_suites_periodic(suite_ids, user_id, periodic_task_id=None):
    logger = logging.getLogger('test_plt')
    suite = CaseSuite.objects.get(id=suite_ids[0])
    bat = TestBatch.objects.create(
        project=suite.project,
        created_by_id=user_id,
        start_at=timezone.now(),
        run_type=TestBatch.RUN_TYPE_PERIODIC,
        obj_type=TestBatch.OBJ_TYPE_SUITE,
        status=TestBatch.STATUS_PENDING,
        periodic_task_id=periodic_task_id
    )
    for sid in suite_ids:
        bat.suites.create(case_suite_id=sid, test_batch=bat)
    return run_suites(suite_ids, user_id, bat.id)
