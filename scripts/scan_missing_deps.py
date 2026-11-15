# -*- coding: utf-8 -*-
"""扫描后端所有第三方 import，找出 venv 里没装的包。

为什么做这个：
  合并四人的代码后，requirements.txt 只记录了最早的依赖。
  C 的视觉要 opencv、B 的预测要 statsmodels —— 这类缺失不是"报错"，而是
  "功能静默不可用"（接口返回 errors 数组，页面空白），答辩现场才发现。
  所以一次性扫干净。
"""
import ast
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

BACKEND = r'C:\Users\Lenovo\Desktop\制造系统软件开发\SmartWorks\backend'

STDLIB_HINT = set(sys.stdlib_module_names)
LOCAL = {'apps', 'algorithms', 'config', 'manage', 'conftest'}

# 包名 → pip 安装名 不一致的情况
PIP_NAME = {
    'cv2': 'opencv-python-headless',
    'PIL': 'Pillow',
    'sklearn': 'scikit-learn',
    'yaml': 'PyYAML',
    'dateutil': 'python-dateutil',
    'dotenv': 'python-dotenv',
    'django_filters': 'django-filter',
    'rest_framework': 'djangorestframework',
    'drf_spectacular': 'drf-spectacular',
    'simple_history': 'django-simple-history',
    'import_export': 'django-import-export',
}

import importlib.util


def installed(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def main():
    mods = {}
    for root, dirs, fs in os.walk(BACKEND):
        dirs[:] = [d for d in dirs
                   if d not in ('migrations', '__pycache__', 'node_modules', '.venv')]
        for f in fs:
            if not f.endswith('.py'):
                continue
            p = os.path.join(root, f)
            try:
                tree = ast.parse(io.open(p, encoding='utf-8').read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split('.')[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split('.')[0]]
                for n in names:
                    if n in STDLIB_HINT or n in LOCAL or not n:
                        continue
                    mods.setdefault(n, set()).add(p.replace(BACKEND + os.sep, ''))

    missing = []
    present = []
    for mod, files in sorted(mods.items()):
        if installed(mod):
            present.append((mod, len(files)))
        else:
            missing.append((mod, sorted(files)))

    print('  后端引用的第三方顶层模块：%d 个' % len(mods))
    print()
    print('  [已安装] %d 个：%s' % (len(present), ', '.join(m for m, _ in present)))
    print()
    if missing:
        print('  [缺失] %d 个：' % len(missing))
        for mod, files in missing:
            pip = PIP_NAME.get(mod, mod)
            print('    %-14s -> pip 包名 %-26s 被 %d 个文件引用' % (mod, pip, len(files)))
            for f in files[:3]:
                print('         ' + f)
            if len(files) > 3:
                print('         ... 还有 %d 个' % (len(files) - 3))
        print()
        print('  需要安装的命令：')
        print('    ..\\.venv\\Scripts\\python.exe -m pip install %s'
              % ' '.join(PIP_NAME.get(m, m) for m, _ in missing))
    else:
        print('  [缺失] 无')


if __name__ == '__main__':
    main()
