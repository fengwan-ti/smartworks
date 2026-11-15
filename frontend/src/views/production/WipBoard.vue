<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset" />
      <BaseTable
        :columns="columns" :rows="rows" :total="total"
        :show-pagination="false"
      >
        <template #wip_qty="{ row }">
          <span class="wip-qty">{{ row.wip_qty }}</span>
        </template>
      </BaseTable>
    </div>
  </div>
</template>

<script setup>
/** 在制品监控 —— /production/wip/ 按工单+工序聚合报工（不依赖 B）。 */
import { onMounted, ref } from 'vue'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { listWip } from '@/api/production'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = ref({})

const searchFields = ref([
  { prop: 'work_order_id', label: '工单ID', type: 'input' }
])

const columns = [
  { prop: 'work_order_id', label: '工单ID', width: 120 },
  { prop: 'operation_seq', label: '工序序号', width: 100 },
  { prop: 'step_type', label: '最新工序类型', width: 140 },
  { prop: 'reported_qty', label: '累计报工', width: 110 },
  { prop: 'good_qty', label: '累计合格', width: 110 },
  { prop: 'defect_qty', label: '累计不良', width: 110 },
  { prop: 'wip_qty', label: '在制数量', width: 110, slot: 'wip_qty' },
  { prop: 'last_report_at', label: '最近报工', width: 170 }
]

async function load() {
  loading.value = true
  try {
    const data = await listWip({ ...query.value })
    rows.value = data.results || data || []
    total.value = rows.value.length
  } finally {
    loading.value = false
  }
}

function onSearch(params) {
  query.value = params
  load()
}
function onReset() {
  query.value = {}
  load()
}

onMounted(load)
</script>

<style scoped>
.wip-qty {
  font-weight: 700;
  color: var(--el-color-primary);
}
</style>
