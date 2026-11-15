"""总路由。每个应用自己的路由放在 apps/<app>/urls.py。"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    # 接口文档
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # 业务接口
    path('api/v1/core/', include('apps.core.urls')),
    path('api/v1/masterdata/', include('apps.masterdata.urls')),
    # D（设备与物流调度）：设备台账与告警维修点检、路网与距离矩阵、AGV 调度、成品仓
    path('api/v1/equipment/', include('apps.equipment.urls')),
    path('api/v1/logistics/', include('apps.logistics.urls')),
    path('api/v1/planning/', include('apps.planning.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    # C（执行与质量）：inventory（原料仓 + D 的成品仓合并挂载）/ production / quality
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/production/', include('apps.production.urls')),
    path('api/v1/quality/', include('apps.quality.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
