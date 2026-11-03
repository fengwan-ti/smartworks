"""process 应用路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProcessEnumView, ProcessTemplateViewSet

router = DefaultRouter()
router.register('templates', ProcessTemplateViewSet, basename='process-template')

urlpatterns = [
    # 枚举先于 router，避免被 '' 兜底吞掉
    path('enums/', ProcessEnumView.as_view(), name='process-enums'),
    path('', include(router.urls)),
]
