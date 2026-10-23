"""主数据后台。

为什么主数据不写页面而用 Admin：
  主数据是低频维护的字典数据，字段固定、无复杂流程。
  Django Admin 自带列表、搜索、筛选、表单校验、导入导出，
  直接用它可以把省下的时间投到真正需要自定义界面的业务模块上。
  需要给业务人员用的少数页面（如产品管理）再单独做，见 frontend/views/masterdata。
"""
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import (
    Customer,
    Material,
    Product,
    ProductFamily,
    Supplier,
    Workshop,
    Workstation,
)


class BaseAdmin(ImportExportModelAdmin):
    """带 Excel 导入导出能力的基类。"""
    list_per_page = 30


@admin.register(ProductFamily)
class ProductFamilyAdmin(BaseAdmin):
    list_display = ('code', 'name', 'is_active', 'remark')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)


@admin.register(Material)
class MaterialAdmin(BaseAdmin):
    list_display = ('code', 'name', 'spec', 'category', 'uom', 'safety_stock', 'is_active')
    search_fields = ('code', 'name', 'spec')
    list_filter = ('category', 'is_active')


@admin.register(Product)
class ProductAdmin(BaseAdmin):
    list_display = ('code', 'name', 'drawing_no', 'family', 'material', 'uom',
                    'std_cost', 'is_active')
    search_fields = ('code', 'name', 'drawing_no')
    list_filter = ('family', 'is_active')
    autocomplete_fields = ('family', 'material')


@admin.register(Customer)
class CustomerAdmin(BaseAdmin):
    list_display = ('code', 'name', 'contact', 'phone', 'is_active')
    search_fields = ('code', 'name', 'contact')


@admin.register(Supplier)
class SupplierAdmin(BaseAdmin):
    list_display = ('code', 'name', 'contact', 'phone', 'is_active')
    search_fields = ('code', 'name', 'contact')


@admin.register(Workshop)
class WorkshopAdmin(BaseAdmin):
    list_display = ('code', 'name', 'is_active')


@admin.register(Workstation)
class WorkstationAdmin(BaseAdmin):
    list_display = ('code', 'name', 'workshop', 'agv_load_point', 'is_active')
    search_fields = ('code', 'name', 'agv_load_point')
    list_filter = ('workshop', 'is_active')
