"""成品仓路由（负责人 D）。被 apps/inventory/urls.py include。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventory import views_finished

router = DefaultRouter()
router.register('finished-inbounds', views_finished.FinishedInboundViewSet,
                basename='finished-inbound')
router.register('shipments', views_finished.ShipmentViewSet, basename='shipment')

urlpatterns = [
    path('stock-aging/', views_finished.StockAgingView.as_view(), name='stock-aging'),
    path('turnover/', views_finished.TurnoverView.as_view(), name='turnover'),
    path('', include(router.urls)),
]
