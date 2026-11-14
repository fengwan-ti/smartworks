"""计划应用路由。挂载前缀：/api/v1/planning/"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('employee-skills', views.EmployeeSkillViewSet, basename='employee-skill')

urlpatterns = [
    path('', include(router.urls)),
]
