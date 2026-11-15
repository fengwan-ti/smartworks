<template>
  <div class="sw-page">
    <div class="sw-metrics">
      <div class="sw-metric" :class="{ 'sw-metric--warn': stats.open_orders > 0 }">
        <div class="sw-metric__label">未完成工单</div>
        <div class="sw-metric__value">{{ stats.open_orders }}<span class="sw-metric__unit">张</span></div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">已完修</div>
        <div class="sw-metric__value">{{ stats.done_orders }}<span class="sw-metric__unit">张</span></div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">累计停机</div>
        <div class="sw-metric__value">{{ stats.total_downtime_minutes }}<span class="sw-metric__unit">分钟</span></div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">平均停机 MTTR</div>
        <div class="sw-metric__value">{{ stats.mttr_minutes }}<span class="sw-metric__unit">分钟</span></div>
        <div class="sw-metric__foot">
          <template v-for="t in stats.by_type || []" :key="t.type">
            {{ typeLabel(t.type) }} {{ t.count }}&nbsp;
          </template>
        </div>
      </div>
    </div>

    <div class="sw-card">
      <div class="sw-toolbar">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <span class="sw-sub" style="margin-left: auto; align-self: center">
          状态只能通过 派工 → 开始 → 完工 三个动作推进，不能直接改
        </span>
      </div>

      <SearchForm
        :fields="searchFields"
        :loading="loading"
        @search="onSearch"
        @reset="onReset"
      />

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
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
        <template #equipment="{ row }">
          <div>{{ row.equipment_code }}</div>
          <div class="sw-sub">{{ row.equipment_name }}</div>
        </template>
        <template #fault="{ row }">
          <span :title="row.fault_desc">{{ row.fault_desc || '—' }}</span>
        </template>
        <template #downtime="{ row }">
          <span v-if="row.downtime_minutes">{{ row.downtime_minutes }} 分</span>
          <span v-else class="sw-sub">—</span>
        </template>
        <template #created="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
        <template #actions="{ row }">
          <el-button v-if="!row.assignee" link type="primary" @click="onAssign(row)">
            派工
          </el-button>
          <el-button
            v-if="row.status === 'assigned'"
            link
            type="primary"
            @click="onStart(row)"
          >
            开始
          </el-button>
          <el-button
            v-if="row.status === 'processing'"
            link
            type="success"
            @click="openFinish(row)"
          >
            完工
          </el-button>
          <el-button v-if="row.alarm_code" link @click="showDetail(row)">详情</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="finishVisible" title="完工登记" width="560px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        title="停机时长由现场填写，不用开始/结束时间相减"
        description="中间等备件、等班次的时间不属于维修时间，相减会把 MTTR 算大。"
      />
      <el-form ref="finishRef" :model="finishForm" :rules="finishRules" label-width="90px">
        <el-form-item label="停机时长" prop="downtime_minutes">
          <el-input-number v-model="finishForm.downtime_minutes" :min="0" :step="10" />
          <span class="sw-sub" style="margin-left: 8px">分钟</span>
        </el-form-item>
        <el-form-item label="原因分析">
          <el-input v-model="finishForm.cause" type="textarea" :rows="2"
                    placeholder="如：主轴轴承磨损" />
        </el-form-item>
        <el-form-item label="处理措施">
          <el-input v-model="finishForm.action" type="textarea" :rows="2"
                    placeholder="如：更换 6205 轴承、复测振动 3.2 mm/s" />
        </el-form-item>
        <el-form-item label="更换备件">
          <el-input v-model="finishForm.spare_parts" placeholder="如：6205 轴承 ×2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="finishVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onFinish">确认完工</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="工单详情" size="440px">
      <el-descriptions v-if="current" :column="1" border>
        <el-descriptions-item label="工单编号">{{ current.code }}</el-descriptions-item>
        <el-descriptions-item label="设备">
          {{ current.equipment_code }} {{ current.equipment_name }}
        </el-descriptions-item>
        <el-descriptions-item label="来源告警">{{ current.alarm_code || '—' }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ current.order_type_label }}</el-descriptions-item>
        <el-descriptions-item label="优先级">P{{ current.priority }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ current.status_label }}</el-descriptions-item>
        <el-descriptions-item label="维修人">{{ current.assignee_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="故障现象">{{ current.fault_desc || '—' }}</el-descriptions-item>
        <el-descriptions-item label="原因分析">{{ current.cause || '—' }}</el-descriptions-item>
        <el-descriptions-item label="处理措施">{{ current.action || '—' }}</el-descriptions-item>
        <el-descriptions-item label="更换备件">{{ current.spare_parts || '—' }}</el-descriptions-item>
        <el-descriptions-item label="停机">
          {{ current.downtime_minutes ? `${current.downtime_minutes} 分钟` : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="实际开始">
          {{ current.started_at ? formatTime(current.started_at) : '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="实际完成">
          {{ current.finished_at ? formatTime(current.finished_at) : '—' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * 维修工单（W4）。
 *
 * 工单不是"告警的附属物"：计划保养也必须开一张，所以这张表能独立新建。
 * 状态机只有三条边：
 *   created --assign--> assigned --start--> processing --finish--> done
 * 页面只暴露这三个动作按钮，不提供状态下拉 —— 跳过"开始"直接完工，
 * 会让 started_at 空着，后面的工时统计全是错的。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  assignMaintenance,
  fetchAlarmStats,
  fetchMaintenanceOrders,
  finishMaintenance,
  startMaintenance
} from '@/api/equipment'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const stats = ref({
  open_orders: 0, done_orders: 0, total_downtime_minutes: 0,
  mttr_minutes: 0, by_type: []
})

const searchFields = ref([
  { prop: 'equipment_code', label: '设备编码', type: 'input', placeholder: '如 EQ-DR-01' },
  {
    prop: 'status', label: '状态', type: 'select',
    options: [
      { value: 'created', label: '待派工' },
      { value: 'assigned', label: '已派工' },
      { value: 'processing', label: '维修中' },
      { value: 'done', label: '已完工' }
    ]
  },
  {
    prop: 'order_type', label: '类型', type: 'select',
    options: [
      { value: 'corrective', label: '故障维修' },
      { value: 'preventive', label: '计划保养' }
    ]
  }
])

const columns = [
  { prop: 'code', label: '工单编号', width: 150 },
  { prop: 'equipment', label: '设备', width: 150, slot: 'equipment' },
  { prop: 'alarm_code', label: '来源告警', width: 140 },
  { prop: 'order_type_label', label: '类型', width: 100 },
  { prop: 'priority', label: '优先级', width: 90, slot: 'priority' },
  { prop: 'status', label: '状态', width: 100, slot: 'status' },
  { prop: 'assignee_name', label: '维修人', width: 100 },
  { prop: 'fault', label: '故障现象', minWidth: 180, slot: 'fault' },
  { prop: 'downtime_minutes', label: '停机', width: 90, slot: 'downtime' },
  { prop: 'created_at', label: '创建时间', width: 150, slot: 'created' },
  { prop: 'actions', label: '操作', width: 160, slot: 'actions' }
]

const finishVisible = ref(false)
const finishRef = ref()
const finishForm = reactive({
  id: null, downtime_minutes: 30, cause: '', action: '', spare_parts: ''
})
const finishRules = {
  downtime_minutes: [{ required: true, message: '请填写停机时长', trigger: 'blur' }]
}

const detailVisible = ref(false)
const current = ref(null)

function typeLabel(type) {
  return { corrective: '故障', preventive: '保养', predictive: '预测' }[type] || type
}

function priorityTag(priority) {
  if (priority <= 1) return 'danger'
  if (priority <= 2) return 'warning'
  return 'info'
}

function statusTag(status) {
  return {
    created: 'info', assigned: 'warning', processing: 'primary',
    done: 'success', cancelled: 'info'
  }[status] || 'info'
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 16) : '—'
}

async function loadStats() {
  try {
    stats.value = await fetchAlarmStats()
  } catch (e) {
    console.error('[MaintenanceList] 指标加载失败', e)
  }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchMaintenanceOrders({
      page: page.value, page_size: pageSize.value, ...query.value
    })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[MaintenanceList] 加载工单失败', e)
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

async function refreshAll() {
  await Promise.all([load(), loadStats()])
}

async function onAssign(row) {
  try {
    await assignMaintenance(row.id)
    ElMessage.success('已派工')
    await refreshAll()
  } catch (e) {
    // 已提示
  }
}

async function onStart(row) {
  const confirmed = await ElMessageBox.confirm(
    `确认开始维修 ${row.code}（${row.equipment_code}）？开始时间会被记下来。`,
    '开始维修',
    { confirmButtonText: '开始', cancelButtonText: '取消' }
  ).catch(() => false)
  if (!confirmed) return
  try {
    await startMaintenance(row.id)
    ElMessage.success('已开始')
    await refreshAll()
  } catch (e) {
    // 已提示
  }
}

function openFinish(row) {
  Object.assign(finishForm, {
    id: row.id,
    downtime_minutes: row.downtime_minutes || 30,
    cause: row.cause || '',
    action: row.action || '',
    spare_parts: row.spare_parts || ''
  })
  finishVisible.value = true
}

async function onFinish() {
  const ok = await finishRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await finishMaintenance(finishForm.id, {
      downtime_minutes: finishForm.downtime_minutes,
      cause: finishForm.cause,
      action: finishForm.action,
      spare_parts: finishForm.spare_parts
    })
    ElMessage.success('已完工')
    finishVisible.value = false
    await refreshAll()
  } catch (e) {
    // 已提示
  } finally {
    saving.value = false
  }
}

function showDetail(row) {
  current.value = row
  detailVisible.value = true
}

onMounted(() => {
  load()
  loadStats()
})
</script>
