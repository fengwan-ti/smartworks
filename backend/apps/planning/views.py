"""计划与人员接口（负责人 A）。

本文件当前提供：
  · 员工技能 CRUD
  · GET qualified/   按工序找合格人员（B 的排产派工校验用，对应契约 I-04）
  · GET matrix/      人员 × 工序 矩阵（前端画表用）
  · GET step-types/  工序类型下拉（唯一来源 apps/equipment/constants.py）
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BizError
from apps.core.pagination import StandardPagination
from apps.equipment.constants import StepType

from .models import LEVEL_ORDER, EmployeeSkill, Level
from .serializers import EmployeeSkillSerializer


class EmployeeSkillViewSet(viewsets.ModelViewSet):
    """员工技能。一个人对同一工序只有一条，重复提交会走唯一约束报错。"""

    queryset = EmployeeSkill.objects.select_related('user').all()
    serializer_class = EmployeeSkillSerializer
    pagination_class = StandardPagination
    search_fields = ('user__username', 'user__name', 'step_type')
    filterset_fields = ('user', 'step_type', 'level', 'is_active')
    ordering_fields = ('user_id', 'step_type', 'level', 'created_at')

    @action(detail=False, methods=['get'])
    def qualified(self, request):
        """按工序找合格人员。B 的排产派工校验调用这里。

        参数：
            step_type  必填，必须是 11 个工序类型之一
            min_level  可选，junior / mid / senior，表示"至少这个等级"
            certified  可选，传 1 表示只要持证的

        返回：[{user_id, username, name, level, is_certified}]
        """
        step_type = request.query_params.get('step_type')
        if not step_type:
            raise BizError(11001, 'step_type 必填')
        if step_type not in StepType.values:
            raise BizError(11003, '工序类型不在数据字典内：%s' % step_type)

        qs = self.get_queryset().filter(
            step_type=step_type, is_active=True, user__is_active=True)

        min_level = request.query_params.get('min_level')
        if min_level:
            if min_level not in Level.values:
                raise BizError(11003, '技能等级不在取值范围内：%s' % min_level)
            allowed = [lv for lv, order in LEVEL_ORDER.items()
                       if order >= LEVEL_ORDER[Level(min_level)]]
            qs = qs.filter(level__in=allowed)

        if request.query_params.get('certified') in ('1', 'true', 'True'):
            qs = qs.filter(is_certified=True)

        data = [{
            'user_id': s.user_id,
            'username': s.user.username,
            'name': s.user.display_name,
            'step_type': s.step_type,
            'level': s.level,
            'level_label': Level(s.level).label,
            'is_certified': s.is_certified,
        } for s in qs]
        return Response(data)

    @action(detail=False, methods=['get'])
    def matrix(self, request):
        """人员 × 工序 矩阵。

        返回：
            {
              "step_types": [{"value": "cutting", "label": "下料"}, ...],
              "users": [{"user_id": 1, "username": "admin", "name": "管理员",
                         "skills": {"cutting": "senior", ...}}]
            }

        为什么后端出这个结构：前端自己拼要做 人数 × 工序 次判断，
        而且等级排序逻辑要重写一遍，容易和 qualified/ 的口径不一致。
        """
        step_types = [{'value': v, 'label': StepType(v).label} for v in StepType.values]

        skills = (EmployeeSkill.objects
                  .select_related('user')
                  .filter(is_active=True, user__is_active=True)
                  .order_by('user_id', 'step_type'))

        users = {}
        for s in skills:
            u = users.setdefault(s.user_id, {
                'user_id': s.user_id,
                'username': s.user.username,
                'name': s.user.display_name,
                'skills': {},
            })
            u['skills'][s.step_type] = s.level

        return Response({'step_types': step_types, 'users': list(users.values())})

    @action(detail=False, methods=['get'], url_path='step-types')
    def step_types(self, request):
        """工序类型下拉。全项目唯一来源是 apps/equipment/constants.py。"""
        return Response([{'value': v, 'label': StepType(v).label} for v in StepType.values])
