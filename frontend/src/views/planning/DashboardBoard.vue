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

        <el-row :gutter="16" class="mini-row">
          <el-col :span="8">
            <el-card shadow="never" class="mini-card">
              <div class="card-sub-title">延迟工单</div>
              <template v-if="data.delayed_work_orders.length">
                <div v-for="w in data.delayed_work_orders.slice(0, 5)" :key="w.code" class="mini-line">
                  <el-tag size="small" type="danger">延迟</el-tag>
                  <span>{{ w.code }} · {{ w.product_code }}</span>
                  <span class="mini-sub">交期 {{ w.due_date }}</span>
                </div>
              </template>
              <el-empty v-else description="没有延迟工单" :image-size="46" />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="never" class="mini-card">
              <div class="card-sub-title">瓶颈设备（单台覆盖工序）</div>
              <el-table :data="data.bottlenecks" border size="small" v-if="data.bottlenecks.length">
                <el-table-column prop="label" label="工序" width="80" />
                <el-table-column prop="equipment" label="设备" width="110" />
                <el-table-column prop="capacity_per_hour" label="件/h" width="70" align="right" />
                <el-table-column label="负荷" width="70" align="right">
                  <template #default="{ row }">{{ row.load == null ? '—' : row.load + '%' }}</template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="没有单台瓶颈" :image-size="46" />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="never" class="mini-card">
              <div class="card-sub-title">齐套状态（最近一次检查）</div>
              <template v-if="data.kit">
                <div class="mini-line"><b>{{ data.kit.mps_code }}</b></div>
                <el-tag :type="data.kit.ready ? 'success' : 'danger'" size="small">
                  {{ data.kit.ready ? '齐套' : '缺料 ' + data.kit.shortage_count + ' 项' }}
                </el-tag>
                <span class="mini-sub" v-if="data.kit.checked_at">{{ data.kit.checked_at.slice(0, 19) }}</span>
              </template>
              <el-empty v-else description="还没有做过齐套检查" :image-size="46" />
            </el-card>
          </el-col>
        </el-row>

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
import { usePolling } from '@/composables/usePolling'
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
// 生产看板常挂在车间大屏上，60 秒刷一次（比告警慢，因为工单变化没那么频繁）
usePolling(load, 60000)

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
.mini-row { margin-bottom: 8px; }
.mini-card { min-height: 150px; }
.mini-line { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; font-size: 13px; }
.mini-sub { margin-left: auto; font-size: 12px; color: #8a8f99; }
.kpi { flex: 1; min-width: 110px; background: #f5f7fa; border-radius: 6px; padding: 8px 12px; }
.kpi.warn { background: #fef0f0; }
.kpi-num { font-size: 20px; font-weight: 600; color: var(--sw-primary); }
.kpi-label { font-size: 12px; color: #8a8f99; }
.card-sub-title { font-size: 13px; font-weight: 600; color: #606266; margin: 10px 0 6px; }
.chart { width: 100%; height: 300px; }
</style>
