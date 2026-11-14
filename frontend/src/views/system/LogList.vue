<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset" />

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="tip"
        title="操作日志是「谁在什么时候改了什么」的唯一凭据。日志只允许追加、不允许修改或删除，所以这一页是只读的。"
      />

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #action="{ row }">
          <el-tag size="small" effect="plain" class="mono">{{ row.action }}</el-tag>
        </template>
        <template #user="{ row }">
          {{ row.user_name || row.username || '—' }}
        </template>
        <template #detail="{ row }">
          <span class="mono detail">{{ stringify(row.detail) }}</span>
        </template>
      </BaseTable>
    </div>
  </div>
</template>

<script setup>
/**
 * 操作日志页（只读）。
 *
 * 答辩会被问：「怎么保证责任可追溯？」
 * 答：关键动作（登录、分配菜单、单据确认）都会写一条日志，
 *     日志只读，任何人不能改；本页就是它的可视化。
 */
import { onMounted, ref } from 'vue'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import request from '@/utils/request'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '动作 / 目标 / 用户名' },
  {
    prop: 'target_model',
    label: '目标模型',
    type: 'select',
    width: '200px',
    options: [
      { value: 'core.Role', label: 'core.Role 角色' },
      { value: 'core.User', label: 'core.User 用户' },
      { value: 'masterdata.Product', label: 'masterdata.Product 产品' }
    ]
  }
])

const columns = [
  { prop: 'created_at', label: '时间', width: 180 },
  { prop: 'action', label: '动作', width: 160, slot: 'action' },
  { prop: 'user', label: '操作人', width: 130, slot: 'user' },
  { prop: 'target_model', label: '目标模型', width: 180 },
  { prop: 'target_id', label: '目标 ID', width: 100 },
  { prop: 'detail', label: '详情', slot: 'detail' },
  { prop: 'ip', label: 'IP', width: 130 }
]

function stringify(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  try {
    const s = JSON.stringify(v)
    return s.length > 90 ? s.slice(0, 90) + '…' : s
  } catch (e) {
    return String(v)
  }
}

async function load() {
  loading.value = true
  try {
    const data = await request.get('/core/logs/', {
      params: { page: page.value, page_size: pageSize.value, ...query.value }
    })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[LogList] 加载日志失败', e)
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
  font-size: 12px;
}
.detail {
  color: #6b7280;
}
</style>
