# -*- coding: utf-8 -*-
"""启动前后端并打开浏览器。由 3-启动系统.bat 调用。

三个踩坑后修正的点：
  1) 浏览器地址必须用 localhost，不能用 127.0.0.1
     Vite 默认监听的 host 是 "localhost"，在 Windows 上优先解析为 IPv6 的 ::1。
     实测 netstat 显示 "TCP [::1]:5173 LISTENING"，即只绑了 IPv6，
     用 http://127.0.0.1:5173（IPv4）始终连不上，表现就是"无法访问此页面"。
  2) 启动前先清掉占用 5173 / 8000 的残留进程
     否则 Vite 会自动换到 5174，浏览器打开的地址和实际不一致。
  3) 用 cmd.exe /k 而不是 shell=True
     /k 让窗口在命令结束后不关闭，报错信息留在屏幕上；用 /c 则出错即关窗、看不见原因。
"""
import os
import shutil
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
BACKEND = os.path.join(ROOT, 'backend')
FRONTEND = os.path.join(ROOT, 'frontend')
CMD = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'cmd.exe')
CREATE_NEW_CONSOLE = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0x00000010)
BAR = '=' * 54

WEB_URL = 'http://localhost:5173'
API_URL = 'http://localhost:8000'


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def pids_on_port(port):
    """用 netstat 找出正在 LISTEN 指定端口的进程号。"""
    pids = set()
    try:
        out = subprocess.run(['netstat', '-ano'], capture_output=True).stdout or b''
        text = out.decode('gbk', errors='replace')
    except Exception:                                          # noqa: BLE001
        return pids
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != 'TCP':
            continue
        local, state, pid = parts[1], parts[3].upper(), parts[4]
        if state != 'LISTENING':
            continue
        if local.endswith(':%d' % port):
            if pid.isdigit() and pid != '0':
                pids.add(pid)
    return pids


def free_port(port, label):
    pids = pids_on_port(port)
    if not pids:
        return
    print('  %s 端口 %d 被占用（PID %s），先结束它们' % (label, port, ', '.join(sorted(pids))))
    for pid in pids:
        subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
    time.sleep(1)


def spawn(window_title, cwd, cmdline):
    argv = [CMD, '/k', 'title ' + window_title + ' & ' + cmdline]
    print('    窗口: ' + window_title)
    print('    命令: ' + cmdline)
    return subprocess.Popen(argv, cwd=cwd, creationflags=CREATE_NEW_CONSOLE)


def main():
    head('SmartWorks 启动')
    if not os.path.exists(VENV_PY):
        print()
        print('  [错误] 没找到虚拟环境，请先双击 1-安装依赖.bat')
        print()
        return 1
    if not os.path.isdir(FRONTEND):
        print()
        print('  [错误] 找不到 frontend 目录')
        print()
        return 1
    if not os.path.isdir(os.path.join(FRONTEND, 'node_modules')):
        print()
        print('  [错误] 前端依赖没装，请先双击 1-安装依赖.bat')
        print()
        return 1

    npm = shutil.which('npm')
    if not npm:
        print()
        print('  [错误] 找不到 npm，请重装 Node.js LTS 并重启电脑')
        print()
        return 1
    print('  npm: ' + npm)

    head('清理上次残留的进程')
    free_port(8000, '后端')
    free_port(5173, '前端')
    print('  清理完成')

    print()
    print('  会弹出两个黑窗口，都不要关')
    print('  关掉它们就等于关闭系统')
    print('  某个窗口出现红色报错，把那一段发到群里')
    print()

    head('启动后端 ' + API_URL)
    spawn('SmartWorks-BACKEND-do-not-close',
          BACKEND,
          '..\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000')
    print('  等待 5 秒 ...')
    time.sleep(5)

    head('启动前端 ' + WEB_URL)
    spawn('SmartWorks-FRONTEND-do-not-close',
          FRONTEND,
          '"%s" run dev' % npm)
    print('  等待 15 秒让前端编译 ...')
    time.sleep(15)

    head('就绪')
    print('  系统界面   ' + WEB_URL)
    print('  接口文档   ' + API_URL + '/api/docs/')
    print('  后台管理   ' + API_URL + '/admin/')
    print()
    print('  账号 admin    密码 admin123')
    print()
    print('  注意：地址必须是 localhost，不是 127.0.0.1')
    print('        强制刷新用 Ctrl + Shift + R')
    print()

    webbrowser.open(WEB_URL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
