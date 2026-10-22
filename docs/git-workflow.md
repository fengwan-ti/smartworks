# Git 协作指南

> 四个人改同一个仓库。不按这份流程走，一定会在某一天把别人的代码覆盖掉。

## 一、第一次：把仓库推到远程（组长做一次）

GitHub 和 Gitee 都可以。**优先用你已有账号的那个平台**：
GitHub 需要个人访问令牌（见第九节），Gitee 可直接用密码。
GitHub 在国内可能偶发连接超时，重试或换 Gitee 即可。

1. 打开 https://gitee.com ，注册并登录
2. 右上角 **+** → **新建仓库**
3. 填写：
   - 仓库名称：`smartworks`
   - 路径：默认即可
   - **不要**勾选"使用 Readme 文件初始化"（否则和本地冲突）
   - 开源/私有都可以
4. 创建后页面会给出一段命令，复制**"已有仓库"**那一段，类似：

```bash
git remote add origin https://gitee.com/你的用户名/smartworks.git
git push -u origin main
```

5. 在 `SmartWorks` 目录打开命令行，粘贴执行
6. 首次 push 会要求输入 Gitee 的**用户名和密码**（或私人令牌）

推成功后在网页上能看到 114 个文件。

## 二、其余三人：克隆下来

```bash
cd C:\Users\你的用户名\Desktop
git clone https://gitee.com/你的用户名/smartworks.git
```

然后按 `README.md` 跑 `0 → 1 → 2 → 3`。**不要**用 zip 解压的方式长期工作，只用于应急。

## 三、每天：三行命令

```bash
git pull                     # 1. 先拉别人的改动
git status                   # 2. 看自己改了哪些文件
git add -A                   # 3. 暂存
git commit -m "feat(inventory): 新增入库扫码上架"
git push                     # 4. 推上去
```

顺序不能反：**先 pull 再改**，比改完再合并省事得多。

## 四、提交信息规范

格式：`类型(应用名): 中文说明`

| 类型 | 用于 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 只改文档 |
| `refactor` | 重构，行为不变 |
| `chore` | 配置、依赖、脚本 |

例子：

```
feat(process): 新增工艺路线复制功能
fix(planning): 修正冻结区工单被重排的问题
docs: 补充接口契约的排产部分
```

## 五、分支（第二周开始用）

| 分支 | 谁动 | 用途 |
|---|---|---|
| `main` | 只有组长 | 随时能跑的稳定版 |
| `feature/xxx` | 各人 | 自己的开发分支 |

```bash
git checkout -b feature/inventory-inbound     # 建自己的分支
# ...写代码、提交...
git push -u origin feature/inventory-inbound
```

写完后在 Gitee 上发起"合并请求"，由组长确认再合到 main。

## 六、四条铁律

1. **跑不通的代码不许 push 到 main**
2. **不提交 `.env`、`.venv`、`node_modules`、`db.sqlite3`**（`.gitignore` 已挡）
3. **不提交数据库密码、密钥**
4. **每天至少提交一次**，提交信息写清楚改了什么

## 七、常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| push 被拒，提示 non-fast-forward | 远程有别人的新提交 | 先 `git pull --rebase`，再 push |
| 大量文件显示"都被修改"但内容没变 | 换行符差异 | 本仓库有 `.gitattributes`，执行 `git add --renormalize .` 后提交 |
| 中文文件名显示乱码 | Git 默认转义中文 | `git config --global core.quotepath false` |
| 不知道谁改了什么 | — | `git log --oneline -10` 或 Gitee 网页看提交记录 |
| 误提交了 `.env` | — | 立刻 `git rm --cached .env` 后提交，并**更换数据库密码** |

## 八、为什么要这么做（给新手的说明）

Git 不是"备份工具"，是**协作工具**。它解决的是：四个人同时改同一个项目，谁的改动该保留、谁的改了别的地方、冲突时以谁为准。

没有它，常见的三种灾难是：
- A 把整个文件夹发给 B，B 改完发回来，A 自己那段改动丢了
- 两人都改了同一个文件，靠"复制粘贴谁的最后版"决定，另一方白干
- 出了问题想退回昨天能跑的版本，但没有"昨天"这个东西


## 九、用 GitHub 的完整步骤（含个人访问令牌）

### 9.1 为什么不能直接用密码

GitHub 自 2021 年起取消了密码认证，git push 时必须用 **Personal Access Token（PAT）** 代替密码。
这是新手最容易卡住的一步：填了账号密码会一直报 Authentication failed。

### 9.2 建仓库

1. 登录 github.com，右上角 **+** → **New repository**
2. Repository name 填 smartworks
3. **不要**勾 Add a README file / Add .gitignore / Choose a license
   （勾了远程会先有一个提交，和本地冲突）
4. 可见性选 **Public**；若选 Private，需把老师加为协作者
5. 点 **Create repository**

页面下方会出现 ...or push an existing repository from the command line，复制那三行。

### 9.3 创建令牌

1. 右上头像 → **Settings**
2. 左侧最下方 → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. **Generate new token (classic)**
5. Note 填 smartworks；Expiration 选 90 days
6. 勾选 **repo**（即可覆盖仓库读写）
7. **Generate token**，复制 ghp_ 开头的字符串

> 令牌只显示一次，复制后先存到记事本。泄露了就在同一页面 Revoke 重新生成。

### 9.4 推送

在 SmartWorks 目录执行：

`ash
git remote add origin https://github.com/你的用户名/smartworks.git
git branch -M main
git push -u origin main
`

弹出认证窗口时：

| 字段 | 填什么 |
|---|---|
| Username | GitHub 用户名 |
| Password | **刚才生成的 PAT**，不是账号密码 |

成功后 Windows 凭据管理器会记住，以后 push 不再询问。

若之前配过别的远程，用：

`ash
git remote set-url origin https://github.com/你的用户名/smartworks.git
`

### 9.5 GitHub 常见故障

| 报错 | 原因 | 解决 |
|---|---|---|
| Failed to connect to github.com port 443 | 国内访问 GitHub 不稳 | 重试；开代理；或改用 Gitee |
| Authentication failed | 密码框填了账号密码 | 改用 PAT |
| 
emote origin already exists | 已配置过远程 | git remote set-url origin <新地址> |
| Updates were rejected | 远程有别人的提交 | git pull --rebase 后再 push |
| 网页上看不到中文文件名 | Git 转义中文 | git config --global core.quotepath false |

### 9.6 交接时要注意

学期末交作业给的是**仓库地址**。若仓库是 Private，必须：

1. 在仓库 **Settings → Collaborators** 里把老师账号加成协作者，或
2. 提前把仓库改为 Public

**别到最后一天才发现老师打不开。**
