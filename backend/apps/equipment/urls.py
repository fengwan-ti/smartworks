"""设备应用路由。挂载前缀：/api/v1/equipment/"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.equipment import views

router = DefaultRouter()
router.register('equipments', views.EquipmentViewSet, basename='equipment')

urlpatterns = [
    # 工序类型字典（11 个值）
    path('step-types/', views.StepTypeView.as_view(), name='step-types'),
    path('', include(router.urls)),
]
