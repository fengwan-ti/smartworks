<template>
  <div class="sw-page">
    <el-alert
      title="Day 1 验收页"
      type="success"
      :closable="false"
      description="点下面三个按钮，验证统一响应体的三种形态。全部通过即 Day 1 完成。"
      show-icon
    />

    <div class="sw-card" style="margin-top: 16px">
      <div class="sw-toolbar">
        <el-button type="primary" @click="onSuccess">1. 验证成功响应</el-button>
        <el-button type="success" @click="onPaginated">2. 验证分页响应</el-button>
        <el-button type="danger" @click="onError">3. 验证异常响应</el-button>
      </div>

      <el-divider content-position="left">最近一次结果</el-divider>
      <pre class="result">{{ resultText }}</pre>

      <el-divider content-position="left">分页数据表格（BaseTable 组件示例）</el-divider>
      <BaseTable :columns="columns" :rows="rows" :total="total" @change="loadPage" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import BaseTable from '@/components/BaseTable.vue'
import { demoError, demoPaginated, demoSuccess } from '@/api/core'

const resultText = ref('尚未请求')
const rows = ref([])
const total = ref(0)
const columns = [
  { prop: 'id', label: 'ID', width: 90 },
  { prop: 'name', label: '名称' }
]

function show(title, payload) {
  resultText.value = `${title}\n${JSON.stringify(payload, null, 2)}`
}

async function onSuccess() {
  show('成功响应', await demoSuccess())
}

async function onError() {
  try {
    await demoError()
  } catch (e) {
    show('异常响应（已被 request.js 拦下并提示）', e)
  }
}

async function loadPage({ page, pageSize }) {
  const data = await demoPaginated({ page, page_size: pageSize })
  rows.value = data.results
  total.value = data.count
  show('分页响应', data)
}

async function onPaginated() {
  await loadPage({ page: 1, pageSize: 10 })
}

onMounted(() => {
  onPaginated()
})
</script>

<style scoped>
.result {
  margin: 0;
  padding: 12px;
  background: #0f172a;
  color: #d7e3ff;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
}
</style>
