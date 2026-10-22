"""统一响应体渲染器。

约定（全项目唯一入口，其他人不得自行包装）：
  成功：{"code": 0, "message": "ok", "data": ...}
  分页：data 为 {"count": .., "page": .., "page_size": .., "results": [..]}
  失败：{"code": <错误码>, "message": "<中文说明>", "data": null}（由 exceptions.py 产生）
"""
from django.conf import settings
from rest_framework.renderers import JSONRenderer

_ENVELOPE_KEYS = {'code', 'message', 'data'}


def _default_page_size():
    return getattr(settings, 'REST_FRAMEWORK', {}).get('PAGE_SIZE', 20)


class UnifiedJSONRenderer(JSONRenderer):
    """把所有成功响应包装成统一结构；分页结果转成统一分页字段。"""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')
        request = renderer_context.get('request')
        status_code = getattr(response, 'status_code', 200)

        # 204 无内容：不包装。浏览器会丢弃 204 的响应体，包装反而造成结构不一致
        if status_code == 204:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and _ENVELOPE_KEYS.issubset(data.keys()):
            # 异常处理器已包装，直接透传
            payload = data
        elif status_code >= 400:
            payload = {
                'code': status_code * 100,
                'message': _guess_message(data) or '请求失败',
                'data': None,
            }
        else:
            payload = {'code': 0, 'message': 'ok', 'data': self._normalize(data, request)}

        return super().render(payload, accepted_media_type, renderer_context)

    def _normalize(self, data, request):
        """把 DRF 分页结构转成统一分页结构。"""
        if not isinstance(data, dict):
            return data
        if 'results' not in data or 'count' not in data:
            return data

        page, page_size = 1, _default_page_size()
        query = getattr(request, 'query_params', None)
        if query is not None:
            try:
                page = int(query.get('page', 1))
            except (TypeError, ValueError):
                page = 1
            try:
                page_size = int(query.get('page_size', page_size))
            except (TypeError, ValueError):
                page_size = _default_page_size()

        return {
            'count': data.get('count', 0),
            'page': page,
            'page_size': page_size,
            'results': data.get('results', []),
        }


def _guess_message(data):
    """从 DRF 的错误结构里抽出第一条可读信息。"""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        if 'detail' in data:
            return _guess_message(data['detail'])
        for key, value in data.items():
            msg = _guess_message(value)
            if msg:
                return f'{key}: {msg}'
        return ''
    if isinstance(data, (list, tuple)):
        for item in data:
            msg = _guess_message(item)
            if msg:
                return msg
    return ''
