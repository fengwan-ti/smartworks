<template>
  <div class="sw-page">
    <!-- 指标全部来自后端 board：前端不自己数，否则和空驶率口径对不上 -->
    <div class="sw-metrics">
      <div class="sw-metric" :class="{ 'sw-metric--warn': board.pending > 0 }">
        <div class="sw-metric__label">待派车</div>
        <div class="sw-metric__value">{{ board.pending }}<span class="sw-metric__unit">单</span></div>
        <div class="sw-metric__foot">已派 {{ board.assigned }} · 执行中 {{ board.running }}</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">已完成</div>
        <div class="sw-metric__value">{{ board.done }}<span class="sw-metric__unit">单</span></div>
        <div class="sw-metric__foot">取消 {{ board.cancelled }} 单</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">今日总里程</div>
        <div class="sw-metric__value" style="font-size: 22px">
          {{ toMeters(board.today_total_mm) }}
        </div>
        <div class="sw-metric__foot">
          载货 {{ toMeters(board.today_loaded_mm) }} · 空驶 {{ toMeters(board.today_empty_mm) }}
        </div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--danger': board.empty_ratio >= 0.5 }">
        <div class="sw-metric__label">今日空驶率</div>
        <div class="sw-metric__value">{{ pct(board.empty_ratio) }}</div>
        <div class="sw-metric__foot">
          空驶 ÷ 总里程（只算已派车任务）· 车 {{ board.agv_idle }}空闲/{{ board.agv_busy }}在跑
        </div>
      </div>
    </div>

    <div class="sw-card">
      <div class="sw-toolbar">
        <span style="font-weight: 600">搬运任务</span>
        <el-button :loading="loading" style="margin-left: auto" @click="refreshAll">刷新</el-button>
        <el-button type="primary" :loading="assigning" :disabled="!board.pending"
                   @click="onAssignPending">
          一键派完（{{ board.pending }}）
        </el-button>
      </div>

      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset" />

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #code="{ row }">
          <div>{{ row.code }}</div>
          <div class="sw-sub">{{ row.ref_doc || '手工创建' }}</div>
        </template>
        <template #type="{ row }">
          <el-tag size="small" effect="plain">{{ row.task_type_label }}</el-tag>
        </template>
        <template #from="{ row }">
          <div>{{ row.from_node_code || '—' }}</div>
          <div class="sw-sub">{{ row.from_location || '' }}</div>
        </template>
        <template #to="{ row }">
          <div>{{ row.to_node_code || '—' }}</div>
          <div class="sw-sub">{{ row.to_location || '' }}</div>
        </template>
        <template #qty="{ row }">
          <span v-if="row.qty !== null && row.qty !== undefined">{{ trimQty(row.qty) }}</span>
          <span v-else class="sw-sub">—</span>
        </template>
        <template #priority="{ row }">
          <el-tag :type="priorityTag(row.priority)" size="small" effect="plain">
            P{{ row.priority }}
          </el-tag>
        </template>
        <template #status="{ row }">
          <el-tag :type="statusTag(row.status)" size="small" effect="light">
            {{ row.status_label }}
          </el-tag>
        </template>
        <template #distance="{ row }">
          <div v-if="row.distance_mm">{{ toMeters(row.distance_mm) }}</div>
          <div v-else class="sw-sub">—</div>
          <div class="sw-sub">
            空驶 {{ row.empty_distance_mm === null || row.empty_distance_mm === undefined
              ? '—' : toMeters(row.empty_distance_mm) }}
          </div>
        </template>
        <template #actions="{ row }">
          <el-button v-if="row.status === 'pending'" link type="primary" @click="onAssign(row)">
            派车
          </el-button>
          <el-button v-if="row.status === 'assigned'" link type="primary" @click="onStart(row)">
            开始
          </el-button>
          <el-button v-if="row.status === 'running'" link type="success" @click="onDone(row)">
            完成
          </el-button>
          <el-button v-if="canCancel(row)" link type="danger" @click="onCancel(row)">
            取消
          </el-button>
          <el-button link @click="showDetail(row)">详情</el-button>
        </template>
      </BaseTable>
    </div>

    <el-drawer v-model="detailVisible" title="搬运任务详情" size="480px">
      <el-descriptions v-if="current" :column="1" border size="small">
        <el-descriptions-item label="任务编号">{{ current.code }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ current.task_type_label }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ current.status_label }}</el-descriptions-item>
        <el-descriptions-item label="起点">
          {{ current.from_node_code || '—' }} {{ current.from_location || '' }}
        </el-descriptions-item>
        <el-descriptions-item label="终点">
          {{ current.to_node_code || '—' }} {{ current.to_location || '' }}
        </el-descriptions-item>
        <el-descriptions-item label="数量">{{ current.qty ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">P{{ current.priority }}</el-descriptions-item>
        <el-descriptions-item label="来源">
          {{ current.ref_type_label || '—' }}
          <span v-if="current.ref_doc">· {{ current.ref_doc }}</span>
          <span v-if="current.ref_seq !== null && current.ref_seq !== undefined">
            · 工序 {{ current.ref_seq }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="派车">
          {{ current.agv_code || '未派车' }}
        </el-descriptions-item>
        <el-descriptions-item label="载货里程">{{ toMeters(current.distance_mm) }}</el-descriptions-item>
        <el-descriptions-item label="空驶里程">{{ toMeters(current.empty_distance_mm) }}</el-descriptions-item>
        <el-descriptions-item label="计划窗口">
          {{ fmtTime(current.plan_start) }} ~ {{ fmtTime(current.plan_end) }}
        </el-descriptions-item>
        <el-descriptions-item label="实际">
          开始 {{ fmtTime(current.started_at) }} · 完成 {{ fmtTime(current.finished_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="实际耗时">
          {{ current.duration_minutes === null || current.duration_minutes === undefined
            ? '—' : current.duration_minutes + ' 分钟' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注">{{ current.remark || '—' }}</el-descriptions-item>
      </el-descriptions>
      <p class="sw-sub" style="margin-top: 12px">
        空驶里程只有在派过车之后才有值 —— 派单前不知道车在哪，就不知道要空跑多远。
      </p>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * 搬运任务（角色 D，W3/W5）。
 *
 * 这张表是**状态机**，不是可随便改的表：
 *   pending --派车--> assigned --开始--> running --完成--> done
 *   pending/assigned --取消--> cancelled
 * 所以操作列只按当前状态出现对应按钮，不给状态下拉框。
 * 非法流转后端报 14504，前端提前把按钮藏掉，少一次无谓的报错。
 *
 * 「一键派完」走 assign-pending：按优先级逐条派，失败的会带回原因
 * （通常是"没有空闲车"/"载重不够"），前端按成功数给一句汇总。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  assignPendingTasks,
  assignTask,
  changeTaskStatus,
  fetchAgvs,
  fetchTaskBoard,
  fetchTransportTasks
} from '@/api/logistics'

const loading = ref(false)
const assigning = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const agvOptions = ref([])

const board = reactive({
  pending: 0, assigned: 0, running: 0, done: 0, cancelled: 0,
  today_loaded_mm: 0, today_empty_mm: 0, today_total_mm: 0,
  empty_ratio: 0, agv_idle: 0, agv_busy: 0, agv_total: 0
})

const searchFields = ref([
  { prop: 'search', label: '单号/位置', type: 'input', placeholder: '任务号、单据号、起点终点' },
  {
    prop: 'status', label: '状态', type: 'select',
    options: [
      { value: 'pending', label: '待派车' },
      { value: 'assigned', label: '已派车' },
      { value: 'running', label: '执行中' },
      { value: 'done', label: '已完成' },
      { value: 'cancelled', label: '已取消' }
    ]
  },
  {
    prop: 'task_type', label: '类型', type: 'select',
    options: [
      { value: 'feed', label: '领料' },
      { value: 'transfer', label: '转序' },
      { value: 'inbound', label: '成品入库' },
      { value: 'return', label: '退料' }
    ]
  },
  { prop: 'ref_doc', label: '来源单据', type: 'input', placeholder: '如 WO202611-0001' },
  { prop: 'agv', label: 'AGV', type: 'select', options: [] }
])

const columns = [
  { prop: 'code', label: '任务编号 / 来源', width: 175, fixed: 'left', slot: 'code' },
  { prop: 'task_type_label', label: '类型', width: 85, slot: 'type' },
  { prop: 'from', label: '起点', minWidth: 140, slot: 'from' },
  { prop: 'to', label: '终点', minWidth: 140, slot: 'to' },
  { prop: 'qty', label: '数量', width: 75, slot: 'qty' },
  { prop: 'priority', label: '优先级', width: 80, slot: 'priority' },
  { prop: 'status', label: '状态', width: 95, slot: 'status' },
  { prop: 'agv_code', label: '执行车', width: 90 },
  { prop: 'distance_mm', label: '里程', width: 115, slot: 'distance' },
  { prop: 'actions', label: '操作', width: 175, slot: 'actions', fixed: 'right' }
]

const detailVisible = ref(false)
const current = ref(null)

const priorityTag = (p) => (p <= 1 ? 'danger' : p <= 2 ? 'warning' : 'info')

function statusTag(status) {
  return {
    pending: 'info', assigned: 'warning', running: 'primary',
    done: 'success', cancelled: 'info'
  }[status] || 'info'
}

function canCancel(row) {
  return row.status === 'pending' || row.status === 'assigned'
}

/** 毫米 → 米；空值返回 "—"，避免页面出现 "0 m" 被当成"不用跑" */
function toMeters(mm) {
  if (mm === null || mm === undefined || mm === '') return '—'
  return Math.round(Number(mm) / 10) / 100 + ' m'
}

function pct(v) {
  return ((Number(v) || 0) * 100).toFixed(1) + '%'
}

/** 数量是 decimal(12,3)，接口给 "1.000"；去掉无意义的尾零，1 就显示 1 */
function trimQty(qty) {
  const n = Number(qty)
  return Number.isInteger(n) ? String(n) : String(n)
}

function fmtTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 16)
}

async function loadBoard() {
  try {
    Object.assign(board, await fetchTaskBoard())
  } catch (e) {
    console.warn('[TransportTaskList] 看板加载失败', e)
  }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchTransportTasks({
      page: page.value, page_size: pageSize.value, ...query.value
    })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    // request 拦截器已弹过提示，这里只留日志，避免一次失败弹两条
    console.error('[TransportTaskList] 加载失败', e)
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await Promise.all([load(), loadBoard()])
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

function showDetail(row) {
  current.value = row
  detailVisible.value = true
}

async function onAssign(row) {
  try {
    const res = await assignTask(row.id)
    const meters = toMeters(res?.empty_distance_mm)
    ElMessage.success(`已派 ${res?.agv?.code || ''}，空驶 ${meters}`)
    await refreshAll()
  } catch (e) {
    // 拦截器已提示（没车 / 载重不够 / 电量不足）
  }
}

async function onStart(row) {
  try {
    await changeTaskStatus(row.id, { status: 'running' })
    ElMessage.success('已开始')
    await refreshAll()
  } catch (e) {
    // 拦截器已提示
  }
}

async function onDone(row) {
  try {
    await changeTaskStatus(row.id, { status: 'done' })
    ElMessage.success('已完成')
    await refreshAll()
  } catch (e) {
    // 拦截器已提示
  }
}

async function onCancel(row) {
  const confirmed = await ElMessageBox.confirm(
    `取消任务 ${row.code}？取消后不能恢复。`, '取消任务',
    { confirmButtonText: '取消任务', cancelButtonText: '再想想', type: 'warning' }
  ).catch(() => false)
  if (!confirmed) return
  try {
    await changeTaskStatus(row.id, { status: 'cancelled', reason: '页面手工取消' })
    ElMessage.success('已取消')
    await refreshAll()
  } catch (e) {
    // 拦截器已提示
  }
}

async function onAssignPending() {
  assigning.value = true
  try {
    const res = await assignPendingTasks({ limit: 50 })
    const failed = (res?.results || []).filter((r) => !r.ok)
    if (failed.length) {
      ElMessage.warning(
        `派了 ${res.assigned}/${res.total} 单，${failed.length} 单失败：`
        + `${failed[0].code || ''} ${failed[0].message || failed[0].reason || ''}`
      )
    } else {
      ElMessage.success(`已派完 ${res.assigned} 单`)
    }
    await refreshAll()
  } catch (e) {
    // 拦截器已提示
  } finally {
    assigning.value = false
  }
}

onMounted(async () => {
  try {
    const data = await fetchAgvs({ page: 1, page_size: 100 })
    agvOptions.value = (data && data.results) || data || []
    const field = searchFields.value.find((f) => f.prop === 'agv')
    if (field) {
      field.options = agvOptions.value.map((a) => ({ value: a.id, label: a.code }))
    }
  } catch (e) {
    console.warn('[TransportTaskList] AGV 列表加载失败', e)
  }
  await refreshAll()
})
</script>
