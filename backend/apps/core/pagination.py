"""统一分页。渲染器会把结果转成 {"count","page","page_size","results"}。"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200
