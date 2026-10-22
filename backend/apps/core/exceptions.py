"""统一异常处理。

用法：
  1. 业务规则冲突时在 services.py 里 raise BizError(12101, '领料数量超过工单数量')
  2. 其余异常由 unified_exception_handler 统一转换成统一响应体
"""
import logging

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class BizError(Exception):
    """业务规则异常。号段必须用自己那一段（见 docs/api-contract.md）。"""

    def __init__(self, code, message, status_code=status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _flatten(detail, prefix=''):
    """把 DRF 的 detail（可能是 dict/list/str 嵌套）压成一句中文。"""
    if detail is None:
        return ''
    if isinstance(detail, str):
        return f'{prefix}{detail}' if prefix else detail
    if isinstance(detail, (list, tuple)):
        for item in detail:
            text = _flatten(item, prefix)
            if text:
                return text
        return ''
    if isinstance(detail, dict):
        for key, value in detail.items():
            if key == 'detail':
                text = _flatten(value)
                if text:
                    return text
            text = _flatten(value, f'{key}: ')
            if text:
                return text
        return ''
    return str(detail)


def _code_of(exc, response):
    if isinstance(exc, ValidationError):
        return 10001
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return 10201
    if isinstance(exc, PermissionDenied):
        return 10202
    if isinstance(exc, NotFound):
        return 10301
    if isinstance(exc, MethodNotAllowed):
        return 10005
    if isinstance(exc, Throttled):
        return 10006
    if isinstance(exc, APIException):
        return response.status_code * 100
    return 10900


def unified_exception_handler(exc, context):
    # 业务异常
    if isinstance(exc, BizError):
        return Response(
            {'code': exc.code, 'message': exc.message, 'data': None},
            status=exc.status_code,
        )

    response = exception_handler(exc, context)

    # 未捕获的异常：记日志，返回统一 500
    if response is None:
        logger.exception('未捕获异常: %s', exc)
        return Response(
            {'code': 10900, 'message': '服务器内部错误', 'data': None},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response.data = {
        'code': _code_of(exc, response),
        'message': _flatten(response.data) or '请求失败',
        'data': None,
    }
    return response
