#!/usr/bin/env python
"""Django 命令行入口。"""
import os
import sys


def _make_console_gbk_safe():
    """把 stdout/stderr 的 errors 从 strict 改成 replace。

    背景（2026-11-15 B 现场踩到）：Windows 中文控制台是 cp936(GBK)，
    代码里只要出现一个 GBK 编不了的字符（`−` U+2212、`✅`、`⚠️`…），
    print 就会直接抛 UnicodeEncodeError 把整条命令打断 ——
    `demo_w5_schedule` 就是在打印"提升：makespan −62.8%"那一行崩的。

    改 errors='replace' 之后，最坏的后果只是那一个字符显示成 `?`，
    命令继续跑完。这不是纵容乱写字符：源码里该用 ASCII 还是用 ASCII，
    这里只是加一道"演示现场不能因为一个符号而翻车"的兜底。

    reconfigure 只在 3.7+ 且 stdout 有该方法时存在（被重定向到 StringIO
    之类的情况下会跳过，不影响单测）。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    _make_console_gbk_safe()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "无法导入 Django。请确认已激活虚拟环境并执行 pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
