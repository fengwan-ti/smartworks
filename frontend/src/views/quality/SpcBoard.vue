<template>
  <div class="sw-page">
    <div class="sw-card">
      <div class="spc-bar">
        <el-select v-model="standardItem" filterable placeholder="选择检验项" style="width: 280px">
          <el-option v-for="o in itemOptions" :key="o.id" :label="o.standard_name + ' / ' + o.name" :value="o.id" />
        </el-select>
        <el-button type="primary" :loading="loading" :disabled="!standardItem" @click="loadSpc">分析</el-button>
      </div>
    </div>

    <div v-if="result" class="sw-card">
      <div class="kpi-row">
        <div class="kpi">
          <span class="kpi-label">CL 中心线</span>
          <span class="kpi-value">{{ result.cl }}</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">UCL 上控限</span>
          <span class="kpi-value">{{ result.ucl }}</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">LCL 下控限</span>
          <span class="kpi-value">{{ result.lcl }}</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Cp</span>
          <span class="kpi-value">{{ result.cp ?? '—' }}</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Cpk</span>
          <span class="kpi-value" :class="{ bad: Number(result.cpk) < 1.33 }">{{ result.cpk ?? '—' }}</span>
        </div>
      </div>
      <div ref="chartRef" class="spc-chart" />
      <el-alert v-if="outOfControl.length" type="error" :closable="false"
        :title="`发现 ${outOfControl.length} 个超出控制限的点，过程失控`" />
      <el-alert v-else type="success" :closable="false" title="所有点均在控制限内，过程受控" />
    </div>
  </div>
</template>

<script setup>
/** SPC 分析 —— /quality/spc/，X-R 控制图 + Cp/Cpk。 */
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { listAllStandardItems, getSpc } from '@/api/quality'

const loading = ref(false)
const standardItem = ref(null)
const itemOptions = ref([])
const result = ref(null)
const chartRef = ref()
let chart = null

const outOfControl = computed(() =>
  (result.value?.points || []).filter(
    (p) => Number(p.value) > Number(result.value.ucl) || Number(p.value) < Number(result.value.lcl)
  )
)

async function loadItems() {
  const data = await listAllStandardItems({ page_size: 200 })
  itemOptions.value = data.results || data || []
}

async function loadSpc() {
  loading.value = true
  try {
    result.value = await getSpc({ standard_item: standardItem.value })
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  const points = result.value.points || []
  chart.setOption({
    grid: { left: 50, right: 20, top: 30, bottom: 60 },
    xAxis: { type: 'category', data: points.map((_, i) => i + 1) },
    yAxis: { type: 'value', scale: true },
    series: [
      {
        name: '测量值', type: 'line', data: points.map((p) => Number(p.value)),
        symbol: 'circle', symbolSize: 6,
        lineStyle: { color: '#409eff' }, itemStyle: { color: '#409eff' },
        markLine: {
          silent: true, symbol: 'none',
          data: [
            { yAxis: Number(result.value.ucl), lineStyle: { color: '#f56c6c', type: 'dashed' }, label: { formatter: 'UCL' } },
            { yAxis: Number(result.value.cl), lineStyle: { color: '#67c23a' }, label: { formatter: 'CL' } },
            { yAxis: Number(result.value.lcl), lineStyle: { color: '#f56c6c', type: 'dashed' }, label: { formatter: 'LCL' } }
          ]
        }
      }
    ]
  })
}

onBeforeUnmount(() => {
  chart?.dispose()
})

loadItems()
</script>

<style scoped>
.spc-bar {
  display: flex;
  gap: 12px;
}
.kpi-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}
.kpi {
  display: flex;
  flex-direction: column;
}
.kpi-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.kpi-value {
  font-size: 20px;
  font-weight: 700;
}
.kpi-value.bad {
  color: var(--el-color-danger);
}
.spc-chart {
  width: 100%;
  height: 320px;
}
</style>
