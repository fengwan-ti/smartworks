<template>
  <div class="d-page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <div>
            <div class="title">生产看板（W7）</div>
            <div class="sub">
              数据源：排产方案 / 工单工序状态 / C 的报工汇总（I-08）
              <span v-if="data && data.plan"> · 最新方案 {{ data.plan.code }}</span>
            </div>
          </div>
          <div class="actions">
            <el-button @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <template v-if="data">
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-num">{{ data.work_order_count }}</div><div class="kpi-label">工单总数</div></div>
          <div class="kpi" :class="{ warn: data.delayed_count > 0 }">
            <div class="kpi-num">{{ data.delayed_count }}</div><div class="kpi-label">延迟工单</div>
          </div>
          <div class="kpi">
            <div class="kpi-num">{{ data.operations.done }}/{{ data.operations.total }}</div>
            <div class="kpi-label">工序完成</div>
          </div>
          <div class="kpi">
            <div class="kpi-num">{{ data.reported.good_qty }}</div><div class="kpi-label">报工良品</div>
          </div>
          <div class="kpi">
            <div class="kpi-num">{{ data.reported.defect_qty }}</div><div class="kpi-label">报工不良</div>
          </div>
          <div class="kpi" v-if="data.plan">
            <div class="kpi-num">{{ data.plan.kpi.makespan_hours }}h</div>
            <div class="kpi-label">方案总跨度</div>
          </div>
          <div class="kpi" v-if="data.plan">
            <div class="kpi-num">{{ data.plan.kpi.on_time_rate }}%</div>
            <div class="kpi-label">方案准时率</div>
          </div>
        </div>

        <el-row :gutter="16">
          <el-col :span="16">
            <div class="card-sub-title">工单工序进度</div>
            <div ref="chartEl" class="chart"></div>
          </el-col>
          <el-col :span="8">
            <div class="card-sub-title">最新方案设备负荷</div>
            <el-table :data="loadRows" border size="small">
              <el-table-column prop="name" label="设备" />
              <el-table-column prop="load" label="负荷%" width="90" align="right" />
            </el-table>
            <div class="card-sub-title" style="margin-top: 16px">工单状态分布</div>
            <el-table :data="statusRows" border size="small">
              <el-table-column prop="label" label="状态" />
              <el-table-column prop="count" label="数量" width="80" align="right" />
            </el-table>
          </el-col>
        </el-row>

        <div class="card-sub-title">工单明细</div>
        <el-table :data="data.work_orders" border stripe size="small">
          <el-table-column prop="code" label="工单号" width="130" />
          <el-table-column prop="product_code" label="产品" width="120" />
          <el-table-column prop="qty" label="数量" width="90" align="right" />
          <el-table-column prop="due_date" label="交期" width="110" />
          <el-table-column prop="status_label" label="状态" width="90" />
          <el-table-column label="工序" width="90" align="center">
            <template #default="{ row }">{{ row.operations_done }}/{{ row.operations_total }}</template>
          </el-table-column>
          <el-table-column prop="good_qty" label="报工良品" width="100" align="right" />
          <el-table-column prop="defect_qty" label="不良" width="80" align="right" />
          <el-table-column label="延迟" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.delayed" size="small" type="danger">延迟</el-tag>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { fetchDashboard } from '@/api/planning'

const data = ref(null)
const chartEl = ref(null)
const loadRows = ref([])
const statusRows = ref([])
let chart = null

const STATUS_LABEL = {
  draft: '草稿', planned: '已排产', released: '已下达',
  in_production: '生产中', completed: '已完工', closed: '已关闭', cancelled: '已取消',
}

async function load() {
  data.value = await fetchDashboard()
  loadRows.value = Object.entries(data.value.plan?.kpi?.equipment_load || {}).map(
    ([id, load]) => ({ name: `设备#${id}`, load }),
  )
  statusRows.value = Object.entries(data.value.status_count || {}).map(
    ([k, v]) => ({ label: STATUS_LABEL[k] || k, count: v }),
  )
  await nextTick()
  render()
}

function render() {
  if (!chartEl.value || !data.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const rows = data.value.work_orders || []
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['已完成工序', '未完成工序'] },
    grid: { left: 40, right: 20, top: 40, bottom: 70 },
    xAxis: { type: 'category', data: rows.map((r) => r.code.slice(-4)), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '工序数' },
    series: [
      { name: '已完成工序', type: 'bar', stack: 'ops', data: rows.map((r) => r.operations_done),
        itemStyle: { color: '#67c23a' } },
      { name: '未完成工序', type: 'bar', stack: 'ops',
        data: rows.map((r) => Math.max(r.operations_total - r.operations_done, 0)),
        itemStyle: { color: '#e6a23c' } },
    ],
  })
}

function onResize() { chart && chart.resize() }
onMounted(() => { load(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.d-page { padding: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 16px; font-weight: 600; color: var(--sw-primary); }
.sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin: 6px 0 14px; }
.kpi { flex: 1; min-width: 110px; background: #f5f7fa; border-radius: 6px; padding: 8px 12px; }
.kpi.warn { background: #fef0f0; }
.kpi-num { font-size: 20px; font-weight: 600; color: var(--sw-primary); }
.kpi-label { font-size: 12px; color: #8a8f99; }
.card-sub-title { font-size: 13px; font-weight: 600; color: #606266; margin: 10px 0 6px; }
.chart { width: 100%; height: 300px; }
</style>
