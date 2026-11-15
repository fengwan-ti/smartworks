# -*- coding: utf-8 -*-
"""停止 SmartWorks 的前后端服务。由 5-停止系统.bat 调用。

为什么需要这个脚本：
  两个服务跑在独立控制台窗口里，平时关窗口就能停。但有两种情况关不干净：
    1. 窗口被最小化后忘了在哪个
    2. 进程异常退出，端口还被占着（表现：Vite 自动跳到 5174，
       浏览器打 5173 却打不开 —— 这个坑我们踩过一次）
  所以给一个"一句话停干净"的入口。
"""
import os
import subprocess
import sys
import time

BAR = '=' * 54


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def pids_on_port(port):
    """用 netstat 找正在 LISTEN 指定端口的进程号。"""
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
        if local.endswith(':%d' % port) and pid.isdigit() and pid != '0':
            pids.add(pid)
    return pids


def kill(pid):
    try:
        subprocess.run(['taskkill', '/PID', pid, '/F'],
                       capture_output=True, timeout=10)
        return True
    except Exception:                                          # noqa: BLE001
        return False


def main():
    head('SmartWorks 停止服务')

    total = 0
    for port, label in ((8000, '后端 Django'), (5173, '前端 Vite'), (5174, '前端 Vite（备用端口）')):
        pids = pids_on_port(port)
        if not pids:
            print('  %-22s 端口 %d  没有进程占用' % (label, port))
            continue
        print('  %-22s 端口 %d  占用进程 %s' % (label, port, ', '.join(sorted(pids))))
        for pid in sorted(pids):
            ok = kill(pid)
            print('      结束 PID %-8s %s' % (pid, '成功' if ok else '失败（可能已退出）'))
            total += 1
        time.sleep(0.4)

    # 再把残留的标题窗口对应的进程兜一遍（按命令行特征找）
    try:
        out = subprocess.run(
            ['wmic', 'process', 'where',
             "name='node.exe' or name='python.exe'", 'get', 'ProcessId,CommandLine'],
            capture_output=True).stdout or b''
        text = out.decode('gbk', errors='replace')
        for line in text.splitlines():
            low = line.lower()
            if 'vite' in low or 'runserver' in low:
                parts = line.split()
                if parts and parts[-1].isdigit():
                    pid = parts[-1]
                    if kill(pid):
                        print('  兜底结束 PID %-8s （命令行匹配 vite/runserver）' % pid)
                        total += 1
    except Exception:                                          # noqa: BLE001
        pass

    head('已停止' if total else '没有需要停止的服务')
    if total:
        print('  现在可以放心关掉那两个黑窗口了')
        print('  下次使用：双击 3-启动系统.bat')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
