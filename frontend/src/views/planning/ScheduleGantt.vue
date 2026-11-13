<template>
  <div class="p-page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <div>
            <div class="title">排产方案与甘特图</div>
            <div class="sub">规则版：交期优先 → 最早可用设备 → 换型矩阵加换型时间；下料/检验不占设备</div>
          </div>
          <div class="actions">
            <el-select v-model="mpsId" placeholder="选择 MPS" style="width: 190px">
              <el-option v-for="m in mpsList" :key="m.id" :label="`${m.code}（${m.period}）`" :value="m.id" />
            </el-select>
            <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" placeholder="计划起始" style="width: 140px" />
            <el-button type="primary" :loading="running" @click="run">运行排产</el-button>
            <el-button @click="loadLatest">刷新</el-button>
          </div>
        </div>
      </template>

      <template v-if="plan">
        <div class="kpi-row">
          <div class="kpi"><div class="kpi-num">{{ plan.kpi.work_order_count ?? '-' }}</div><div class="kpi-label">工单数</div></div>
          <div class="kpi"><div class="kpi-num">{{ plan.kpi.operation_count ?? '-' }}</div><div class="kpi-label">工序数</div></div>
          <div class="kpi"><div class="kpi-num">{{ plan.kpi.changeover_count ?? '-' }}</div><div class="kpi-label">换型次数</div></div>
          <div class="kpi"><div class="kpi-num">{{ plan.kpi.on_time_rate ?? '-' }}%</div><div class="kpi-label">准时率</div></div>
          <div class="kpi"><div class="kpi-num">{{ plan.kpi.makespan_hours ?? '-' }}h</div><div class="kpi-label">总跨度</div></div>
          <div class="kpi"><div class="kpi-num">{{ plan.kpi.equipment_used ?? '-' }}</div><div class="kpi-label">使用设备</div></div>
        </div>
        <el-alert v-if="plan.kpi.warnings && plan.kpi.warnings.length" type="warning" :closable="false" show-icon
          :title="plan.kpi.warnings.join('；')" style="margin-bottom: 10px" />

        <div class="plan-line">
          方案：<b>{{ plan.code }}</b> · {{ plan.name }} · 状态 {{ plan.status }} · 起始 {{ plan.start_at }}
          <el-button v-if="plan.status === 'draft'" link type="primary" @click="confirmPlanRow">确认方案</el-button>
        </div>

        <div ref="chartEl" class="gantt"></div>

        <div class="bottom-grid">
          <div>
            <el-divider content-position="left">工单</el-divider>
            <el-table :data="workOrders" border size="small">
              <el-table-column prop="code" label="工单号" width="130" />
              <el-table-column prop="product_code" label="产品" width="120" />
              <el-table-column prop="qty" label="数量" width="90" align="right" />
              <el-table-column prop="due_date" label="交期" width="110" />
              <el-table-column prop="status" label="状态" width="90" />
              <el-table-column label="计划" min-width="180">
                <template #default="{ row }">{{ fmt(row.plan_start) }} → {{ fmt(row.plan_end) }}</template>
              </el-table-column>
            </el-table>
          </div>
          <div>
            <el-divider content-position="left">设备负荷</el-divider>
            <el-table :data="loadRows" border size="small">
              <el-table-column prop="name" label="设备" />
              <el-table-column prop="load" label="负荷%" width="100" align="right">
                <template #default="{ row }">{{ row.load }}%</template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>
      <el-empty v-else description="选择 MPS 后点“运行排产”，或先到订单模块生成 MPS" />
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { fetchMpsList } from '@/api/order'
import {
  confirmPlan, fetchEquipments, fetchPlanGantt, fetchPlans, runSchedule,
  fetchWorkOrders,
} from '@/api/planning'

const COLORS = {
  cutting: '#909399', rough_turning: '#409eff', finish_turning: '#79bbff',
  milling: '#67c23a', slot_milling: '#95d475', gear_milling: '#b88230',
  drilling: '#e6a23c', grinding: '#f56c6c', deburring: '#d4a017',
  cleaning: '#17b3a3', inspection: '#9254de',
}
const STEP_LABEL = {
  cutting: '下料', rough_turning: '粗车', finish_turning: '精车', milling: '铣削',
  slot_milling: '铣槽', gear_milling: '滚齿', drilling: '钻孔', grinding: '磨削',
  deburring: '去毛刺', cleaning: '清洗', inspection: '检验',
}

const mpsList = ref([])
const mpsId = ref(null)
const startDate = ref(new Date().toISOString().slice(0, 10))
const running = ref(false)
const plan = ref(null)
const bars = ref([])
const workOrders = ref([])
const loadRows = ref([])
const chartEl = ref(null)
let chart = null

function fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' }

async function loadMps() {
  const data = await fetchMpsList({ page: 1, page_size: 50 })
  mpsList.value = data.results || []
  if (!mpsId.value && mpsList.value.length) mpsId.value = mpsList.value[0].id
}

async function run() {
  if (!mpsId.value) { ElMessage.warning('请先选择 MPS'); return }
  running.value = true
  try {
    const startAt = `${startDate.value}T08:00:00+08:00`
    const created = await runSchedule({ mps_id: mpsId.value, start_at: startAt })
    ElMessage.success(`已生成方案 ${created.code}`)
    await showPlan(created)
  } finally { running.value = false }
}

async function loadLatest() {
  const data = await fetchPlans({ page: 1, page_size: 1 })
  const latest = (data.results || [])[0]
  if (latest) await showPlan(latest)
  else ElMessage.info('还没有排产方案，先点“运行排产”')
}

async function showPlan(p) {
  plan.value = p
  const [gantt, wos, eqs] = await Promise.all([
    fetchPlanGantt(p.id),
    fetchWorkOrders({ page: 1, page_size: 100, mps: p.mps }),
    fetchEquipments({ page: 1, page_size: 100 }),
  ])
  bars.value = gantt.bars || []
  workOrders.value = wos.results || []
  const eqMap = {}
  for (const e of (eqs.results || eqs || [])) eqMap[e.id] = e.code
  loadRows.value = Object.entries(p.kpi.equipment_load || {}).map(([id, load]) => ({
    name: eqMap[id] || `设备#${id}`, load,
  }))
  await nextTick()
  renderChart()
}

function renderChart() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const rows = [...new Set(bars.value.map((b) => b.work_order))]
  const data = bars.value.map((b) => ({
    name: `${b.work_order} ${STEP_LABEL[b.step_type] || b.step_type}`,
    value: [rows.indexOf(b.work_order), new Date(b.start).getTime(), new Date(b.end).getTime()],
    itemStyle: { color: COLORS[b.step_type] || '#409eff' },
    detail: b,
  }))
  chart.setOption({
    tooltip: {
      formatter: (p) => {
        const b = p.data.detail
        return `${b.work_order} · ${b.product} ${b.product_name}<br/>`
          + `#${b.seq} ${STEP_LABEL[b.step_type] || b.step_type} ${b.step_label ? '· ' + b.step_label : ''}<br/>`
          + `设备：${b.equipment || '不占设备'}<br/>`
          + `${fmt(b.start)} → ${fmt(b.end)}${b.changeover_minutes ? '（含换型 ' + b.changeover_minutes + ' 分）' : ''}`
      },
    },
    grid: { left: 120, right: 24, top: 20, bottom: 40 },
    xAxis: { type: 'time', axisLabel: { formatter: (v) => fmt(new Date(v).toISOString()) } },
    yAxis: { type: 'category', data: rows, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'custom',
      renderItem: (params, api) => {
        const y = api.value(0)
        const start = api.coord([api.value(1), y])
        const end = api.coord([api.value(2), y])
        const height = api.size([0, 1])[1] * 0.55
        return {
          type: 'rect',
          shape: { x: start[0], y: start[1] - height / 2, width: Math.max(end[0] - start[0], 2), height },
          style: api.style(),
        }
      },
      encode: { x: [1, 2], y: 0 },
      data,
    }],
  })
}

async function confirmPlanRow() {
  plan.value = await confirmPlan(plan.value.id)
  ElMessage.success('方案已确认')
}

function onResize() { chart && chart.resize() }

onMounted(async () => {
  await loadMps()
  await loadLatest()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.p-page { padding: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 16px; font-weight: 600; color: var(--sw-primary); }
.sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.actions { display: flex; gap: 8px; align-items: center; }
.kpi-row { display: flex; gap: 12px; margin: 6px 0 12px; flex-wrap: wrap; }
.kpi { flex: 1; min-width: 100px; background: #f5f7fa; border-radius: 6px; padding: 8px 12px; }
.kpi-num { font-size: 20px; font-weight: 600; color: var(--sw-primary); }
.kpi-label { font-size: 12px; color: #8a8f99; }
.plan-line { font-size: 13px; color: #606266; margin-bottom: 8px; }
.gantt { width: 100%; height: 420px; border: 1px solid #ebeef5; border-radius: 4px; }
.bottom-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-top: 8px; }
</style>
