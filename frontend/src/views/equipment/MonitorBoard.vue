<template>
  <div class="sw-page">
    <div class="sw-metrics">
      <div class="sw-metric">
        <div class="sw-metric__label">在册设备</div>
        <div class="sw-metric__value">{{ summary.equipment_total || 0 }}<span class="sw-metric__unit">台</span></div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--warn': summary.alarm_open > 0 }">
        <div class="sw-metric__label">未关闭告警</div>
        <div class="sw-metric__value">{{ summary.alarm_open || 0 }}<span class="sw-metric__unit">条</span></div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--danger': summary.alarm_critical > 0 }">
        <div class="sw-metric__label">严重告警</div>
        <div class="sw-metric__value">{{ summary.alarm_critical || 0 }}<span class="sw-metric__unit">条</span></div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">待维修 / 待点检</div>
        <div class="sw-metric__value">
          {{ summary.maintenance_open || 0 }} / {{ summary.inspection_due || 0 }}
        </div>
        <div class="sw-metric__foot">点检到期按 next_due_at 判断</div>
      </div>
    </div>

    <div class="sw-grid">
      <!-- 左：设备清单。点一行切右边的曲线 -->
      <div class="sw-card">
        <div class="sw-toolbar">
          <strong style="font-size: 14px">设备清单</strong>
          <el-button size="small" :loading="loading" style="margin-left: auto" @click="loadOverview">
            刷新
          </el-button>
        </div>
        <el-table
          :data="equipments"
          size="small"
          highlight-current-row
          :current-row-key="selected"
          row-key="code"
          @row-click="onSelect"
        >
          <el-table-column prop="code" label="编码" width="100" />
          <el-table-column label="设备" min-width="120">
            <template #default="{ row }">
              <div>{{ row.name }}</div>
              <div class="sw-sub">{{ row.workstation || '未分配工位' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="86">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small" effect="light">
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="告警" width="70" align="center">
            <template #default="{ row }">
              <span :class="{ 'sw-danger': row.open_alarms > 0 }">{{ row.open_alarms }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最新振动" width="96">
            <template #default="{ row }">
              {{ latestOf(row, 'vibration') }}
            </template>
          </el-table-column>
        </el-table>
        <div class="sw-sub" style="margin-top: 8px">
          标了「不计 OEE」的设备（8# 去毛刺台）在 OEE 页会被跳过，这里照常看读数
        </div>
      </div>

      <!-- 右：四通道曲线。四个量纲不同，各自一根 y 轴，别硬塞进一张图 -->
      <div class="sw-card">
        <div class="sw-toolbar">
          <strong style="font-size: 14px">
            {{ currentName }} · 四通道曲线
          </strong>
          <el-button size="small" :loading="simulating" @click="onSimulate">
            模拟一段数据
          </el-button>
          <el-button size="small" :loading="seriesLoading" @click="loadSeries">刷新曲线</el-button>
        </div>

        <el-empty v-if="!selected" description="点左边任意一台设备看曲线" />
        <div v-else class="sw-charts">
          <div v-for="c in channels" :key="c.value" class="sw-chart">
            <div class="sw-chart__title">{{ c.label }}</div>
            <div :ref="(el) => setChartRef(c.value, el)" class="sw-chart__body" />
            <div v-if="!series[c.value]?.points?.length" class="sw-chart__empty">
              这段没有读数，点「模拟一段数据」造几条
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 设备监测（W4）。
 *
 * 为什么是"四张小图"而不是一张四线图：
 *   振动 4.5 mm/s、温度 78 ℃、电流 12 A、转速 1450 rpm —— 量纲差三个数量级。
 *   画在一张图上，转速会把其他三条压成贴着 x 轴的直线，
 *   现场看曲线是为了"看出哪一条不对劲"，不是比大小。
 *
 * 数据来源两段：
 *   monitor/overview  一次拿全车间最新值（第一屏用，只发一个请求）
 *   sensor-readings/series  选中设备时按通道各拉一次（画曲线用）
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import echarts from '@/charts'
import {
  fetchMonitorOverview,
  fetchSeries,
  simulateReadings
} from '@/api/equipment'

const loading = ref(false)
const seriesLoading = ref(false)
const simulating = ref(false)
const equipments = ref([])
const channels = ref([])
const summary = ref({})
const selected = ref('')
const series = reactive({})

const chartEls = {}
const charts = {}

const currentName = computed(() => {
  const hit = equipments.value.find((e) => e.code === selected.value)
  return hit ? `${hit.code} ${hit.name}` : '未选择设备'
})

function statusTag(status) {
  return { normal: 'success', wearing: 'warning', abnormal: 'danger' }[status] || 'info'
}

function latestOf(row, channel) {
  const hit = row.latest && row.latest[channel]
  return hit ? hit.value.toFixed(2) : '—'
}

function setChartRef(channel, el) {
  if (el) chartEls[channel] = el
}

async function loadOverview() {
  loading.value = true
  try {
    const data = await fetchMonitorOverview()
    equipments.value = data.equipments || []
    channels.value = data.channels || []
    summary.value = data.summary || {}
    // 默认选第一台，省得进来先看一片空白
    if (!selected.value && equipments.value.length) {
      await onSelect(equipments.value[0])
    }
  } catch (e) {
    console.error('[Monitor] 总览加载失败', e)
  } finally {
    loading.value = false
  }
}

async function onSelect(row) {
  selected.value = row.code
  await nextTick()
  await loadSeries()
}

async function loadSeries() {
  if (!selected.value) return
  seriesLoading.value = true
  try {
    const results = await Promise.all(
      channels.value.map((c) =>
        fetchSeries({ equipment_code: selected.value, channel: c.value, limit: 200 })
      )
    )
    results.forEach((r, i) => {
      const channel = channels.value[i].value
      series[channel] = r
      renderChart(channel, r, channels.value[i].label)
    })
  } catch (e) {
    console.error('[Monitor] 曲线加载失败', e)
  } finally {
    seriesLoading.value = false
  }
}

function renderChart(channel, payload, label) {
  const el = chartEls[channel]
  if (!el) return
  if (!charts[channel]) charts[channel] = echarts.init(el)
  const points = payload.points || []
  charts[channel].setOption(
    {
      grid: { left: 52, right: 16, top: 16, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: points.map((p) => String(p.t).slice(11, 16)),
        axisLabel: { fontSize: 10, color: '#8a94a6' }
      },
      yAxis: {
        type: 'value',
        scale: true,
        name: label,
        nameTextStyle: { fontSize: 10, color: '#8a94a6' },
        axisLabel: { fontSize: 10, color: '#8a94a6' },
        splitLine: { lineStyle: { color: '#f0f2f5' } }
      },
      series: [
        {
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: points.map((p) => p.v),
          lineStyle: { width: 1.6 },
          areaStyle: { opacity: 0.08 }
        }
      ]
    },
    true
  )
}

async function onSimulate() {
  if (!selected.value) {
    ElMessage.warning('先选一台设备')
    return
  }
  simulating.value = true
  try {
    const result = await simulateReadings({
      equipment_codes: [selected.value],
      minutes: 30,
      step_minutes: 1
    })
    ElMessage.success(`已写入 ${result.points ?? 0} 条读数（${result.minutes} 分钟）`)
    await Promise.all([loadOverview(), loadSeries()])
  } catch (e) {
    // 已提示
  } finally {
    simulating.value = false
  }
}

/** 容器尺寸变化（收起侧边栏、换分辨率）时重画一次，否则图会停在旧宽度 */
function onResize() {
  Object.values(charts).forEach((c) => c.resize())
}

onMounted(async () => {
  await loadOverview()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  Object.values(charts).forEach((c) => c.dispose())
})
</script>

<style scoped>
.sw-grid {
  display: grid;
  grid-template-columns: minmax(360px, 5fr) minmax(420px, 7fr);
  gap: 12px;
  align-items: start;
}

@media (max-width: 1200px) {
  .sw-grid {
    grid-template-columns: 1fr;
  }
}

.sw-charts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.sw-chart {
  position: relative;
  border: 1px solid #f0f2f5;
  border-radius: var(--sw-radius);
  padding: 6px 8px 2px;
}

.sw-chart__title {
  font-size: 12px;
  color: #606266;
  padding-left: 4px;
}

.sw-chart__body {
  height: 150px;
}

.sw-chart__empty {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  text-align: center;
  font-size: 12px;
  color: #b6bcc8;
  pointer-events: none;
}

.sw-danger {
  color: #c02f2f;
  font-weight: 600;
}
</style>
