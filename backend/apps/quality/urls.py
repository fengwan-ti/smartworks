"""quality 路由（负责人 C）。契约见 docs/api-contract.md 2.8。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('standards', views.StandardViewSet, basename='standard')
router.register('standard-items', views.StandardItemViewSet, basename='standard-item')
router.register('inspections', views.InspectionViewSet, basename='inspection')
router.register('measurements', views.MeasurementViewSet, basename='measurement')
router.register('defects', views.DefectRecordViewSet, basename='defect')
router.register('defect-codes', views.DefectCodeViewSet, basename='defect-code')

urlpatterns = [
    path('spc/', views.spc),
    path('vision/detect/', views.vision_detect),
    path('vision/recognize/', views.vision_recognize),
    path('', include(router.urls)),
]
