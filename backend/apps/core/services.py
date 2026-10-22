"""core 应用的业务逻辑。视图只做参数校验与调用，逻辑都在这里。"""


def build_menu_tree(user):
    """根据用户角色构建菜单树。

    返回：[{id, code, name, path, component, icon, children: [...]}]
    只返回 dir 与 menu 类型；button 类型单独汇总到权限码列表。
    """
    if not user or not user.is_authenticated:
        return [], []

    if user.is_superuser:
        from .models import Menu
        menus = list(Menu.objects.filter(is_active=True))
    else:
        from .models import Menu
        menus = list(
            Menu.objects.filter(is_active=True, roles__users=user).distinct()
        )

    permission_codes = sorted({m.permission_code for m in menus if m.permission_code})

    visible = [m for m in menus if m.menu_type in ('dir', 'menu')]
    by_parent = {}
    for m in visible:
        by_parent.setdefault(m.parent_id, []).append(m)

    def build(parent_id):
        nodes = []
        for m in sorted(by_parent.get(parent_id, []), key=lambda x: (x.sort, x.code)):
            children = build(m.id)
            nodes.append({
                'id': m.id,
                'code': m.code,
                'name': m.name,
                'path': m.path,
                'component': m.component,
                'icon': m.icon,
                'children': children,
            })
        return nodes

    return build(None), permission_codes


def build_user_payload(user):
    """组装登录与 /me 共用的返回结构。"""
    menus, permission_codes = build_menu_tree(user)
    return {
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.display_name,
            'employee_no': user.employee_no or '',
            'department': user.department.name if user.department else '',
            'position': user.position.name if user.position else '',
            'is_superuser': user.is_superuser,
            'roles': [{'code': r.code, 'name': r.name} for r in user.roles.all()],
        },
        'menus': menus,
        'permissions': permission_codes,
    }


def write_operation_log(user, action, target_model='', target_id='', detail=None, ip=''):
    """写操作日志。失败不影响主流程。"""
    from .models import OperationLog

    try:
        OperationLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action=action,
            target_model=target_model,
            target_id=str(target_id or ''),
            detail=detail or {},
            ip=ip or '',
        )
    except Exception:  # noqa: BLE001 - 日志写入失败不应影响业务
        pass
