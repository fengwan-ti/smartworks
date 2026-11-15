<template>
  <div class="sw-page">
    <!-- KPI：左边优化方案、右边就近派车基线，中间是提升幅度。
         这三个数就是答辩时「算法到底有没有用」的直接回答。 -->
    <div class="sw-metrics">
      <div class="sw-metric">
        <div class="sw-metric__label">完工时刻 makespan</div>
        <div class="sw-metric__value">
          {{ fmtDuration(result.makespan_s) }}
          <span v-if="result.baseline" class="sw-metric__unit">
            / 基线 {{ fmtDuration(result.baseline.makespan_s) }}
          </span>
        </div>
        <div class="sw-metric__foot">
          <el-tag v-if="improve.makespan_ratio" type="success" size="small" effect="light">
            缩短 {{ pct(improve.makespan_ratio) }}
          </el-tag>
          <span v-else class="sw-sub">最后一台车收工的时刻</span>
        </div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">空驶率</div>
        <div class="sw-metric__value">
          {{ pct(result.empty_ratio) }}
          <span v-if="result.baseline" class="sw-metric__unit">
            / 基线 {{ pct(result.baseline.empty_ratio) }}
          </span>
        </div>
        <div class="sw-metric__foot">
          <!-- improvement.empty_ratio_delta = 基线 − 优化：正数是改善，负数是变差。
               必须写出方向：55.4% / 基线 52.8% 单看数字像变好了，其实是为了压缩工期多跑空趟。 -->
          <el-tag
            v-if="improve.empty_ratio_delta !== undefined && improve.empty_ratio_delta !== null"
            :type="improve.empty_ratio_delta >= 0 ? 'success' : 'warning'"
            size="small"
            effect="light"
          >
            {{ improve.empty_ratio_delta >= 0 ? '改善' : '变差' }}
            {{ Math.abs(improve.empty_ratio_delta * 100).toFixed(1) }} 个百分点
          </el-tag>
          <span v-else>空驶里程 ÷ 总里程</span>
        </div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">任务 / 用车</div>
        <div class="sw-metric__value">{{ result.task_count || 0 }} / {{ result.agv_count || 0 }}</div>
        <div class="sw-metric__foot">
          总里程 {{ fmtMeters((result.total_empty_mm || 0) + (result.total_loaded_mm || 0)) }}
        </div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">算法</div>
        <div class="sw-metric__value" style="font-size: 15px; line-height: 1.6">
          {{ result.algorithm || '未计算' }}
        </div>
        <div class="sw-metric__foot">
          <span v-if="result.improved_by_search">已做 relocate 改进</span>
          <span v-else-if="result.plans?.length">贪心插入即最优，未再改进</span>
          <span v-else>点「算一套方案」开始</span>
        </div>
      </div>
    </div>

    <div class="sw-card">
      <div class="sw-toolbar">
        <el-select
          v-model="selectedAgvs"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          placeholder="参与调度的车（留空=全部可用）"
          style="width: 300px"
        >
          <el-option
            v-for="a in agvOptions"
            :key="a.code"
            :label="`${a.code} ${a.name}（${a.battery}% ${a.status_label}）`"
            :value="a.code"
            :disabled="!a.is_active"
          />
        </el-select>

        <el-select
          v-model="selectedTasks"
          multiple
          collapse-tags
          collapse-tags-tooltip
          filterable
          clearable
          placeholder="指定任务（留空=全部待派车）"
          style="width: 280px"
        >
          <el-option
            v-for="t in taskOptions"
            :key="t.code"
            :label="`${t.code} ${t.from_node_code}→${t.to_node_code} P${t.priority}`"
            :value="t.code"
          />
        </el-select>

        <el-input-number v-model="limit" :min="1" :max="200" :step="5" style="width: 130px" />

        <el-button type="primary" :loading="computing" @click="onCompute(false)">算一套方案</el-button>
        <!-- 不加 :disabled="!hasPlan"：后端 /agv-schedule/ 收 apply=true 就是"算完直接下发"，
             前端拦着反而让人点一下没反应（2026-11-15 无头验收时就卡在这 ——
             按钮是灰的、点了没动静，现场会以为系统坏了）。 -->
        <el-button type="success" :loading="applying" @click="onCompute(true)">
          算并下发
        </el-button>
        <el-button :loading="loadingHistory" @click="loadHistory">刷新历史</el-button>
      </div>
      <div class="sw-sub" style="margin-bottom: 12px">
        三个条件都可留空：「算一套方案」只算并留档（draft），不改任务状态；「算并下发」才真正派车。
        留空时会把全部待派车任务和全部可用车排进去。
      </div>

      <el-alert
        v-if="!hasPlan"
        type="info"
        :closable="false"
        show-icon
        title="还没有方案"
        description="调度对象是「待派车」的搬运任务。没有待派任务时，先跑 manage.py demo_w5_pipeline --reset --derive-only 造 B 的 16 条 legs（或 demo_w5_schedule 造 6 条手工任务）。"
      />

      <!-- 每台车一张卡：顺序就是现场执行的顺序，别用表格按列排 —— 看顺序时表格不直观 -->
      <div v-else class="sw-plans">
        <div v-for="p in result.plans" :key="p.agv_code" class="sw-plan">
          <div class="sw-plan__head">
            <span class="sw-plan__title">{{ p.agv_code }} {{ p.agv_name }}</span>
            <el-tag size="small" effect="plain">{{ p.task_count }} 单</el-tag>
            <el-tag v-if="!p.task_count" size="small" type="info">空闲</el-tag>
          </div>
          <div class="sw-plan__meta">
            起点 {{ p.start_node }} · 空驶 {{ fmtMeters(p.empty_mm) }} ·
            载货 {{ fmtMeters(p.loaded_mm) }} · 用时 {{ fmtDuration(p.elapsed_s) }}
          </div>

          <el-timeline v-if="p.tasks?.length" style="padding-left: 4px; margin-top: 8px">
            <el-timeline-item
              v-for="(t, i) in p.tasks"
              :key="t.code"
              :timestamp="`第 ${i + 1} 单 · ${t.code}`"
              placement="top"
              size="normal"
            >
              <span class="sw-plan__flow">{{ t.from_location }} → {{ t.to_location }}</span>
              <span class="sw-sub">　{{ t.task_type }} · {{ t.qty }} 件 · P{{ t.priority }}</span>
            </el-timeline-item>
          </el-timeline>
          <div v-else class="sw-sub" style="margin-top: 10px">这台车没分到任务</div>
        </div>
      </div>

      <el-alert
        v-if="result.unassigned?.length"
        type="warning"
        :closable="false"
        show-icon
        style="margin-top: 12px"
        :title="`${result.unassigned.length} 条任务无法安排`"
        :description="result.unassigned.map((u) => `${u.code}：${u.reason}`).join('；')"
      />
    </div>

    <div class="sw-card" style="margin-top: 12px">
      <div class="sw-toolbar">
        <strong style="font-size: 14px">历史方案</strong>
        <span class="sw-sub" style="align-self: center">
          每次计算都留档，可回看当时两套 KPI 的差距
        </span>
      </div>
      <BaseTable :columns="historyColumns" :rows="history" :total="historyTotal"
                 @change="onHistoryPage">
        <template #algorithm="{ row }">
          <el-tag size="small" :type="row.status === 'applied' ? 'success' : 'info'" effect="light">
            {{ row.status_label }}
          </el-tag>
        </template>
        <template #gap="{ row }">
          <span v-if="row.kpi?.baseline_makespan_s">
            {{ fmtDuration(row.kpi.makespan_s) }} / {{ fmtDuration(row.kpi.baseline_makespan_s) }}
          </span>
          <span v-else class="sw-sub">—</span>
        </template>
        <template #created="{ row }">
          {{ String(row.created_at || '').replace('T', ' ').slice(0, 16) }}
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openHistory(row)">查看</el-button>
        </template>
      </BaseTable>
    </div>

    <el-drawer v-model="historyVisible" title="方案详情" size="520px">
      <template v-if="historyCurrent">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="方案编号">{{ historyCurrent.code }}</el-descriptions-item>
          <el-descriptions-item label="算法">{{ historyCurrent.algorithm }}</el-descriptions-item>
          <el-descriptions-item label="任务 / 用车">
            {{ historyCurrent.task_count }} / {{ historyCurrent.agv_count }}
          </el-descriptions-item>
          <el-descriptions-item label="makespan">
            {{ fmtDuration(historyCurrent.kpi?.makespan_s) }}
            （基线 {{ fmtDuration(historyCurrent.kpi?.baseline_makespan_s) }}）
          </el-descriptions-item>
          <el-descriptions-item label="空驶率">
            {{ pct(historyCurrent.kpi?.empty_ratio) }}
            （基线 {{ pct(historyCurrent.kpi?.baseline_empty_ratio) }}）
          </el-descriptions-item>
        </el-descriptions>

        <div v-for="p in historyCurrent.detail?.plans || []" :key="p.agv_code"
             style="margin-top: 14px">
          <div class="sw-plan__title">{{ p.agv_code }} {{ p.agv_name }}</div>
          <div class="sw-sub" style="margin: 4px 0">
            空驶 {{ fmtMeters(p.empty_mm) }} · 载货 {{ fmtMeters(p.loaded_mm) }} ·
            用时 {{ fmtDuration(p.elapsed_s) }}
          </div>
          <el-tag
            v-for="code in p.seq || []"
            :key="code"
            size="small"
            style="margin: 2px 4px 2px 0"
            effect="plain"
          >
            {{ code }}
          </el-tag>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * AGV 调度方案（W5，算法任务 1/2 的界面）。
 *
 * 两个入口的区别必须让人一眼看懂，否则容易在演示时误派车：
 *   算一套方案 → apply=false：算完存一条 draft，任务状态不变，可以反复点
 *   算并下发   → apply=true ：真的把任务挂到车上、状态转 assigned
 *
 * 页面刻意把「优化方案」和「就近派车基线」并排显示：
 * 单独给一个 makespan 说明不了什么，两个数放一起才知道算法值多少。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BaseTable from '@/components/BaseTable.vue'
import {
  buildSchedule,
  fetchAgvs,
  fetchSchedulePlans,
  fetchTransportTasks
} from '@/api/logistics'

const computing = ref(false)
const applying = ref(false)
const result = ref({})
const history = ref([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyLoading = ref(false)
const loadingHistory = computed(() => historyLoading.value)

// 三个筛选条件：都留空 = 全部可用车 + 全部待派任务
const selectedAgvs = ref([])
const selectedTasks = ref([])
const limit = ref(50)
const agvOptions = ref([])
const taskOptions = ref([])

const historyVisible = ref(false)
const historyCurrent = ref(null)

const hasPlan = computed(() => (result.value.plans || []).length > 0)
const improve = computed(() => result.value.improvement || {})

const historyColumns = [
  { prop: 'code', label: '方案编号', width: 160 },
  { prop: 'algorithm', label: '状态', width: 100, slot: 'algorithm' },
  { prop: 'task_count', label: '任务数', width: 90 },
  { prop: 'agv_count', label: '用车', width: 80 },
  { prop: 'gap', label: 'makespan 优化/基线', minWidth: 200, slot: 'gap' },
  { prop: 'created_at', label: '计算时间', width: 150, slot: 'created' },
  { prop: 'actions', label: '操作', width: 80, slot: 'actions' }
]

/** 秒 → 1分23秒。超过 1 小时才显示小时，车间里没人关心"0.02 小时" */
function fmtDuration(seconds) {
  const s = Number(seconds || 0)
  if (!s) return '—'
  if (s < 60) return `${s.toFixed(1)} 秒`
  const m = Math.floor(s / 60)
  const rest = Math.round(s - m * 60)
  if (m < 60) return `${m} 分 ${rest} 秒`
  return `${Math.floor(m / 60)} 时 ${m % 60} 分`
}

/** 毫米 → 米。库里全是 mm（整数、不丢精度），展示时才换算 */
function fmtMeters(mm) {
  return `${(Number(mm || 0) / 1000).toFixed(1)} m`
}

function pct(value) {
  if (value === null || value === undefined) return '—'
  return `${(Number(value) * 100).toFixed(1)}%`
}

async function onCompute(apply) {
  if (apply) {
    const confirmed = await ElMessageBox.confirm(
      '会先算一套方案，再把任务真的挂到车上、状态改成「已派车」。确定吗？',
      '算并下发',
      { confirmButtonText: '下发', cancelButtonText: '再想想', type: 'warning' }
    ).catch(() => false)
    if (!confirmed) return
    applying.value = true
  } else {
    computing.value = true
  }

  try {
    const payload = {
      apply,
      limit: limit.value,
      agv_codes: selectedAgvs.value,
      task_codes: selectedTasks.value
    }
    const data = await buildSchedule(payload)
    if (apply) {
      result.value = data.plan || {}
      ElMessage.success(`已下发 ${data.apply?.applied_count || 0} 条任务`)
    } else {
      result.value = data || {}
      ElMessage.success('方案已算好（仅预览，未派车）')
    }
    await Promise.all([loadHistory(), loadOptions()])
  } catch (e) {
    // request.js 已提示；14505/14506 这类业务错误会直接显示后端原文
  } finally {
    computing.value = false
    applying.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await fetchSchedulePlans({ page: historyPage.value, page_size: 10 })
    history.value = (data && data.results) || []
    historyTotal.value = (data && data.count) || 0
  } catch (e) {
    console.error('[SchedulePlan] 历史方案加载失败', e)
  } finally {
    historyLoading.value = false
  }
}

function onHistoryPage({ page }) {
  historyPage.value = page
  loadHistory()
}

function openHistory(row) {
  historyCurrent.value = row
  historyVisible.value = true
}

/** 下拉数据：车全部拉（一般就 3 台），任务只拉待派车的。 */
async function loadOptions() {
  try {
    const [agvData, taskData] = await Promise.all([
      fetchAgvs({ page_size: 50 }),
      fetchTransportTasks({ status: 'pending', page_size: 200 })
    ])
    agvOptions.value = (agvData && agvData.results) || []
    taskOptions.value = (taskData && taskData.results) || []
  } catch (e) {
    console.error('[SchedulePlan] 下拉数据加载失败', e)
  }
}

onMounted(() => {
  loadOptions()
  loadHistory()
})
</script>

<style scoped>
.sw-plans {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px;
}

.sw-plan {
  border: 1px solid #ebeef5;
  border-radius: var(--sw-radius);
  padding: 12px 14px;
}

.sw-plan__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.sw-plan__title {
  font-weight: 600;
  color: var(--sw-primary);
  font-size: 14px;
}

.sw-plan__meta {
  font-size: 12px;
  color: #8a94a6;
}

.sw-plan__flow {
  font-size: 13px;
  color: #303133;
}
</style>
