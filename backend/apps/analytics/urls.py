"""看板路由。挂载前缀：/api/v1/analytics/"""
from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='analytics-dashboard'),
]
