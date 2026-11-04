"""库存应用总路由。挂载前缀：/api/v1/inventory/

⚠️ 这个文件由 D 建，因为成品仓接口要先能访问。
   C 的路由请**不要直接改这个文件**，按同样方式另建 urls_warehouse.py 再 include 一行：
       path('', include('apps.inventory.urls_warehouse')),
   原因：两人同时改同一个 urls.py，冲突会一直存在（和 models.py 拆文件是同一个理由）。
"""
from django.urls import include, path

urlpatterns = [
    # D：成品仓（成品入库、发货、库龄、周转）
    path('', include('apps.inventory.urls_finished')),
    # C：原料仓（仓库、库位、批次、采购入库、领料、台账、盘点）
    # path('', include('apps.inventory.urls_warehouse')),
]
