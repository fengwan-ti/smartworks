"""inventory 路由（负责人 C）。契约见 docs/api-contract.md 2.6。

注意：/inventory/stock/ 是台账（只读聚合），用 ViewSet(list) 挂出来。
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('warehouses', views.WarehouseViewSet, basename='warehouse')
router.register('locations', views.LocationViewSet, basename='location')
router.register('batches', views.BatchViewSet, basename='batch')
router.register('inbounds', views.InboundOrderViewSet, basename='inbound')
router.register('outbounds', views.OutboundOrderViewSet, basename='outbound')
router.register('stock-transactions', views.StockTransactionViewSet,
                basename='stock-transaction')
router.register('stock-takings', views.StockTakingViewSet, basename='stock-taking')
router.register('stock', views.StockLedgerViewSet, basename='stock')

urlpatterns = [
    # 显式放在 router 前面，避免被 detail 路由（pk 通配）截胡
    path('outbounds/from-work-order/',
         views.OutboundOrderViewSet.as_view({'post': 'from_work_order'})),
    path('', include(router.urls)),
]
