"""主数据路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('families', views.ProductFamilyViewSet, basename='product-family')
router.register('materials', views.MaterialViewSet, basename='material')
router.register('products', views.ProductViewSet, basename='product')
router.register('customers', views.CustomerViewSet, basename='customer')
router.register('suppliers', views.SupplierViewSet, basename='supplier')
router.register('workshops', views.WorkshopViewSet, basename='workshop')
router.register('workstations', views.WorkstationViewSet, basename='workstation')

urlpatterns = [
    path('', include(router.urls)),
]
