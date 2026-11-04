"""production 路由（负责人 C）。契约见 docs/api-contract.md 2.7。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('reports', views.WorkReportViewSet, basename='work-report')
router.register('anomalies', views.AnomalyViewSet, basename='anomaly')
router.register('traceability/nodes', views.TraceRecordViewSet,
                basename='trace-node')

urlpatterns = [
    # 契约 88/89/90：工单级动作（work-orders 归 B 的路由，这里只挂动作）
    path('work-orders/<int:work_order_id>/confirm-material/',
         views.work_order_confirm_material),
    path('work-orders/<int:work_order_id>/operations/<int:seq>/start/',
         views.operation_start),
    path('work-orders/<int:work_order_id>/operations/<int:seq>/complete/',
         views.operation_complete),
    # 契约 91/94/95
    path('wip/', views.wip),
    path('traceability/reverse/', views.traceability_reverse),
    path('traceability/forward/', views.traceability_forward),
    path('', include(router.urls)),
]
