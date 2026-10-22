# SmartWorks 智能车间感知分析与决策平台

面向中小型离散机加工车间的生产管理平台。第一代覆盖原料仓储 → 生产加工 → 质量检验 → 成品仓储 → 订单排产的全流程，
并把课程要求的七项算法任务做成系统中可用的功能模块。

> 本文件是团队唯一的启动说明书。换电脑、换人，都从这份文件开始。

## 一、技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 后端 | Django + Django REST Framework | Django 5.x / DRF 3.15 |
| 数据库 | PostgreSQL（演示可回退 SQLite） | 16.x |
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Axios + ECharts | 见 package.json |
| 算法 | OpenCV / scikit-learn / statsmodels / networkx / PuLP | 见 requirements-ml.txt |

## 二、目录结构

```
SmartWorks/
├── backend/          Django 后端
│   ├── config/       项目配置（settings、总路由）
│   └── apps/         12 个业务应用 + integration
├── frontend/         Vue 3 前端
│   └── src/          api / views / components / charts / layouts / router / store / utils
├── docs/             项目文档（接口契约、ER 图、AI 使用记录、非目标清单）
└── scripts/          0/1/2/3/4 五个双击式 .bat（纯批处理，不用 PowerShell）
```

## 三、快速开始（Windows · 不用打命令）

> 全部操作都是**双击**。只有第一次需要装两个软件。

### 前置：装两个软件（只一次）

| 软件 | 地址 | 注意 |
|---|---|---|
| Git | https://git-scm.com/download/win | 一路 Next 即可 |
| Node.js | https://nodejs.org/ | 选 **LTS** 版本，一路 Next |

Python 已装（3.13.7），不用再装。

装完**重启电脑**（或至少关掉所有窗口重开），让系统认到新软件。

### 然后：双击四个文件，按顺序

打开文件夹 `SmartWorks\scripts`，依次双击：

| 顺序 | 双击 | 干什么 | 大概多久 | 成功标志 |
|---|---|---|---|---|
| 0 | `0-环境自检.bat` | 检查 Git / Node / Python 有没有装好 | 5 秒 | 三项都显示版本号 |
| 1 | `1-安装依赖.bat` | 装后端和前端需要的几十个库 | 5~15 分钟 | 最后显示"装好了" |
| 2 | `2-初始化数据库.bat` | 建表 + 创建管理员账号 | 10 秒 | 显示"初始化完成" |
| 3 | `3-启动系统.bat` | 启动系统并自动打开浏览器 | 20 秒 | 浏览器自动弹出登录页 |

### 登录

账号 `admin`　密码 `admin123`

### 改了代码想保存到远程仓库

双击 4-提交并推送.bat：

1. 它会列出你改了哪些文件
2. 让你输入一句说明（直接回车用默认的）
3. 自动完成 暂存 → 提交 → 拉取 → 推送

首次使用会问你要仓库地址，从浏览器仓库页面复制粘贴进去即可。

### 关闭系统

第 3 步会弹出**两个黑窗口**，都关掉就等于关闭系统。

### 出错了怎么办

**不要自己改代码。** 把出错的窗口整屏截图发群里，由 A 统一处理。

常见情况见第五章。

## 四、Day 1 验收标准（统一响应体）

打开 Swagger 或浏览器访问下面三个地址，必须分别得到成功、分页、异常三种结构：

| 地址 | 期望 |
|---|---|
| `/api/v1/core/_demo/success/` | `{"code":0,"message":"ok","data":{...}}` |
| `/api/v1/core/_demo/paginated/` | `data` 内为 `{"count":..,"page":..,"page_size":..,"results":[..]}` |
| `/api/v1/core/_demo/error/` | HTTP 400，`{"code":10001,"message":"工单数量必须大于 0","data":null}` |

前端登录页用 admin/admin123 登录后，进入工作台，页面上有三个按钮可触发同样三种响应。

## 五、给协作成员的约定

1. 所有接口返回统一响应体，**任何人不得自行实现包装逻辑**（由 `apps/core/renderers.py` 与 `exceptions.py` 统一处理）。
2. 业务逻辑写在 `services.py`，不写在 `views.py`。
3. 改接口前先改 `docs/api-contract.md`，再改代码。
4. 每次使用 AI 助手后，在 `docs/AI使用记录.md` 追加一条记录。
5. 详细约定见《AI 协作与角色工作包》第 2 章。

## 六、常见问题

- **前端请求报 CORS**：确认后端 `CORS_ALLOW_ALL_ORIGINS = True`（仅开发环境）。
- **数据库连不上**：把 `.env` 里 `DB_ENGINE` 改为 `sqlite`，先跑通再说。
- **npm 装不上**：脚本已自动切国内镜像；仍失败说明网络问题，找 A 要离线包。
- **双击 .bat 一闪就没了**：通常是前面某步没装好，先跑 `0-环境自检.bat` 看结果。
- **提示找不到 python**：Python 安装时没勾 Add to PATH，重装并勾选。
- **浏览器打不开页面**：先确认两个黑窗口还开着；再确认地址是 `http://localhost:5173`。
