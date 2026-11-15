"""planning 应用路由。"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EmployeeSkillViewSet, SchedulePlanViewSet, WorkOrderViewSet

router = DefaultRouter()
router.register('employee-skills', EmployeeSkillViewSet, basename='employee-skill')
router.register('work-orders', WorkOrderViewSet, basename='work-order')
router.register('schedule-plans', SchedulePlanViewSet, basename='schedule-plan')

urlpatterns = [path('', include(router.urls))]
