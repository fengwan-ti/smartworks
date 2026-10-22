# Git 协作指南

> 四个人改同一个仓库。不按这份流程走，一定会在某一天把别人的代码覆盖掉。

## 一、第一次：把仓库推到远程（组长做一次）

GitHub 在国内访问慢，建议用 **Gitee**。

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
