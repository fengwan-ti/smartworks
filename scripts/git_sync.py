# -*- coding: utf-8 -*-
"""一键提交并推送。由 scripts/提交代码.bat 调用。

为什么做这个：
  新手记不住 git 那几条命令，也容易漏掉 `git pull` 导致推送被拒。
  这个脚本把"暂存 → 写说明 → 提交 → 拉取 → 推送"串成一步，并给出中文提示。

流程：
  1. 检查是否已初始化仓库、是否已配置远程
  2. git status 显示改了什么
  3. git add -A 暂存
  4. 让你输入一句说明（直接回车用默认的"更新时间"）
  5. git commit
  6. git pull --rebase（先拉别人的改动，避免推送被拒）
  7. git push
"""
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAR = '=' * 58


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def git(*args, show=False, check=False):
    """执行 git 命令，返回 (返回码, 输出)。输出按 UTF-8 → GBK 依次尝试解码。"""
    proc = subprocess.run(['git'] + list(args), cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = proc.stdout or b''
    text = ''
    for enc in ('utf-8', 'gbk'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode('utf-8', errors='replace')
    if show and text.strip():
        for line in text.rstrip().splitlines():
            print('    ' + line)
    return proc.returncode, text


def main():
    head('SmartWorks 一键提交并推送')

    if not os.path.isdir(os.path.join(ROOT, '.git')):
        print()
        print('  [错误] 这个目录还不是 Git 仓库')
        print('  请先把 SmartWorks 文件夹解压/克隆完整')
        print()
        return 1

    rc, origin = git('remote', 'get-url', 'origin')
    if rc != 0:
        # 第一次还没有远程仓库：在这里直接问一句地址，帮他配好，省去敲命令
        head('首次使用：需要先告诉脚本仓库地址')
        print('  请先在浏览器里建好仓库（GitHub 或 Gitee），然后复制它的地址。')
        print('  GitHub 地址形如: https://github.com/你的用户名/smartworks.git')
        print('  Gitee  地址形如: https://gitee.com/你的用户名/smartworks.git')
        print('  直接回车 = 取消')
        print()
        try:
            url = input('  仓库地址> ').strip()
        except (EOFError, KeyboardInterrupt):
            url = ''
        if not url:
            print()
            print('  已取消。地址拿到后重新双击本脚本即可。')
            print()
            return 1
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('git@')):
            print()
            print('  [错误] 地址格式不对，应以 https:// 或 git@ 开头')
            print()
            return 1
        rc, out = git('remote', 'add', 'origin', url)
        if rc != 0:
            print()
            print('  [失败] 配置远程仓库失败，请把上面的提示发到群里')
            return 1
        git('branch', '-M', 'main')
        print('  已配置远程仓库: ' + url)
        origin = url
    print('  远程仓库: ' + origin.strip())

    rc, branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    branch = branch.strip() or 'main'
    print('  当前分支: ' + branch)

    head('第 1 步：看看改了什么')
    rc, status = git('status', '--short', show=True)
    if not status.strip():
        print('    （没有任何改动，无需提交）')
        print()
        return 0

    head('第 2 步：暂存全部改动')
    rc, out = git('add', '-A')
    if rc != 0:
        print('  [失败] 暂存失败')
        return 1
    rc, staged = git('diff', '--cached', '--name-only')
    n = len([x for x in staged.splitlines() if x.strip()])
    print('  已暂存 %d 个文件' % n)

    bad = [x for x in staged.splitlines()
           if x.strip() in ('.env',) or '.venv' in x or 'node_modules' in x
           or x.strip().endswith('db.sqlite3')]
    if bad:
        print()
        print('  [注意] 以下文件不该提交，已自动取消暂存：')
        for b in bad:
            print('    ' + b)
            git('reset', 'HEAD', '--', b)
        print('  如果是 .env 被提交过，请按 docs/git-workflow.md 第七节处理')

    head('第 3 步：写一句提交说明')
    print('  格式建议：类型(模块): 说明')
    print('  例子：feat(inventory): 新增入库扫码上架')
    print('  直接回车 = 使用默认说明')
    try:
        msg = input('  说明> ').strip()
    except (EOFError, KeyboardInterrupt):
        msg = ''
    if not msg:
        msg = 'chore: 更新于 ' + datetime.now().strftime('%Y-%m-%d %H:%M')

    head('第 4 步：提交')
    rc, out = git('commit', '-m', msg, show=True)
    if rc != 0:
        print()
        print('  [失败] 提交失败。常见原因：')
        print('    1. 没配置用户名邮箱 → 执行下面两行后重试：')
        print('       git config --global user.name "你的名字"')
        print('       git config --global user.email "你的邮箱"')
        print('    2. 没有实际改动')
        return 1

    head('第 5 步：先拉取别人的改动（避免推送被拒）')
    rc, out = git('pull', '--rebase', 'origin', branch, show=True)
    if rc != 0:
        print()
        print('  [失败] 拉取失败，常见两种情况：')
        print('    1. 远程还没有这个分支（第一次推送）→ 可以忽略，继续往下走')
        print('    2. 存在冲突 → 请把上面的提示发到群里，不要自己乱改')
        print()
        go = input('  仍然尝试推送吗？输入 y 继续，其他键退出 > ').strip().lower()
        if go != 'y':
            print()
            print('  已停止。请把报错发到群里。')
            return 1

    head('第 6 步：推送')
    rc, out = git('push', '-u', 'origin', branch, show=True)
    if rc != 0:
        print()
        print('  [失败] 推送失败。常见原因：')
        print('    1. GitHub 要求用 Personal Access Token 而不是账号密码')
        print('       见 docs/git-workflow.md 第九节')
        print('    2. 网络访问 GitHub 不稳 → 重试，或改用 Gitee')
        print('    3. 远程有别人的提交 → 再运行一次本脚本')
        return 1

    head('完成')
    print('  代码已推送到远程仓库')
    print('  地址: ' + origin.strip())
    print()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print('  已中断。')
        sys.exit(1)
