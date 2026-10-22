# -*- coding: utf-8 -*-
"""一键提交并推送。由 scripts/4-提交并推送.bat 调用。

流程：
  1. 检查是否已初始化仓库；没有远程则交互式询问仓库地址并配置
  2. git status 显示改了什么
  3. 有改动 → 暂存、写说明、提交；没改动 → 跳过，但仍继续推送已有提交
  4. 远程已有该分支 → 先 pull --rebase；远程是空的（首次）→ 跳过 pull
  5. git push

修正记录：
  最初版本在"没有新改动"时直接 return，导致本地已有的提交始终推不上去。
  现在无论有没有新改动都会走到推送这一步。
"""
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAR = '=' * 58
PROTECTED = ('.env',)


def head(text):
    print()
    print(BAR)
    print('  ' + text)
    print(BAR)


def git(*args, show=False):
    """执行 git，返回 (返回码, 输出)。输出按 UTF-8 → GBK 依次尝试解码。"""
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


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ''


def ensure_identity():
    """确保本仓库已配置提交者姓名与邮箱。没有就交互式问一次并写入本仓库配置。

    为什么需要：git commit 会记录作者信息，未配置时直接报
      "Author identity unknown ... unable to auto-detect email address"。
    配置范围用仓库本地（不加 --global），只影响当前项目，不动电脑全局设置。
    """
    _, name = git('config', 'user.name')
    _, email = git('config', 'user.email')
    if name.strip() and email.strip():
        return True

    head('首次使用：需要设置你的名字和邮箱')
    print('  这两个信息会写进每次提交记录，用来标识"这次改动是谁做的"。')
    print('  只要不影响使用，随便填；建议用 GitHub 用户名和它的 noreply 邮箱。')
    print('  例：fengwan-ti / fengwan-ti@users.noreply.github.com')
    print('  留空 = 取消')
    print()
    n = ask('  你的名字> ')
    if not n:
        print()
        print('  已取消。')
        return False
    e = ask('  你的邮箱> ')
    if not e:
        print()
        print('  已取消。')
        return False

    git('config', 'user.name', n)
    git('config', 'user.email', e)
    print('  已记住（只对当前仓库生效）: %s <%s>' % (n, e))
    return True


def setup_remote():
    """首次使用：交互式配置远程仓库地址。返回 (仓库地址 or None)。"""
    head('首次使用：需要先告诉脚本仓库地址')
    print('  请先在浏览器里建好仓库（GitHub 或 Gitee），然后复制它的地址。')
    print('  GitHub 地址形如: https://github.com/你的用户名/smartworks.git')
    print('  Gitee  地址形如: https://gitee.com/你的用户名/smartworks.git')
    print('  直接回车 = 取消')
    print()
    url = ask('  仓库地址> ')
    if not url:
        print()
        print('  已取消。地址拿到后重新双击本脚本即可。')
        print()
        return None
    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('git@')):
        print()
        print('  [错误] 地址格式不对，应以 https:// 或 git@ 开头')
        print()
        return None
    rc, _ = git('remote', 'add', 'origin', url)
    if rc != 0:
        print()
        print('  [失败] 配置远程仓库失败，请把上面的提示发到群里')
        print()
        return None
    git('branch', '-M', 'main')
    print('  已配置远程仓库: ' + url)
    return url


def main():
    head('SmartWorks 一键提交并推送')

    if not os.path.isdir(os.path.join(ROOT, '.git')):
        print()
        print('  [错误] 这个目录还不是 Git 仓库')
        print('  请确认 SmartWorks 文件夹是从仓库克隆下来的，而不是自己拼的')
        print()
        return 1

    rc, origin = git('remote', 'get-url', 'origin')
    if rc != 0:
        origin = setup_remote()
        if not origin:
            return 1
    origin = origin.strip()
    print('  远程仓库: ' + origin)

    rc, branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    branch = branch.strip() or 'main'
    print('  当前分支: ' + branch)

    # ---------- 1 看看改了什么 ----------
    head('第 1 步：看看改了什么')
    rc, status = git('status', '--short', show=True)
    has_change = bool(status.strip())

    # ---------- 2 有改动就提交 ----------
    if has_change:
        head('第 2 步：暂存并提交')
        git('add', '-A')
        rc, staged = git('diff', '--cached', '--name-only')
        names = [x for x in staged.splitlines() if x.strip()]
        print('  已暂存 %d 个文件' % len(names))

        bad = [x for x in names
               if x.strip() in PROTECTED or '.venv' in x or 'node_modules' in x
               or x.strip().endswith('db.sqlite3')]
        if bad:
            print()
            print('  [注意] 以下文件不该提交，已取消暂存：')
            for b in bad:
                print('    ' + b)
                git('reset', 'HEAD', '--', b)
            print('  若 .env 曾被提交过，请按 docs/git-workflow.md 第七节处理')

        print()
        print('  格式建议：类型(模块): 说明    例：feat(inventory): 新增入库扫码上架')
        print('  直接回车 = 使用默认说明')
        msg = ask('  说明> ')
        if not msg:
            msg = 'chore: 更新于 ' + datetime.now().strftime('%Y-%m-%d %H:%M')

        head('提交')
        if not ensure_identity():
            return 1
        rc, out = git('commit', '-m', msg, show=True)
        if rc != 0:
            print()
            print('  [失败] 提交失败。可能原因：暂存区没有实际改动，或配置仍不完整')
            print()
            return 1
    else:
        head('第 2 步：没有新改动')
        print('  工作区是干净的，跳过提交，直接推送已保存的提交')

    # ---------- 3 判断远程是否已有该分支 ----------
    rc, remote_heads = git('ls-remote', '--heads', 'origin', branch)
    remote_exists = bool(remote_heads.strip())

    if remote_exists:
        head('第 3 步：先拉取别人的改动')
        rc, out = git('pull', '--rebase', 'origin', branch, show=True)
        if rc != 0:
            print()
            print('  [失败] 拉取失败，通常是存在冲突或网络问题。')
            print('  不要把上面这段自己乱改，直接发到群里。')
            if ask('  仍然尝试推送吗？输入 y 继续 > ').lower() != 'y':
                print()
                print('  已停止。')
                return 1
    else:
        head('第 3 步：远程还没有这个分支')
        print('  这是第一次推送，跳过拉取')

    # ---------- 4 推送 ----------
    head('第 4 步：推送')
    rc, out = git('push', '-u', 'origin', branch, show=True)
    if rc != 0:
        print()
        print('  [失败] 推送失败。常见原因：')
        print('    1. GitHub 必须用 Personal Access Token 而不是账号密码')
        print('       见 docs/git-workflow.md 第 9.3 节')
        print('    2. 网络访问 GitHub 不稳 → 重试，或改用 Gitee')
        print('    3. 远程有别人的提交 → 再运行一次本脚本')
        return 1

    head('完成')
    print('  已推送成功')
    print('  仓库地址: ' + origin)
    web = origin.replace('.git', '')
    if web.startswith('https://'):
        print('  网页查看: ' + web)
    print()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print('  已中断。')
        sys.exit(1)
