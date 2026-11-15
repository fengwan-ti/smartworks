"""乐观锁（并发修改保护）。

解决什么问题：
  计划和 A 同时打开工单 WO-001，两人看到的都是「planned」。
  计划员先点「下达」，A 后点「取消」。如果没有保护，A 的取消会把
  计划员的下达**悄悄覆盖**掉 —— 谁也不知道刚才发生了什么。
  这叫「后写覆盖」（last write wins），是多用户系统的经典事故。

怎么解决（乐观锁，不加表字段、不加迁移）：
  前端提交时带上「我看到这条记录时它的 updated_at」，
  服务端比对：和库里的不一致就说明有人改过了，返回 409 让前端提示刷新。
  用乐观锁而不是悲观锁（SELECT FOR UPDATE）的原因：
    车间业务冲突概率很低，锁表会让并发变差，乐观锁零成本且不影响正常流程。

向后兼容：
  不传 expected_updated_at 就完全跳过校验。
  这样四人已有的前端页面、测试用例、脚本都不用改一行。
"""
from datetime import datetime, timezone as dt_timezone

from rest_framework import status

from .exceptions import BizError


class StaleObjectError(BizError):
    """409 冲突：记录在你读取之后被别人改过。

    注意：必须通过 super().__init__ 的 status_code 参数传 409。
    只在类上写 status_code = 409 是**无效**的 —— BizError.__init__ 的默认参数
    会把实例属性覆盖回 400，实测就踩过这个坑（返回 10409 但 HTTP 是 400）。
    """

    def __init__(self, message=None):
        super().__init__(10409, message or '记录已被他人修改，请刷新后重试',
                         status_code=status.HTTP_409_CONFLICT)


def _parse(value):
    """把前端传来的时间字符串转成带时区的 datetime。

    容忍三种写法：
      2026-11-15T16:56:19.123456Z      （DRF 默认输出）
      2026-11-15T16:56:19.123456+08:00
      2026-11-15 16:56:19
    """
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace(' ', 'T')
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        # 关键：DRF 配了 DEFAULT_PARSER 的 DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'，
        # 输出的时间**不带时区**。若按 UTC 解释，和库里 +08:00 的值会差 8 小时，
        # 导致每次正常提交都被判成冲突（实测踩过）。
        # 正确做法：按 Django 当前时区（Asia/Shanghai）补上时区。
        from django.utils import timezone as dj_tz
        dt = dj_tz.make_aware(dt, dj_tz.get_current_timezone())
    return dt


def ensure_fresh(instance, request, field='expected_updated_at'):
    """校验记录是否被别人改过。不一致抛 StaleObjectError。

    参数：
        instance  数据库里的对象
        request   DRF 的 request（从 data 里取期望版本）
        field     前端传的字段名，默认 expected_updated_at

    返回：
        True  校验通过或未开启校验
        异常  记录已被修改
    """
    raw = None
    try:
        raw = request.data.get(field)
    except Exception:                                              # noqa: BLE001
        raw = None
    if not raw:
        return True                                                # 未传 = 不校验

    if not hasattr(instance, 'updated_at'):
        return True                                                # 该模型没有版本字段

    expected = _parse(raw)
    if expected is None:
        return True                                                # 传了但解析不了，放行

    actual = instance.updated_at
    if actual is None:
        return True
    if actual.tzinfo is None:
        from django.utils import timezone as dj_tz
        actual = dj_tz.make_aware(actual, dj_tz.get_current_timezone())

    # 按「秒」比较，不能按毫秒。
    # 原因：settings 里 DEFAULT_PARSER 的 DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'，
    # 序列化时**把微秒丢掉了**。库里是 09:03:39.447714，接口返回 17:03:39（本地时区）。
    # 前端把 17:03:39 传回来，与库里的值差 0.44 秒 —— 若按 1 毫秒容差，
    # 每一次正常提交都会被判成冲突。实测踩过，所以容差定为 1 秒。
    if abs((actual - expected).total_seconds()) > 1.0:
        from .models import User                                   # noqa: F401
        who = ''
        updater = getattr(instance, 'updated_by', None)
        if updater is not None:
            who = '（最后由 %s 修改）' % getattr(updater, 'display_name', updater)
        raise StaleObjectError(
            '记录已被他人修改%s，请刷新后再操作' % who)
    return True
