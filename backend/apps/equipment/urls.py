"""设备应用路由。挂载前缀：/api/v1/equipment/"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.equipment import views

router = DefaultRouter()
router.register('equipments', views.EquipmentViewSet, basename='equipment')
router.register('sensor-readings', views.SensorReadingViewSet, basename='sensor-reading')
router.register('alarms', views.AlarmViewSet, basename='alarm')
router.register('maintenance-orders', views.MaintenanceOrderViewSet,
                basename='maintenance-order')
router.register('inspection-plans', views.InspectionPlanViewSet,
                basename='inspection-plan')
router.register('inspection-records', views.InspectionRecordViewSet,
                basename='inspection-record')

urlpatterns = [
    # 工序类型字典（11 个值）
    path('step-types/', views.StepTypeView.as_view(), name='step-types'),
    # 监测页一屏拉全
    path('monitor/overview/', views.MonitorOverviewView.as_view(), name='monitor-overview'),
    path('', include(router.urls)),
]
