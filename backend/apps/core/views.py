"""core 应用的接口。视图只做校验与调用，业务逻辑在 services.py。"""
from django.contrib.auth import authenticate
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import BizError
from .filters import UserFilter
from .models import DataDict, Menu, Role, User
from .pagination import StandardPagination
from .serializers import (
    DataDictSerializer,
    LoginSerializer,
    MenuSerializer,
    RoleSerializer,
    UserSerializer,
)
from .services import build_user_payload, write_operation_log


class LoginView(APIView):
    """登录：用户名密码换 token。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            raise BizError(10101, '用户名或密码错误', status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            raise BizError(10102, '账号已停用，请联系管理员', status.HTTP_403_FORBIDDEN)

        token, _ = Token.objects.get_or_create(user=user)
        payload = build_user_payload(user)
        payload['token'] = token.key
        write_operation_log(user, 'login', 'core.User', user.id, ip=_client_ip(request))
        return Response(payload)


class LogoutView(APIView):
    """登出：销毁 token。"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'message': '已退出登录'})


class MeView(APIView):
    """当前用户信息 + 菜单树 + 权限码。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_user_payload(request.user))


class UserViewSet(viewsets.ModelViewSet):
    """用户管理。Day 1 提供基础 CRUD，权限细化在 W6。"""

    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    pagination_class = StandardPagination
    filterset_class = UserFilter
    search_fields = ('username', 'name', 'employee_no')
    ordering_fields = ('id', 'username', 'date_joined')


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by('code')
    serializer_class = RoleSerializer
    pagination_class = StandardPagination


class MenuViewSet(viewsets.ModelViewSet):
    queryset = Menu.objects.all().order_by('sort', 'code')
    serializer_class = MenuSerializer
    pagination_class = StandardPagination


class DataDictViewSet(viewsets.ReadOnlyModelViewSet):
    """数据字典：前端下拉选项来源。"""

    serializer_class = DataDictSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = DataDict.objects.filter(is_active=True).order_by('dict_type', 'sort')
        dict_type = self.request.query_params.get('dict_type')
        if dict_type:
            qs = qs.filter(dict_type=dict_type)
        return qs


# ---------------------------------------------------------------- Day 1 验证用
class DemoSuccessView(APIView):
    """验证成功响应：应返回 {"code":0,"message":"ok","data":{...}}"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'message': '统一响应体已生效', 'today': request.query_params.get('date', '')})


class DemoPaginatedView(APIView):
    """验证分页响应：应返回 data 内含 count/page/page_size/results。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        items = [{'id': i, 'name': f'样例行 {i}'} for i in range(1, 44)]
        paginator = StandardPagination()
        page = paginator.paginate_queryset(items, request, view=self)
        return paginator.get_paginated_response(page)


class DemoErrorView(APIView):
    """验证异常响应：应返回 HTTP 400 与统一错误结构。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        raise BizError(10001, '工单数量必须大于 0')


class DemoUncaughtView(APIView):
    """验证未捕获异常：应返回 HTTP 500 与 10900。"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        raise RuntimeError('这是一个故意抛出的未捕获异常')


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
