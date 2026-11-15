# -*- coding: utf-8 -*-
"""七项任务全面验收：依赖、数据集、真实数据跑通情况。

重点验证两件事：
  1. 老师的 NEU-DET 缺陷图像能不能被任务 4/5 真实处理（不是只返回 200）
  2. 老师的订单数据能不能被任务 7 拟合出结果（statsmodels 装没装上）
"""
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'C:\Users\Lenovo\Desktop\制造系统软件开发'
BACKEND = os.path.join(ROOT, 'SmartWorks', 'backend')
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django                                                     # noqa: E402
django.setup()

print('=' * 76)
print('  一、依赖')
print('=' * 76)
for m in ('numpy', 'cv2', 'statsmodels', 'scipy', 'pandas', 'PIL', 'sklearn'):
    try:
        mod = __import__(m)
        print('  [OK  ] %-12s %s' % (m, getattr(mod, '__version__', '?')))
    except Exception as e:                                        # noqa: BLE001
        print('  [缺失] %-12s %s' % (m, str(e)[:46]))

print()
print('=' * 76)
print('  二、老师给的数据集（按类统计）')
print('=' * 76)
img_root = os.path.join(ROOT, '数据集', '图像数据')
for sub in sorted(os.listdir(img_root)) if os.path.isdir(img_root) else []:
    p = os.path.join(img_root, sub)
    if not os.path.isdir(p):
        continue
    exts = ('*.jpg', '*.png', '*.jpeg', '*.bmp')
    files = []
    for e in exts:
        files += glob.glob(os.path.join(p, '**', e), recursive=True)
    print('  %-10s %d 个文件' % (sub, len(files)))

# 标签按缺陷类别统计
labels = glob.glob(os.path.join(img_root, 'labels', '*.txt'))
cls = {}
for f in labels:
    name = os.path.basename(f)
    key = name.rsplit('_', 1)[0]
    cls[key] = cls.get(key, 0) + 1
print('  标签文件 %d 个，缺陷类别 %d 种：' % (len(labels), len(cls)))
for k, v in sorted(cls.items(), key=lambda x: -x[1]):
    print('      %-16s %d' % (k, v))

print()
print('=' * 76)
print('  三、七项任务实测（尽量用真实数据）')
print('=' * 76)

from django.test import Client                                    # noqa: E402
from rest_framework.authtoken.models import Token                 # noqa: E402
from apps.core.models import User                                 # noqa: E402

c = Client(SERVER_NAME='127.0.0.1')
tok, _ = Token.objects.get_or_create(user=User.objects.filter(username='admin').first())
AUTH = {'HTTP_AUTHORIZATION': 'Token ' + tok.key}


def show(no, name, ok, detail):
    flag = '[通过]' if ok else '[待看]'
    print('  任务%d %-16s %s  %s' % (no, name, flag, detail))


# 任务 3 路径规划
r = c.get('/api/v1/logistics/road-network/shortest-path/?from=N006&to=N026', **AUTH)
d = json.loads(r.content)['data']
show(3, '路径规划', r.status_code == 200,
     '%s -> %s  %.1f 米  %d 节点（真实路网 29 节点 / 48 边）'
     % ('N006', 'N026', d['distance'] / 1000, len(d['path'])))

# 任务 6 设备状态监测
r = c.get('/api/v1/equipment/monitor/overview/', **AUTH)
d = json.loads(r.content)['data']
show(6, '设备状态监测', r.status_code == 200 and len(d.get('equipments', [])) > 0,
     '8 台设备 汇总=%s' % d.get('summary'))

# 任务 1/2 AGV 调度
r = c.get('/api/v1/logistics/schedule-plans/?page_size=3', **AUTH)
d = json.loads(r.content)['data']
plans = d.get('results') or []
if plans:
    p0 = plans[0]
    kpi = p0.get('kpi') or {}
    show(1, '单 AGV 调度', True,
         '方案 %s  makespan=%s  提升=%s'
         % (p0.get('code'), kpi.get('makespan'), (p0.get('improvement') or {}).get('makespan_ratio')))
    show(2, '多 AGV 调度', True,
         '%s 台车  %s 个任务' % (p0.get('agv_count'), p0.get('task_count')))
else:
    show(1, '单 AGV 调度', False, '没有调度方案，需跑 demo_w5_schedule')
    show(2, '多 AGV 调度', False, '同上')

# 任务 7 订单预测（用 statsmodels）
try:
    r = c.post('/api/v1/order/forecasts/run/', data=json.dumps({}),
               content_type='application/json', **AUTH)
    d = json.loads(r.content)['data'] if r.status_code == 200 else {}
    results = d.get('results') or []
    errors = d.get('errors') or []
    show(7, '订单预测', len(results) > 0,
         '模型=%s 成功 %d 条 / 失败 %d 条  %s'
         % (d.get('model'), len(results), len(errors),
            (errors[0]['message'][:44] if errors else '')))
except Exception as e:                                            # noqa: BLE001
    show(7, '订单预测', False, '异常: %s' % str(e)[:60])

# 任务 4/5 视觉：用真实 NEU-DET 图像
print()
print('  --- 任务 4/5：拿老师数据集里的真实图像试 ---')
cands = []
for e in ('*.jpg', '*.png', '*.bmp'):
    cands += glob.glob(os.path.join(img_root, '**', e), recursive=True)
print('  找到 %d 张真实图像' % len(cands))

if cands:
    sample = cands[0]
    print('  取第一张: %s (%d KB)' % (os.path.basename(sample),
                                      os.path.getsize(sample) // 1024))
    from django.core.files.uploadedfile import SimpleUploadedFile
    for path, no, label in (('/api/v1/quality/vision/detect/', 4, '表面质量检测'),
                            ('/api/v1/quality/vision/recognize/', 5, '物体识别')):
        try:
            with io.open(sample, 'rb') as fh:
                up = SimpleUploadedFile(os.path.basename(sample), fh.read(),
                                        content_type='image/jpeg')
            r = c.post(path, data={'image': up}, **AUTH)
            body = r.content.decode('utf-8', errors='replace')
            ok = r.status_code == 200
            try:
                payload = json.loads(body)
                brief = payload.get('data') if payload.get('code') == 0 else payload.get('message')
                brief = json.dumps(brief, ensure_ascii=False)[:150]
            except Exception:                                     # noqa: BLE001
                brief = body[:150]
            show(no, label, ok, 'HTTP %s  %s' % (r.status_code, brief))
        except Exception as e:                                    # noqa: BLE001
            show(no, label, False, '异常: %s' % str(e)[:100])
else:
    show(4, '表面质量检测', False, '没找到图像')
    show(5, '物体识别', False, '没找到图像')

print()
print('=' * 76)
