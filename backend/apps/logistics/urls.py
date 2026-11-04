"""物流应用路由。挂载前缀：/api/v1/logistics/"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.logistics import views

router = DefaultRouter()
router.register('road-nodes', views.RoadNodeViewSet, basename='road-node')
router.register('road-edges', views.RoadEdgeViewSet, basename='road-edge')

urlpatterns = [
    # 路网批量操作（放在 router 之前，避免 road-network 被当成 road-nodes 的 id）
    path('road-network/import/', views.RoadNetworkView.as_view(), name='road-network-import'),
    path('road-network/distance-matrix/', views.DistanceMatrixView.as_view(),
         name='road-network-distance-matrix'),
    path('road-network/health/', views.NetworkHealthView.as_view(),
         name='road-network-health'),
    path('road-network/shortest-path/', views.ShortestPathView.as_view(),
         name='road-network-shortest-path'),
    path('', include(router.urls)),
]
