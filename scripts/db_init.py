# -*- coding: utf-8 -*-
"""生成迁移文件 + 建数据库表 + 创建管理员账号。由 2-初始化数据库.bat 调用。

三个步骤缺一不可：
  1) makemigrations  读 models.py，生成"怎么改表"的迁移文件
  2) migrate         执行迁移文件，真正在数据库里建表
  3) init_core       灌入初始数据（13 岗位、10 菜单、14 条字典、admin 账号）

踩坑记录：最初漏了第 1 步，导致 migrate 报
  "ValueError: Dependency on app with no migrations: core"
原因是 core 应用只有 migrations/__init__.py 而没有迁移文件，
而 django.contrib.admin 等内置应用依赖 AUTH_USER_MODEL（core.User），
于是迁移图建不起来。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY_REL = os.path.join('..', '.venv', 'Scripts', 'python.exe')
BACKEND = os.path.join(ROOT, 'backend')
BAR = '=' * 54

# 中文控制台是 GBK 编码，子进程输出里可能有它编不出的字符（如 U+FFFD）。
# 不兜底的话 print 会抛 UnicodeEncodeError，整个初始化脚本中断。
try:
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:                                             # noqa: BLE001
    pass


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def sh(cmdline, cwd):
    print('    > ' + cmdline)
    try:
        # 为什么用 shell=True，而不是 [cmd.exe, '/c', cmdline]：
        #   后者在 Windows 上会被 Python 的 list2cmdline 把内层引号转义，
        #   cmd 收到的是 \"...python.exe\"，报「不是内部或外部命令」。
        #   实测：双击 2-初始化数据库.bat 从第 1 步就失败，就是这个原因。
        proc = subprocess.run(cmdline, cwd=cwd, shell=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:                                    # noqa: BLE001
        print('    [无法执行] %r' % e)
        return 1
    raw = proc.stdout or b''
    for enc in ('utf-8', 'gbk'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode('utf-8', errors='replace')
    for line in text.rstrip().splitlines():
        # 再过一遍 GBK：把控制台编不出的字符换成 ?，避免 print 崩掉
        print('    ' + line.encode('gbk', errors='replace').decode('gbk', errors='replace'))
    return proc.returncode


def main():
    head('SmartWorks 初始化数据库')

    if not os.path.exists(os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')):
        print()
        print('  [错误] 没找到虚拟环境，请先双击 1-安装依赖.bat')
        print()
        return 1
    if not os.path.isdir(BACKEND):
        print()
        print('  [错误] 找不到 backend 目录')
        print()
        return 1

    # ---------- 1 ----------
    head('第 1 步 共 3 步：生成迁移文件（读 models.py 生成"怎么改表"）')
    rc = sh('"%s" manage.py makemigrations' % VENV_PY_REL, cwd=BACKEND)
    if rc != 0:
        print()
        print('  [失败] 生成迁移文件失败，请把上面的报错截图发到群里')
        print()
        return 1
    print('  完成')

    # ---------- 2 ----------
    head('第 2 步：在数据库里建表')
    rc = sh('"%s" manage.py migrate' % VENV_PY_REL, cwd=BACKEND)
    if rc != 0:
        print()
        print('  [失败] 建表失败，请把上面的报错截图发到群里')
        print()
        return 1
    print('  完成')

    # ---------- 3 ----------
    head('第 3 步：创建管理员账号与基础数据')
    rc = sh('"%s" manage.py init_core' % VENV_PY_REL, cwd=BACKEND)
    if rc != 0:
        print()
        print('  [失败] 初始化数据失败，请把上面的报错截图发到群里')
        print()
        return 1
    print('  完成：39 条菜单 / 35 条字典 / 3 个部门 / 13 个岗位 / admin 账号')

    # ---------- 4 演示数据 ----------
    #
    # 这一段是 2026-11-15 补的。原来只有第 3 步，别人拉下来能登录但页面全空，
    # 会误以为装失败。下面每个命令都是幂等的，重复跑不会插重复数据。
    seed_steps = [
        ('init_demo', [], '主数据 + 演示账号（demo / planner / 3 名操作工）'),
        ('seed_equipments', ['--create-workshop'], '8 台设备台账并绑定工位'),
        ('seed_d_workstations', ['--cleanup-placeholders'], '工位与路网节点对齐（ST-CUT-01 挂 N006）'),
        ('import_road_network', [], '路网 29 节点 / 48 边'),
        ('seed_agvs', [], '3 台 AGV'),
        ('seed_process', [], '11 条工序模板'),
        ('seed_routes', [], '6 条工艺路线 / 30 道工序 / 6 个 BOM'),
        ('seed_orders', [], '6 条销售订单（4 条已确认）'),
        ('import_sensor_csv', [], '设备时序（12096 行 -> 48384 条读数）'),
        ('simulate_sensors', ['--minutes', '120', '--step', '5'], '补齐 CSV 里没有的 5 台设备'),
        ('check_alarms', [], '扫阈值生成告警，critical 自动开维修单'),
    ]

    head('第 4 步：灌入演示数据（共 %d 项）' % len(seed_steps))
    failed = []
    for name, args, desc in seed_steps:
        cmd = '"%s" manage.py %s' % (VENV_PY_REL, name)
        if args:
            cmd += ' ' + ' '.join(args)
        print()
        print('  [%s] %s' % (name, desc))
        rc = sh(cmd, cwd=BACKEND)
        if rc != 0:
            # 单个命令失败不终止：可能是某人的分支还没提供这条命令
            print('       [跳过] 该步骤没有成功，继续下一步')
            failed.append(name)

    # ---------- 5 业务数据要用接口跑出来 ----------
    head('第 5 步：生成业务数据（MPS、排产、预测、AGV）')
    biz = os.path.join(ROOT, 'scripts', 'one_click_business.py')
    if os.path.exists(biz):
        rc = sh('"%s" "%s"' % (VENV_PY_REL, biz), cwd=os.path.join(ROOT, 'scripts'))
        if rc != 0:
            print('       [跳过] 业务数据生成未全部成功，可稍后在页面上手动点')
            failed.append('业务数据')
    else:
        print('       [跳过] 找不到 scripts/one_click_business.py')
        failed.append('业务数据')

    head('初始化完成')
    print('  管理员账号   admin    密码 admin123')
    print('  演示账号     demo     密码 demo123       （超管，等同 admin）')
    print('  对照账号     planner  密码 planner123    （只有主数据 + 计划管理，用于演示权限）')
    print('  操作工       op_zhang / op_li / op_wang  密码 op123456')
    if failed:
        print()
        print('  [注意] 以下步骤没成功，不影响启动，但对应页面会是空的：')
        for f in failed:
            print('         - ' + f)
        print('         可对照 docs/demo-data-rebuild.md 单独重跑')
    print()
    print('  下一步：双击 3-启动系统.bat')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
