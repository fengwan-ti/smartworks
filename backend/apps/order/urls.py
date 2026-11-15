"""order 应用路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DemandForecastViewSet, MpsViewSet, SalesOrderViewSet

router = DefaultRouter()
router.register('sales-orders', SalesOrderViewSet, basename='sales-order')
router.register('mps', MpsViewSet, basename='mps')
router.register('forecasts', DemandForecastViewSet, basename='forecast')

urlpatterns = [
    path('', include(router.urls)),
]
