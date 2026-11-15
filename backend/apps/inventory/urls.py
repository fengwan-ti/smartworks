"""库存应用总路由。挂载前缀：/api/v1/inventory/

[2026-11-15 合并说明] dw3 与 feature/c-apps 两边都改了这个文件，按"各管一半"的方式合：
   - D：成品仓（成品入库、发货、库龄、周转）-> 走 urls_finished.py
   - C：原料仓（仓库、库位、批次、采购入库领料、台账、盘点）-> 走本文件里的 router
两边路径字面量不重叠（D 是 finished-inbounds / shipments / stock-aging / turnover，
C 是 warehouses / locations / batches / inbounds / outbounds / stock-*），
所以按 include 顺序叠加即可，不要再整文件覆盖。
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
    # D：成品仓（先挂；命中不到会自然落到下面的 C 路由）
    path('', include('apps.inventory.urls_finished')),
    # C：显式放在 router 前面，避免被 detail 路由（pk 通配）截胡
    path('outbounds/from-work-order/',
         views.OutboundOrderViewSet.as_view({'post': 'from_work_order'})),
    path('', include(router.urls)),
]
