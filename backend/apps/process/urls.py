"""process 应用路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangeoverViewSet,
    ProcessBomViewSet,
    ProcessEnumView,
    ProcessRouteViewSet,
    ProcessTemplateViewSet,
)

router = DefaultRouter()
router.register('templates', ProcessTemplateViewSet, basename='process-template')
router.register('routes', ProcessRouteViewSet, basename='process-route')
router.register('boms', ProcessBomViewSet, basename='process-bom')
router.register('changeovers', ChangeoverViewSet, basename='process-changeover')

urlpatterns = [
    path('enums/', ProcessEnumView.as_view(), name='process-enums'),
    path('', include(router.urls)),
]
