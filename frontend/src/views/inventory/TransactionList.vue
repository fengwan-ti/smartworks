<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset" />
      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #biz_type="{ row }">
          <el-tag size="small" :type="bizTypeMap[row.biz_type]?.type || 'info'">
            {{ bizTypeMap[row.biz_type]?.label || row.biz_type }}
          </el-tag>
        </template>
        <template #qty="{ row }">
          <span :style="{ color: row.qty < 0 ? 'var(--el-color-danger)' : 'var(--el-color-success)' }">
            {{ row.qty > 0 ? `+${row.qty}` : row.qty }}
          </span>
        </template>
      </BaseTable>
    </div>
  </div>
</template>

<script setup>
/** 库存流水 —— in_stock_transaction，只读。biz_type: inbound/issue/return/adjust/ship。 */
import { onMounted, ref } from 'vue'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { listStockTransactions, warehouseOptions } from '@/api/inventory'

const bizTypeMap = {
  inbound: { label: '入库', type: 'success' },
  issue: { label: '领用', type: 'danger' },
  return: { label: '退料', type: 'warning' },
  adjust: { label: '盘点调整', type: 'info' },
  ship: { label: '发货', type: 'primary' }
}

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '批次号/单据号' },
  { prop: 'biz_type', label: '业务类型', type: 'select',
    options: Object.entries(bizTypeMap).map(([value, v]) => ({ value, label: v.label })) },
  { prop: 'warehouse', label: '仓库', type: 'select', options: [] },
  { prop: 'created_at', label: '发生日期', type: 'daterange' }
])

const columns = [
  { prop: 'created_at', label: '发生时间', width: 170 },
  { prop: 'batch_no', label: '批次号', width: 130 },
  { prop: 'material_name', label: '物料' },
  { prop: 'biz_type', label: '业务类型', width: 100, slot: 'biz_type' },
  { prop: 'qty', label: '数量', width: 100, slot: 'qty' },
  { prop: 'warehouse_name', label: '仓库', width: 120 },
  { prop: 'location_code', label: '库位', width: 100 },
  { prop: 'ref_doc', label: '来源单据', width: 140 },
  { prop: 'operator_name', label: '操作人', width: 100 }
]

async function load() {
  loading.value = true
  try {
    const data = await listStockTransactions({ page: page.value, page_size: pageSize.value, ...query.value })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

function onSearch(params) {
  query.value = params
  page.value = 1
  load()
}
function onReset() {
  query.value = {}
}
function onPageChange({ page: p, pageSize: s }) {
  page.value = p
  pageSize.value = s
  load()
}

onMounted(async () => {
  load()
  const ws = await warehouseOptions()
  searchFields.value[2].options = ws.map((o) => ({ value: o.id, label: o.name }))
})
</script>
