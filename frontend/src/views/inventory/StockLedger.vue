<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset" />
      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #source_type="{ row }">
          <el-tag size="small" :type="row.source_type === 'production' ? 'success' : 'warning'">
            {{ row.source_type === 'production' ? '生产' : '采购' }}
          </el-tag>
        </template>
        <template #expire_date="{ row }">
          <span :class="{ 'sw-danger': isExpired(row.expire_date) }">{{ row.expire_date || '—' }}</span>
        </template>
      </BaseTable>
    </div>
  </div>
</template>

<script setup>
/** 库存台账 —— /inventory/stock/ 只读聚合（批次维度可用量）。 */
import { onMounted, ref } from 'vue'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { listStock, warehouseOptions } from '@/api/inventory'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '批次号/物料' },
  { prop: 'warehouse', label: '仓库', type: 'select', options: [] },
  {
    prop: 'source_type', label: '来源', type: 'select',
    options: [
      { value: 'purchase', label: '采购' },
      { value: 'production', label: '生产' }
    ]
  }
])

const columns = [
  { prop: 'batch_no', label: '批次号', width: 140 },
  { prop: 'material_name', label: '物料' },
  { prop: 'warehouse_name', label: '仓库', width: 120 },
  { prop: 'location_code', label: '库位', width: 110 },
  { prop: 'qty', label: '在库数量', width: 110 },
  { prop: 'available_qty', label: '可用数量', width: 110 },
  { prop: 'source_type', label: '来源', width: 80, slot: 'source_type' },
  { prop: 'in_date', label: '入库日期', width: 110 },
  { prop: 'expire_date', label: '有效期至', width: 110, slot: 'expire_date' }
]

function isExpired(dateStr) {
  return dateStr && new Date(dateStr) < new Date()
}

async function load() {
  loading.value = true
  try {
    const data = await listStock({ page: page.value, page_size: pageSize.value, ...query.value })
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
  searchFields.value[1].options = ws.map((o) => ({ value: o.id, label: o.name }))
})
</script>

<style scoped>
.sw-danger {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
