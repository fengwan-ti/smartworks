<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset" />

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="tip"
        title="数据字典是全系统的「统一取值」来源：工单状态、设备状态、工序类型、换型来源等都从这里取。前端不写死选项，改字典即改全局。"
      />

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #type="{ row }">
          <el-tag size="small" effect="plain" class="mono">{{ row.dict_type }}</el-tag>
        </template>
        <template #status="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </BaseTable>
    </div>
  </div>
</template>

<script setup>
/**
 * 数据字典页（只读）。
 *
 * 为什么只读：字典属于配置数据，改错会影响全系统取值。
 * 第一代通过 Django Admin 维护（/admin/core/datadict/），这里只做查询对照。
 */
import { onMounted, ref } from 'vue'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { listDicts } from '@/api/core'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '类型 / 编码 / 名称' },
  {
    prop: 'dict_type',
    label: '字典类型',
    type: 'select',
    options: [
      { value: 'work_order_status', label: 'work_order_status 工单状态' },
      { value: 'anomaly_type', label: 'anomaly_type 异常类型' },
      { value: 'equipment_status', label: 'equipment_status 设备状态' },
      { value: 'step_type', label: 'step_type 工序类型' },
      { value: 'route_status', label: 'route_status 路线状态' },
      { value: 'bom_status', label: 'bom_status BOM 状态' },
      { value: 'changeover_source', label: 'changeover_source 换型来源' }
    ],
    width: '260px'
  }
])

const columns = [
  { prop: 'dict_type', label: '字典类型', width: 220, slot: 'type' },
  { prop: 'dict_code', label: '编码', width: 180 },
  { prop: 'dict_name', label: '名称' },
  { prop: 'sort', label: '排序', width: 80 },
  { prop: 'is_active', label: '状态', width: 100, slot: 'status' }
]

async function load() {
  loading.value = true
  try {
    const data = await listDicts({
      page: page.value,
      page_size: pageSize.value,
      ...query.value
    })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[DictList] 加载字典失败', e)
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
  page.value = 1
  load()
}
function onPageChange({ page: p, pageSize: s }) {
  page.value = p
  pageSize.value = s
  load()
}

onMounted(load)
</script>

<style scoped>
.tip {
  margin: 4px 0 14px;
}
.mono {
  font-family: Consolas, Monaco, monospace;
}
</style>
