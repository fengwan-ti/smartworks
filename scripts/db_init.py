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


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def sh(cmdline, cwd):
    print('    > ' + cmdline)
    try:
        proc = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/c', cmdline],
                              cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
        print('    ' + line)
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

    head('初始化完成')
    print('  管理员账号 admin    密码 admin123')
    print('  下一步：双击 3-启动系统.bat')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
