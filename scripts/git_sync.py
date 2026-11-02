# -*- coding: utf-8 -*-
"""一键提交并推送。由 scripts/4-提交并推送.bat 调用。

流程：
  1. 检查仓库与远程；没有远程则交互式询问地址
  2. 显示改了什么
  3. 有改动 → 暂存、写说明、提交；没改动 → 跳过，但仍继续推送已有提交
  4. 远程已有该分支 → 先 pull --rebase
  5. git push

修正记录：
  1. 最初版本在"没有新改动"时直接 return，导致本地已有提交推不上去 → 改为继续推送
  2. 提交前未检测 git 身份，报 Author identity unknown → 增加 ensure_identity()
  3. 原先用 git ls-remote 联网判断远程分支，网络慢或需要认证时会静默卡住，
     屏幕只剩闪烁光标、看不出在等什么 → 改为查本地远程跟踪引用，瞬时返回；
     同时给所有 git 调用加超时，超时会明确报错而不是无限等待
"""
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAR = '=' * 58
PROTECTED = ('.env',)


def say(text=''):
    print(text)
    sys.stdout.flush()


def head(text):
    say()
    say(BAR)
    say('  ' + text)
    say(BAR)


def decode(raw):
    for enc in ('utf-8', 'gbk'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def git(*args, show=False, timeout=120):
    """执行 git，返回 (返回码, 输出)。

    timeout：秒。超时返回码置 124 并在输出里标记，避免无限卡住。
    """
    try:
        proc = subprocess.run(['git'] + list(args), cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or b''
        return 124, decode(raw) + '\n[超时] 命令在 %d 秒内没有返回，已放弃等待' % timeout
    except FileNotFoundError:
        return 127, '[找不到 git] 请先安装 Git 并重启命令行'

    text = decode(proc.stdout or b'')
    if show and text.strip():
        for line in text.rstrip().splitlines():
            say('    ' + line)
    return proc.returncode, text


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ''


def ensure_identity():
    """确保本仓库已配置提交者姓名与邮箱，没有就交互式问一次并写入本仓库配置。

    git commit 会记录作者信息，未配置时报
    "Author identity unknown ... unable to auto-detect email address"。
    配置范围用仓库本地（不加 --global），只影响当前项目。
    """
    _, name = git('config', 'user.name', timeout=20)
    _, email = git('config', 'user.email', timeout=20)
    if name.strip() and email.strip():
        return True

    head('首次使用：需要设置你的名字和邮箱')
    say('  这两个信息会写进每次提交记录，用来标识"这次改动是谁做的"。')
    say('  建议用你自己的 GitHub 用户名和它的 noreply 邮箱。')
    say('  例：fengwan-ti / fengwan-ti@users.noreply.github.com')
    say('  ⚠️ 三个人必须各填各的，否则提交记录会全记在组长名下，个人贡献算不清。')
    say('  留空 = 取消')
    say()
    n = ask('  你的名字> ')
    if not n:
        say()
        say('  已取消。')
        return False
    e = ask('  你的邮箱> ')
    if not e:
        say()
        say('  已取消。')
        return False

    git('config', 'user.name', n, timeout=20)
    git('config', 'user.email', e, timeout=20)
    say('  已记住（只对当前仓库生效）: %s <%s>' % (n, e))
    return True


def setup_remote():
    """首次使用：交互式配置远程仓库地址。返回地址或 None。"""
    head('首次使用：需要先告诉脚本仓库地址')
    say('  请先在浏览器里建好仓库（GitHub 或 Gitee），然后复制它的地址。')
    say('  GitHub 地址形如: https://github.com/你的用户名/smartworks.git')
    say('  Gitee  地址形如: https://gitee.com/你的用户名/smartworks.git')
    say('  直接回车 = 取消')
    say()
    url = ask('  仓库地址> ')
    if not url:
        say()
        say('  已取消。地址拿到后重新双击本脚本即可。')
        return None
    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('git@')):
        say()
        say('  [错误] 地址格式不对，应以 https:// 或 git@ 开头')
        return None
    rc, _ = git('remote', 'add', 'origin', url, timeout=20)
    if rc != 0:
        say()
        say('  [失败] 配置远程仓库失败，请把上面的提示发到群里')
        return None
    git('branch', '-M', 'main', timeout=20)
    say('  已配置远程仓库: ' + url)
    return url


def main():
    head('SmartWorks 一键提交并推送')

    if not os.path.isdir(os.path.join(ROOT, '.git')):
        say()
        say('  [错误] 这个目录还不是 Git 仓库')
        say('  请确认 SmartWorks 是从仓库克隆下来的，而不是自己拼的文件夹')
        return 1

    rc, origin = git('remote', 'get-url', 'origin', timeout=20)
    if rc != 0:
        origin = setup_remote()
        if not origin:
            return 1
    origin = origin.strip()
    say('  远程仓库: ' + origin)

    rc, branch = git('rev-parse', '--abbrev-ref', 'HEAD', timeout=20)
    branch = branch.strip() or 'main'
    say('  当前分支: ' + branch)

    # ---------- 1 看看改了什么 ----------
    head('第 1 步：看看改了什么')
    rc, status = git('status', '--short', show=True, timeout=60)
    has_change = bool(status.strip())
    if not has_change:
        say('    （工作区干净）')

    # ---------- 2 有改动就提交 ----------
    if has_change:
        head('第 2 步：暂存并提交')
        git('add', '-A', timeout=120)
        rc, staged = git('diff', '--cached', '--name-only', timeout=60)
        names = [x for x in staged.splitlines() if x.strip()]
        say('  已暂存 %d 个文件' % len(names))

        bad = [x for x in names
               if x.strip() in PROTECTED or '.venv' in x or 'node_modules' in x
               or x.strip().endswith('db.sqlite3')]
        if bad:
            say()
            say('  [注意] 以下文件不该提交，已取消暂存：')
            for b in bad:
                say('    ' + b)
                git('reset', 'HEAD', '--', b, timeout=30)
            say('  若 .env 曾被提交过，请按 docs/git-workflow.md 第七节处理')

        say()
        say('  格式建议：类型(模块): 说明    例：feat(inventory): 新增入库扫码上架')
        say('  直接回车 = 使用默认说明')
        msg = ask('  说明> ')
        if not msg:
            msg = 'chore: 更新于 ' + datetime.now().strftime('%Y-%m-%d %H:%M')

        head('提交')
        if not ensure_identity():
            return 1
        rc, out = git('commit', '-m', msg, show=True, timeout=120)
        if rc != 0:
            say()
            say('  [失败] 提交失败。可能是暂存区没有实际改动，或配置仍不完整')
            return 1
    else:
        head('第 2 步：没有新改动')
        say('  跳过提交，直接推送已保存的提交')

    # ---------- 3 判断远程是否已有该分支（只查本地记录，不联网） ----------
    rc_ref, _ = git('rev-parse', '--verify', 'refs/remotes/origin/%s' % branch, timeout=20)
    remote_exists = rc_ref == 0

    if remote_exists:
        head('第 3 步：先拉取别人的改动')
        say('  正在连接远程仓库，网络慢的话请等，不要关窗口')
        rc, out = git('pull', '--rebase', 'origin', branch, show=True, timeout=180)
        if rc != 0:
            say()
            if rc == 124:
                say('  [超时] 拉取超过 180 秒没有返回，通常是网络问题')
            else:
                say('  [失败] 拉取失败，通常是存在冲突或网络问题。')
                say('  不要把上面这段自己乱改，直接发到群里。')
            if ask('  仍然尝试推送吗？输入 y 继续 > ').lower() != 'y':
                say()
                say('  已停止。')
                return 1
    else:
        head('第 3 步：远程还没有这个分支')
        say('  这是第一次推送，跳过拉取')

    # ---------- 4 推送 ----------
    head('第 4 步：推送')
    say('  正在上传，可能要几十秒到几分钟，期间没有新输出是正常的')
    rc, out = git('push', '-u', 'origin', branch, show=True, timeout=600)
    if rc != 0:
        say()
        if rc == 124:
            say('  [超时] 推送超过 10 分钟没有完成，网络太慢或连接被中断。')
            say('  建议：换网络后重跑本脚本；已提交的代码不会丢。')
        else:
            say('  [失败] 推送失败。常见原因：')
            say('    1. GitHub 必须用 Personal Access Token 而不是账号密码')
            say('       见 docs/git-workflow.md 第 9.3 节')
            say('    2. 网络访问 GitHub 不稳 → 重试，或改用 Gitee')
            say('    3. 远程有别人的提交 → 再运行一次本脚本')
            say('    4. 不是仓库协作者 → 让组长在 Settings → Collaborators 里加你')
        return 1

    head('完成')
    say('  已推送成功')
    say('  仓库地址: ' + origin)
    web = origin.replace('.git', '')
    if web.startswith('https://'):
        say('  网页查看: ' + web)
    say()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say()
        say('  已中断。代码已安全保存在本地，重新双击本脚本可继续。')
        sys.exit(1)
