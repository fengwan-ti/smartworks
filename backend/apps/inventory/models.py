"""库存应用模型入口。

⚠️ 这个文件只做汇总，不要在这里写模型。

为什么拆分：Django 一个应用只有一个 models.py，而原料仓归 C、成品仓归 D。
两人同时改同一个文件会让 makemigrations 互相覆盖，迁移历史直接乱掉。
拆成两个文件后，各改各的，互不影响。

  models_warehouse.py   C 负责 —— 仓库、库位、批次、库存流水、原料出入库
  models_finished.py    D 负责 —— 成品入库单、发货出库单

改动规则：
  1. 只改自己那个文件
  2. 改完跑 makemigrations inventory，迁移文件会自动生成
  3. 提交前确认迁移文件里只有自己的表
"""
from .models_finished import *      # noqa: F401,F403
from .models_warehouse import *     # noqa: F401,F403
