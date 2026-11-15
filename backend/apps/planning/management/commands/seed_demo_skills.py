# -*- coding: utf-8 -*-
"""演示用操作工技能种子（B 的派工依赖 A 的 EmployeeSkill，但 A 的 init_demo 暂未种）。

幂等：按用户名 update_or_create；技能按 11 个工序类型补齐。
演示机跑一次即可：
    python manage.py seed_demo_skills
"""
from django.core.management.base import BaseCommand

from apps.core.models import User
from apps.equipment.constants import StepType
from apps.planning.models import EmployeeSkill, Level

WORKERS = [
    ('worker1', '张师傅', Level.SENIOR, True),
    ('worker2', '李师傅', Level.MID, True),
    ('worker3', '王师傅', Level.JUNIOR, False),
]


class Command(BaseCommand):
    help = '生成演示操作工（张/李/王）并给 11 个工序技能，供派工演示'

    def handle(self, *args, **options):
        created_users = 0
        created_skills = 0
        for username, name, level, certified in WORKERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'name': name, 'is_active': True},
            )
            if created:
                user.set_password('worker123')
                user.save()
                created_users += 1
            else:
                user.name = name
                user.save(update_fields=['name'])
            for step_type in StepType.values:
                _, s_created = EmployeeSkill.objects.update_or_create(
                    user=user, step_type=step_type,
                    defaults={'level': level, 'is_certified': certified,
                              'is_active': True},
                )
                if s_created:
                    created_skills += 1
        self.stdout.write(self.style.SUCCESS(
            f'演示操作工：新增用户 {created_users} 个，技能 {created_skills} 条'
            f'（共 {EmployeeSkill.objects.count()} 条）'))
