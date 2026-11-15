# -*- coding: utf-8 -*-
"""一键生成业务数据：MPS -> 排产 -> 订单预测。

为什么单独一个文件而不是内联在 db_init.py 里：
  内联要处理三层引号（bat -> python -c -> 命令字符串），极易出错，
  而且没法单独调试。独立文件可以单独跑、单独测。
"""
import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(BACKEND, 'backend')
sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django                                                     # noqa: E402
django.setup()

from django.test import Client                                    # noqa: E402
from rest_framework.authtoken.models import Token                 # noqa: E402
from apps.core.models import User                                 # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')

c = Client(SERVER_NAME='127.0.0.1')
admin = User.objects.filter(username='admin').first() or User.objects.filter(
    username='demo').first()
if admin is None:
    print('  [跳过] 没有 admin 账号，先跑 init_core')
    sys.exit(1)

tok, _ = Token.objects.get_or_create(user=admin)
AUTH = {'HTTP_AUTHORIZATION': 'Token ' + tok.key}

ok, skip = [], []


def call(label, method, url, payload=None):
    try:
        if method == 'POST':
            r = c.post(url, data=json.dumps(payload or {}),
                       content_type='application/json', **AUTH)
        else:
            r = c.get(url, **AUTH)
        body = r.content.decode('utf-8', errors='replace')
        if r.status_code in (200, 201):
            print('  [完成] %-22s HTTP %s' % (label, r.status_code))
            ok.append(label)
            return json.loads(body).get('data')
        print('  [跳过] %-22s HTTP %s  %s' % (label, r.status_code, body[:90]))
        skip.append(label)
        return None
    except Exception as e:                                        # noqa: BLE001
        print('  [跳过] %-22s 异常 %s' % (label, str(e)[:80]))
        skip.append(label)
        return None


# 幂等守卫：MPS 与预测都是「有就跳过」。
# 没有守卫的话，每跑一次初始化就多一套 MPS + 4 张工单，
# 演示页面上会出现 4 条同名 MPS —— 实测踩过。
from apps.order.models import DemandForecast                       # noqa: E402
from apps.order.models import Mps as MpsModel                      # noqa: E402

PERIOD = '2026-11-16'

if MpsModel.objects.filter(period=PERIOD).exists():
    print('  [已有] %-22s 已存在 period=%s 的 MPS，跳过生成' % ('生成 MPS', PERIOD))
    skip.append('生成 MPS')
else:
    call('生成 MPS', 'POST', '/api/v1/order/mps/from-orders/', {'period': PERIOD})

# 2) 用该 MPS 跑排产（同一 MPS 已有方案就跳过）
from apps.planning.models import SchedulePlan                      # noqa: E402

mps_obj = MpsModel.objects.filter(period=PERIOD).order_by('-id').first()
if mps_obj is None:
    print('  [跳过] %-22s 没有 MPS' % '运行排产')
    skip.append('运行排产')
elif SchedulePlan.objects.filter(mps=mps_obj).exists():
    print('  [已有] %-22s 该 MPS 已有排产方案，跳过' % '运行排产')
    skip.append('运行排产')
else:
    call('运行排产', 'POST', '/api/v1/planning/schedule-plans/run/',
         {'mps_id': mps_obj.id})

# 3) 订单预测（已有记录就跳过）
if DemandForecast.objects.exists():
    print('  [已有] %-22s 已有 %d 条预测记录，跳过'
          % ('运行订单预测', DemandForecast.objects.count()))
    skip.append('运行订单预测')
else:
    call('运行订单预测', 'POST', '/api/v1/order/forecasts/run/', {})

# 4) AGV 调度演示（需要车是 idle）
from apps.logistics.models import Agv                              # noqa: E402
n = Agv.objects.update(status='idle')
if n:
    print('  已把 %d 台 AGV 置为空闲（调度演示的前提）' % n)

print()
print('  完成 %d 项，跳过 %d 项' % (len(ok), len(skip)))
if skip:
    print('  跳过的项可稍后在页面上手动操作，或对照 docs/demo-data-rebuild.md')
sys.exit(0)
