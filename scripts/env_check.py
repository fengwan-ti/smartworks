# -*- coding: utf-8 -*-
"""环境自检：检查 Python、Node.js、Git 是否可用。"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAR = '=' * 54


def head(text):
    print(BAR)
    print('  ' + text)
    print(BAR)


def exe_version(exe, args=('--version',)):
    """执行 exe 并返回第一行版本信息，失败返回 None。"""
    try:
        r = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=15)
        out = (r.stdout or '') + (r.returncode and (r.stderr or '') or '')
        line = out.strip().splitlines()
        return line[0] if line else None
    except Exception:
        return None


def main():
    head('SmartWorks 环境自检')
    print('  项目目录: ' + ROOT)
    print()

    ok = {}

    # ---- Python ----
    print('[1] Python')
    print('    版本: %d.%d.%d' % sys.version_info[:3])
    print('    位置: ' + sys.executable)
    ok['python'] = sys.version_info >= (3, 10)
    print('    判定: ' + ('合格' if ok['python'] else '版本过低，需要 3.10 以上'))
    print()

    # ---- Node.js / npm ----
    print('[2] Node.js / npm')
    node = shutil.which('node')
    npm = shutil.which('npm')
    if node:
        print('    node: ' + str(exe_version(node)))
        print('    路径: ' + node)
    else:
        print('    node: 没有安装')
    if npm:
        print('    npm : ' + str(exe_version(npm)))
    else:
        print('    npm : 没有安装')
    ok['node'] = bool(node and npm)
    print('    判定: ' + ('合格' if ok['node'] else '缺少 Node.js，请安装 LTS 版并重启电脑'))
    print()

    # ---- Git ----
    print('[3] Git')
    git = shutil.which('git')
    if git:
        print('    git : ' + str(exe_version(git)))
        print('    路径: ' + git)
    else:
        print('    git : 没有安装')
    ok['git'] = bool(git)
    print('    判定: ' + ('合格' if ok['git'] else '未安装。不影响装依赖，但今天要补装'))
    print()

    # ---- 项目文件 ----
    print('[4] 项目文件')
    for rel in ('backend/manage.py', 'backend/requirements.txt', 'frontend/package.json', '.env.example'):
        p = os.path.join(ROOT, rel)
        print(('    %-28s %s' % (rel, '存在' if os.path.exists(p) else '缺失')))
    print()

    # ---- 虚拟环境 ----
    print('[5] 虚拟环境 .venv')
    venv_py = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
    print('    ' + ('已创建' if os.path.exists(venv_py) else '尚未创建（跑 1-安装依赖 时会创建）'))
    print()

    head('结论')
    if ok['python'] and ok['node']:
        print('  Python 与 Node.js 都就绪，可以双击 1-安装依赖.bat')
    else:
        print('  还有必需项没装好，请按上面的提示补装，装完重启电脑再跑一次本自检')
    if not ok['git']:
        print('  注意：Git 还没装，请今天补装')
    print()
    return 0 if (ok['python'] and ok['node']) else 1


if __name__ == '__main__':
    sys.exit(main())
