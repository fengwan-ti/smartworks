"""主数据接口。

统一约定：
  · 列表支持 page / page_size / ordering / search + 各自筛选项
  · 所有响应体由 core.renderers 统一包装，这里只 return Response
  · 每个资源额外提供 options/ 动作，供其他模块做下拉选择
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.pagination import StandardPagination
from apps.core.permissions import ModulePermission

from .models import (
    Customer,
    Material,
    Product,
    ProductFamily,
    Supplier,
    Workshop,
    Workstation,
)
from .serializers import (
    CustomerSerializer,
    MaterialSerializer,
    ProductDetailSerializer,
    ProductFamilySerializer,
    ProductListSerializer,
    SupplierSerializer,
    WorkshopSerializer,
    WorkstationSerializer,
)


class BaseMasterDataViewSet(viewsets.ModelViewSet):
    """主数据通用基类：统一分页、搜索、排序、权限与 options 下拉。

    权限口径（第一代刻意做粗）：
      一个资源一个权限码，读与写共用同一个码。
      原因：细到 read/write 两码会让 4 个人维护 30 多个码，漏配就出现"莫名 403"，
      排查成本远高于收益。需要细分时把 required_perm 改成 dict{'GET': ...} 即可，
      ModulePermission 已经支持按方法取值。
    """

    pagination_class = StandardPagination
    permission_classes = (IsAuthenticated, ModulePermission)
    option_fields = ('id', 'code', 'name')

    def get_serializer_class(self):
        if getattr(self, 'detail_serializer_class', None) and self.action in ('retrieve',):
            return self.detail_serializer_class
        return self.serializer_class

    @action(detail=False, methods=['get'])
    def options(self, request):
        """下拉选项：只返回 id / code / name，最多 500 条。"""
        qs = self.filter_queryset(self.get_queryset())[:500]
        data = [{k: getattr(obj, k) for k in self.option_fields} for obj in qs]
        return Response(data)


class ProductFamilyViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:family'
    queryset = ProductFamily.objects.all()
    serializer_class = ProductFamilySerializer
    search_fields = ('code', 'name')
    filterset_fields = ('is_active',)


class MaterialViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:material'
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    search_fields = ('code', 'name', 'spec')
    filterset_fields = ('is_active', 'category')


class ProductViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:product'
    queryset = Product.objects.select_related('family', 'material').all()
    serializer_class = ProductListSerializer
    detail_serializer_class = ProductDetailSerializer
    search_fields = ('code', 'name', 'drawing_no', 'spec')
    filterset_fields = ('is_active', 'family', 'material')
    ordering_fields = ('code', 'name', 'std_cost', 'created_at')


class CustomerViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:customer'
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    search_fields = ('code', 'name', 'contact')
    filterset_fields = ('is_active',)


class SupplierViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:supplier'
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ('code', 'name', 'contact')
    filterset_fields = ('is_active',)


class WorkshopViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:workshop'
    queryset = Workshop.objects.all()
    serializer_class = WorkshopSerializer
    search_fields = ('code', 'name')
    filterset_fields = ('is_active',)


class WorkstationViewSet(BaseMasterDataViewSet):
    required_perm = 'masterdata:workstation'
    queryset = Workstation.objects.select_related('workshop').all()
    serializer_class = WorkstationSerializer
    search_fields = ('code', 'name', 'agv_load_point')
    filterset_fields = ('is_active', 'workshop')
