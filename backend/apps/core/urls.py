"""core 应用路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('users', views.UserViewSet, basename='user')
router.register('roles', views.RoleViewSet, basename='role')
router.register('menus', views.MenuViewSet, basename='menu')
router.register('dicts', views.DataDictViewSet, basename='dict')

urlpatterns = [
    # 认证
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('me/', views.MeView.as_view(), name='me'),
    # Day 1 验证接口
    path('_demo/success/', views.DemoSuccessView.as_view(), name='demo-success'),
    path('_demo/paginated/', views.DemoPaginatedView.as_view(), name='demo-paginated'),
    path('_demo/error/', views.DemoErrorView.as_view(), name='demo-error'),
    path('_demo/uncaught/', views.DemoUncaughtView.as_view(), name='demo-uncaught'),
    # 资源
    path('', include(router.urls)),
]
