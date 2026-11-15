# C 的 W5 全链联调指南（随 feature/c-apps 交付）

> 本文档对应 `backend/apps/inventory/management/commands/init_demo_c.py` 的演示数据。
> 全部命令在 `backend/` 目录下执行。

## 1. 启动（每人 5 分钟）

```bash
cd backend
# 装依赖（首次）
pip install -r ../requirements.lock
# 建库 + A 的主数据/菜单种子
python manage.py migrate
python manage.py init_demo        # A 的：主数据、车间工位、超管 demo/demo123
# C 的演示数据（批次/报工/检验/SPC/算法参数）
python manage.py init_demo_c
python manage.py runserver
```

登录账号（演示）：`demo / demo123`（A 的超管）或 `c1 / c12345678`（C 的演示号，需在前端登录页用）。

## 2. 全链冒烟（10 条，按顺序打，全绿即联调通过）

拿 token：`POST /api/v1/core/auth/login/ {"username":"c1","password":"c12345678"}`（以 A 的 core 路径为准），后续请求带 `Authorization: Token <token>`。

| # | 环节 | 请求 | 期望 |
|---|------|------|------|
| 1 | 库存可用量 | `GET /api/v1/inventory/stock/available/?material_ids=<M001_id>,<M002_id>` | M001=100.000 / M002=80.000 |
| 2 | FIFO 推荐 | `GET /api/v1/inventory/batches/fifo/?material=<M001_id>` | B20261101 在列 |
| 3 | 按工单领料 | `POST /api/v1/inventory/outbounds/from-work-order/ {"work_order_id":1,"warehouse":<WH01_id>,"items":[{"material":<M001_id>,"qty":"20.000"}]}` | 201，单号 LL 开头 |
| 4 | 领料出库确认 | `POST /api/v1/inventory/outbounds/<id>/confirm/` | 200，FIFO 扣 B20261101 |
| 5 | 可用量复核 | 重打 #1 | M001=80.000（扣了 20） |
| 6 | 报工汇总 | `GET /api/v1/production/reports/summary/?work_order_id=1` | cutting+milling 两工序，good 合计 95 |
| 7 | 撤销报工 | `POST /api/v1/production/reports/<id>/revoke/` | 200（仅当天） |
| 8 | 逆向追溯 | `POST /api/v1/production/traceability/reverse/ {"batch_no":"FG20261101"}` | 返回 direction=reverse |
| 9 | SPC 真 CpK | `GET /api/v1/quality/spc/?item_id=<QS-DEMO-001 的检验项 id>` | cp≈1.28 / cpk≈1.25，usl=50.05，lsl=49.95 |
| 10 | 算法参数 | `GET /api/v1/quality/algorithm-params/T4_SURFACE_DEFECT/` 后 `PUT` 改 `area_threshold`，再 `POST /api/v1/quality/vision/detect/` 传图 | 改参数后框数变化，说明读库生效 |

抽样方案（B 建 I-08/09 mock 后联调时用）：`GET /api/v1/quality/sampling/?lot_qty=500&aql=1.0` → H 码 / n=50 / Ac=1。

## 3. 交接给 D 的两句话

- 成品入库/发货**必须调** `apps.inventory.services.write_stock_transaction(batch, biz_type, qty, ref_doc=...)`，不要自己 INSERT 流水表（biz_type 取 inbound/issue/return/adjust/ship）。
- 演示成品批次 `FG20261101`（product=P001）已备好，供你测 `/production/traceability/reverse/`。

## 4. 联调口径（群里有异议按此裁决）

1. `Batch.source_type` 当前取 `purchase/production`（A 的骨架口径）；D 若坚持 `produce`，改后要同步 `in_batch` 约束与 D 的写库代码——**改前必须群拍板**。
2. 成品入库接口归属（A 契约 `/inventory/finished-inbounds/` 归 D vs 与 D v2 约定 `/inventory/inbounds/from-work-order/` 归 C）——联调用 A 契约路径，归属争议 W5 后再清。
3. 判定结论唯一读 `Inspection.status`；D 侧校验类名必须 import `apps.quality.models.Inspection`（不是 InspectionOrder）。

## 5. 常见坑

- 测试/演示前先 `migrate`（quality.0003_algorithmparam 是本分支新增）。
- `init_demo_c` 幂等，可反复跑；测量值缺失会自动补。
- 报工撤销只允许当天（测试里有覆盖）；工序 start/complete 在 B 的 planning 未合入前返回 13050，属预期降级。
