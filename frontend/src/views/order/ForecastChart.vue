<template>
  <div class="f-page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <div>
            <div class="title">需求预测（任务 7）</div>
            <div class="sub">数据：data/teacher-orders-6parts-weekly.csv（261 周 × 6 零件）· 测试集最后 8 周 · 主指标 MAPE</div>
          </div>
          <div class="actions">
            <el-select v-model="model" style="width: 170px">
              <el-option label="SARIMA（主模型）" value="sarima" />
              <el-option label="指数平滑" value="exp_smoothing" />
              <el-option label="移动平均 MA(4)" value="moving_average" />
              <el-option label="季节朴素（基线）" value="seasonal_naive" />
            </el-select>
            <el-input-number v-model="horizon" :min="1" :max="26" style="width: 140px" />
            <el-button type="primary" :loading="running" @click="run">运行预测</el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="!results.length" type="info" :closable="false" show-icon
        title="点“运行预测”对 6 种零件跑一遍：SARIMA 用季节差分 + 漂移，测试集最后 8 周。" />

      <template v-else>
        <el-table :data="results" border size="small" style="margin-bottom: 12px">
          <el-table-column prop="product" label="产品编码" width="120" />
          <el-table-column label="MAPE" width="110" align="right">
            <template #default="{ row }">
              <el-tag :type="row.mape < row.baseline_seasonal_mape ? 'success' : 'warning'" size="small">{{ row.mape }}%</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="同周去年基线" width="130" align="right">
            <template #default="{ row }">{{ row.baseline_seasonal_mape }}%</template>
          </el-table-column>
          <el-table-column prop="rmse" label="RMSE" width="100" align="right" />
          <el-table-column label="未来首周预测" width="130" align="right">
            <template #default="{ row }">{{ row.forecast[0]?.qty }}</template>
          </el-table-column>
          <el-table-column label="未来 8 周" min-width="240">
            <template #default="{ row }">
              <span class="fc-inline">{{ row.forecast.map((f) => f.qty).join(' / ') }}</span>
            </template>
          </el-table-column>
          <el-table-column label="查看" width="80">
            <template #default="{ row }">
              <el-button link type="primary" @click="selectProduct(row)">曲线</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="current" class="chart-box">
          <div class="chart-title">{{ current.product }} · 历史 52 周 + 未来 {{ current.forecast.length }} 周预测</div>
          <div ref="chartEl" class="chart"></div>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { runForecast } from '@/api/order'
import { productOptions } from '@/api/masterdata'

const model = ref('sarima')
const horizon = ref(8)
const running = ref(false)
const results = ref([])
const current = ref(null)
const chartEl = ref(null)
let chart = null

async function run() {
  running.value = true
  try {
    const products = (await productOptions()).map((p) => p.code)
      .filter((c) => c.startsWith('PF-'))
    const data = await runForecast({ products, model: model.value, horizon: horizon.value })
    results.value = data.results || []
    if (data.errors?.length) ElMessage.warning(data.errors.map((e) => `${e.product}: ${e.message}`).join('；'))
    if (results.value.length) {
      current.value = results.value[0]
      await nextTick()
      render()
    }
  } finally { running.value = false }
}

async function selectProduct(row) {
  current.value = row
  await nextTick()
  render()
}

function render() {
  if (!chartEl.value || !current.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const h = current.value.history
  const f = current.value.forecast
  const x = [...h.periods, ...f.map((i) => i.period)]
  const history = [...h.values, ...f.map(() => null)]
  const forecast = [...h.periods.map(() => null), ...f.map((i) => i.qty)]
  forecast[h.periods.length - 1] = h.values[h.values.length - 1]
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['历史', '预测'] },
    grid: { left: 50, right: 20, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: x, axisLabel: { rotate: 40, fontSize: 10 } },
    yAxis: { type: 'value', name: '件/周' },
    series: [
      { name: '历史', type: 'line', data: history, smooth: true, symbol: 'none', lineStyle: { width: 2 } },
      { name: '预测', type: 'line', data: forecast, smooth: true, symbol: 'circle', symbolSize: 5,
        lineStyle: { type: 'dashed', width: 2, color: '#e6a23c' }, itemStyle: { color: '#e6a23c' } },
    ],
  })
}

function onResize() { chart && chart.resize() }
onMounted(() => { window.addEventListener('resize', onResize) })
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.f-page { padding: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 16px; font-weight: 600; color: var(--sw-primary); }
.sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.actions { display: flex; gap: 8px; align-items: center; }
.fc-inline { font-family: Consolas, monospace; font-size: 12px; }
.chart-box { margin-top: 8px; }
.chart-title { font-size: 13px; color: #606266; margin-bottom: 6px; }
.chart { width: 100%; height: 380px; border: 1px solid #ebeef5; border-radius: 4px; }
</style>
