# -*- coding: utf-8 -*-
"""安装 SmartWorks 依赖：逐个包安装 + 心跳显示 + 超时保护 + 截获输出。

三次踩坑与对应修复：
  1) 让 pip 输出直接继承控制台 -> 输出被缓冲，屏幕一片空白，看起来像卡死
     修复：用 stdout=PIPE 把输出截获，由本脚本负责打印
  2) 用相对路径 ".venv\\Scripts\\python.exe" 启动 -> 父进程当前目录是 scripts，
     相对路径解析到 scripts\\.venv，不存在，CreateProcess 直接失败（0.1 秒报错且无输出）
     修复：改用绝对路径
  3) 一个包下载要好几分钟，期间无输出仍像卡死
     修复：每 5 秒打印一个点表示仍在工作，并给每个包设 4 分钟超时上限
"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.join(ROOT, '.venv')
VENV_PY = os.path.join(VENV, 'Scripts', 'python.exe')
MIRROR = 'https://pypi.tuna.tsinghua.edu.cn/simple'
NPM_REGISTRY = 'https://registry.npmmirror.com'
COMSPEC = os.environ.get('COMSPEC', r'C:\Windows\System32\cmd.exe')
BAR = '=' * 60
PKG_TIMEOUT = 240          # 单个包最长等待 4 分钟

PACKAGES = [
    ('Django', 'Web 框架'),
    ('djangorestframework', 'REST 接口'),
    ('django-cors-headers', '跨域'),
    ('drf-spectacular', '接口文档'),
    ('django-filter', '筛选'),
    ('django-simple-history', '变更历史'),
    ('django-import-export', 'Excel 导入导出'),
    ('python-dotenv', '读取 .env'),
    ('Pillow', '图像处理'),
    ('requests', 'HTTP 请求'),
    ('pytest', '测试'),
    ('pytest-django', 'Django 测试'),
    ('ruff', '代码规范'),
]


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def child_env():
    """让子进程（pip、npm 里的 Node 无关，pip 是 Python）统一用 UTF-8 输出，
    否则输出被重定向到管道时 Python 会按系统 GBK 写，中文路径会变成乱码。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    return env


def decode_out(raw):
    """按 UTF-8 解码，失败再退回 GBK，最后兜底替换。"""
    if not raw:
        return ''
    for enc in ('utf-8', 'gbk'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def run(argv, cwd=None, tail=None, timeout=None, heartbeat=False):
    """执行命令，返回 (返回码, 输出文本)。heartbeat=True 时每 5 秒打一个点。"""
    try:
        proc = subprocess.Popen(argv, cwd=cwd or ROOT, env=child_env(),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except FileNotFoundError as e:
        return 127, '[无法启动进程] %s' % e
    except Exception as e:                                     # noqa: BLE001
        return 1, '[执行异常] %r' % e

    t0 = time.time()
    killed = False
    while True:
        rc = proc.poll()
        if rc is not None:
            break
        if timeout and (time.time() - t0) > timeout:
            proc.kill()
            killed = True
            break
        time.sleep(5)
        if heartbeat:
            print('         .', flush=True)

    out = b''
    try:
        out = proc.stdout.read() or b''
    except Exception:                                          # noqa: BLE001
        pass
    text = decode_out(out)

    if killed:
        if tail:
            show_tail(text, tail)
        return 124, text + '\n[已超时，强制结束]'
    if tail is not None and rc != 0:
        show_tail(text, tail)
    return proc.returncode, text


def show_tail(text, n=30):
    if not text or not text.strip():
        print('         | （没有输出）')
        return
    for line in text.rstrip().splitlines()[-n:]:
        print('         | ' + line)


def pip_base():
    return ['-m', 'pip', 'install',
            '--progress-bar', 'off',
            '--timeout', '20', '--retries', '1',
            '--no-input', '--disable-pip-version-check']


def pip_install(package):
    rc, out = run([VENV_PY, '-u'] + pip_base() + ['-i', MIRROR, package],
                  heartbeat=True, tail=30, timeout=PKG_TIMEOUT)
    if rc == 0:
        return 0, out
    print('         镜像源没成功，改用官方源重试 ...')
    return run([VENV_PY, '-u'] + pip_base() + [package],
               heartbeat=True, tail=30, timeout=PKG_TIMEOUT)


def main():
    head('SmartWorks 依赖安装')
    print('  项目目录 : ' + ROOT)
    print('  虚拟环境 : ' + VENV_PY)
    print('  说明：装包时每 5 秒打印一个点，表示仍在工作')
    print('        单个包最多等 4 分钟，超时会自动跳过并报错')

    # ---------- 1 环境 ----------
    head('第 1 步 共 6 步：检查环境')
    print('  Python 版本: %d.%d.%d' % sys.version_info[:3])
    if sys.version_info < (3, 10):
        print()
        print('  [失败] Python 版本过低，需要 3.10 以上')
        return 1
    npm = shutil.which('npm')
    print('  npm 路径   : ' + (npm or '没找到'))
    if not npm:
        print()
        print('  [失败] 没找到 npm，请先安装 Node.js LTS 并重启电脑')
        return 1
    print('  检查通过')

    # ---------- 2 虚拟环境 ----------
    head('第 2 步：准备虚拟环境 .venv')
    if os.path.exists(VENV_PY):
        print('  已存在，跳过创建')
    else:
        if os.path.exists(VENV):
            print('  发现不完整的 .venv，先删除')
            shutil.rmtree(VENV, ignore_errors=True)
        print('  正在创建 ...')
        rc, out = run([sys.executable, '-m', 'venv', VENV], tail=20)
        if rc != 0 or not os.path.exists(VENV_PY):
            print()
            print('  [失败] 虚拟环境创建失败')
            return 1
        print('  已创建')

    # ---------- 3 pip 自检 ----------
    head('第 3 步：检查 .venv 里的 pip 是否可用')
    rc, out = run([VENV_PY, '-m', 'pip', '--version'], tail=10)
    print('  ' + (out.strip() or '(无输出)'))
    if rc != 0:
        print()
        print('  [失败] 虚拟环境里的 pip 不可用')
        print('  解决：删除 SmartWorks 下的 .venv 文件夹，再运行本脚本')
        return 1
    print('  pip 可用')

    # ---------- 4 逐个装包 ----------
    total = len(PACKAGES)
    head('第 4 步：安装 Python 库，共 %d 个' % total)
    print()

    failed = None
    for i, (pkg, desc) in enumerate(PACKAGES, start=1):
        print('  [%2d/%2d] %-22s %s' % (i, total, pkg, desc))
        t0 = time.time()
        rc, out = pip_install(pkg)
        cost = time.time() - t0
        if rc != 0:
            print('         [失败] 耗时 %.1f 秒' % cost)
            failed = pkg
            break
        print('         完成，%.1f 秒' % cost)

    if failed:
        print()
        print(BAR)
        print('  [失败] 卡在包：%s' % failed)
        print('  上面以 | 开头的行是 pip 的原始输出，请整段截图发到群里')
        print(BAR)
        return 1

    # ---------- 5 导入自检 ----------
    head('第 5 步：验证关键库能否导入')
    code = ('import django, rest_framework, corsheaders, drf_spectacular, '
            'django_filters, simple_history, import_export, dotenv, PIL, requests; '
            'print("全部导入成功，Django 版本 " + django.get_version())')
    rc, out = run([VENV_PY, '-c', code], tail=20)
    print('  ' + (out.strip() or '(无输出)'))
    if rc != 0:
        print()
        print('  [失败] 库装上了但导入失败，可能存在版本冲突')
        return 1

    # ---------- 6 前端 ----------
    head('第 6 步：安装前端依赖，3 到 8 分钟')
    frontend = os.path.join(ROOT, 'frontend')
    if not os.path.isdir(frontend):
        print()
        print('  [失败] 找不到 frontend 目录')
        return 1
    if os.path.isdir(os.path.join(frontend, 'node_modules')):
        print('  node_modules 已存在，跳过')
    else:
        print('  设置镜像源 ...')
        run([COMSPEC, '/c', 'npm config set registry ' + NPM_REGISTRY], cwd=frontend, tail=5)
        print('  开始安装（每 5 秒一个点）...')
        t0 = time.time()
        rc, out = run([COMSPEC, '/c', 'npm install --no-audit --no-fund'],
                      cwd=frontend, heartbeat=True, tail=30, timeout=600)
        if rc != 0:
            print('         [失败] 见上方 npm 输出')
            return 1
        print('  前端依赖安装完成，%.1f 秒' % (time.time() - t0))

    # ---------- 7 配置文件 ----------
    head('第 7 步：生成配置文件 .env')
    env_path = os.path.join(ROOT, '.env')
    example = os.path.join(ROOT, '.env.example')
    if os.path.exists(env_path):
        print('  已存在，跳过')
    elif os.path.exists(example):
        shutil.copyfile(example, env_path)
        print('  已生成（默认 SQLite，不需要装数据库）')
    else:
        print()
        print('  [失败] 找不到 .env.example')
        return 1

    head('全部完成')
    print('  下一步：双击 2-初始化数据库.bat')
    print()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print('  已中断。重新双击 1-安装依赖.bat 可继续，已装好的会跳过。')
        sys.exit(1)
