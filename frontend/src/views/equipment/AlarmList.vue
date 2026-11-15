<template>
  <div class="sw-page">
    <!-- 指标卡：四个数就是「设备现在健不健康」的一句话回答 -->
    <div class="sw-metrics">
      <div class="sw-metric" :class="{ 'sw-metric--warn': stats.open_alarms > 0 }">
        <div class="sw-metric__label">未关闭告警</div>
        <div class="sw-metric__value">{{ stats.open_alarms }}<span class="sw-metric__unit">条</span></div>
        <div class="sw-metric__foot">含已确认未关闭</div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--danger': stats.critical_alarms > 0 }">
        <div class="sw-metric__label">严重告警</div>
        <div class="sw-metric__value">{{ stats.critical_alarms }}<span class="sw-metric__unit">条</span></div>
        <div class="sw-metric__foot">critical 等级未关闭</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">未完成维修工单</div>
        <div class="sw-metric__value">{{ stats.open_orders }}<span class="sw-metric__unit">张</span></div>
        <div class="sw-metric__foot">已完修 {{ stats.done_orders }} 张</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">平均停机 MTTR</div>
        <div class="sw-metric__value">{{ stats.mttr_minutes }}<span class="sw-metric__unit">分钟</span></div>
        <div class="sw-metric__foot">只统计已完修工单</div>
      </div>
    </div>

    <div class="sw-card">
      <div class="sw-toolbar">
        <el-button type="primary" :loading="scanning" @click="onScan">扫描阈值告警</el-button>
        <el-button @click="reportVisible = true">人工上报</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
        <span class="sw-sub" style="margin-left: auto; align-self: center">
          阈值来源 services.ALARM_RULES：振动 1.8/2.4、温度 55/65、电流 11/13（左警告右严重），
          同类 60 分钟内不重复报
        </span>
      </div>

      <SearchForm
        :fields="searchFields"
        :loading="loading"
        @search="onSearch"
        @reset="onReset"
      />

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #level="{ row }">
          <el-tag :type="levelTag(row.level)" size="small" effect="dark">
            {{ row.level_label }}
          </el-tag>
        </template>
        <template #metric="{ row }">
          <span v-if="row.metric_value !== null">
            {{ row.metric_value }} / {{ row.threshold }}
          </span>
          <span v-else class="sw-sub">—</span>
        </template>
        <template #status="{ row }">
          <el-tag :type="statusTag(row.status)" size="small" effect="light">
            {{ row.status_label }}
          </el-tag>
        </template>
        <template #occurred="{ row }">
          {{ formatTime(row.occurred_at) }}
        </template>
        <template #actions="{ row }">
          <el-button v-if="row.status === 'open'" link type="primary" @click="onAck(row)">
            确认
          </el-button>
          <el-button v-if="row.status !== 'closed'" link type="danger" @click="onClose(row)">
            关闭
          </el-button>
          <el-button link @click="showDetail(row)">详情</el-button>
        </template>
      </BaseTable>
    </div>

    <!-- 人工上报：只写 source=manual，不改已有记录 -->
    <el-dialog v-model="reportVisible" title="人工上报告警" width="520px">
      <el-form ref="reportRef" :model="report" :rules="reportRules" label-width="90px">
        <el-form-item label="设备" prop="equipment">
          <el-select v-model="report.equipment" filterable placeholder="请选择设备" style="width: 100%">
            <el-option
              v-for="e in equipmentOptions"
              :key="e.id"
              :label="`${e.code} ${e.name}`"
              :value="e.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="等级" prop="level">
          <el-radio-group v-model="report.level">
            <el-radio-button value="info">提示</el-radio-button>
            <el-radio-button value="warning">警告</el-radio-button>
            <el-radio-button value="critical">严重</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述" prop="message">
          <el-input v-model="report.message" type="textarea" :rows="3"
                    placeholder="现场看到什么就写什么，例如：主轴异响、转速不稳" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onReport">上报</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="告警详情" size="420px">
      <el-descriptions v-if="current" :column="1" border>
        <el-descriptions-item label="告警编号">{{ current.code }}</el-descriptions-item>
        <el-descriptions-item label="设备">
          {{ current.equipment_code }} {{ current.equipment_name }}
        </el-descriptions-item>
        <el-descriptions-item label="等级">{{ current.level_label }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ current.source_label }}</el-descriptions-item>
        <el-descriptions-item label="触发通道">
          {{ current.channel_label || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="规则">{{ current.rule || '—' }}</el-descriptions-item>
        <el-descriptions-item label="触发值 / 阈值">
          {{ current.metric_value ?? '—' }} / {{ current.threshold ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="描述">{{ current.message }}</el-descriptions-item>
        <el-descriptions-item label="发生时间">{{ formatTime(current.occurred_at) }}</el-descriptions-item>
        <el-descriptions-item label="确认人">
          {{ current.acked_by_name || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="关闭时间">
          {{ current.closed_at ? formatTime(current.closed_at) : '—' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * 告警看板（W4）。
 *
 * 这一页的定位不是"告警列表"，而是「设备现在能不能干活」的一屏判断：
 * 上面四个数给出结论，下面表格给出来源。
 *
 * 三个动作有严格区分，别混：
 *   扫描   —— 按阈值规则检查最新读数，生成新告警（会顺手给 critical 开维修工单）
 *   确认   —— 表示"人看到了，正在处理"，告警还在
 *   关闭   —— 表示"这事结束了"，才能从指标卡里消失
 */
import { onMounted, reactive, ref } from 'vue'
import { usePolling } from '@/composables/usePolling'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  ackAlarm,
  closeAlarm,
  createAlarm,
  fetchAlarmStats,
  fetchAlarms,
  fetchEquipments,
  scanAlarms
} from '@/api/equipment'

const loading = ref(false)
const saving = ref(false)
const scanning = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const stats = ref({
  open_alarms: 0, critical_alarms: 0, open_orders: 0,
  done_orders: 0, mttr_minutes: 0
})
const equipmentOptions = ref([])

const searchFields = ref([
  { prop: 'equipment_code', label: '设备编码', type: 'input', placeholder: '如 EQ-DR-01' },
  {
    prop: 'level', label: '等级', type: 'select',
    options: [
      { value: 'info', label: '提示' },
      { value: 'warning', label: '警告' },
      { value: 'critical', label: '严重' }
    ]
  },
  {
    prop: 'status', label: '状态', type: 'select',
    options: [
      { value: 'open', label: '待处理' },
      { value: 'acked', label: '已确认' },
      { value: 'closed', label: '已关闭' }
    ]
  }
])

const columns = [
  { prop: 'code', label: '告警编号', width: 150 },
  { prop: 'equipment_code', label: '设备', width: 110 },
  { prop: 'level', label: '等级', width: 90, slot: 'level' },
  { prop: 'channel_label', label: '通道', width: 100 },
  { prop: 'metric', label: '触发值/阈值', width: 130, slot: 'metric' },
  { prop: 'message', label: '描述', minWidth: 200 },
  { prop: 'occurred_at', label: '发生时间', width: 160, slot: 'occurred' },
  { prop: 'status', label: '状态', width: 100, slot: 'status' },
  { prop: 'actions', label: '操作', width: 170, slot: 'actions' }
]

const reportVisible = ref(false)
const reportRef = ref()
const report = reactive({ equipment: null, level: 'warning', message: '' })
const reportRules = {
  equipment: [{ required: true, message: '请选择设备', trigger: 'change' }],
  message: [{ required: true, message: '请填写现场现象', trigger: 'blur' }]
}

const detailVisible = ref(false)
const current = ref(null)

function levelTag(level) {
  return { info: 'info', warning: 'warning', critical: 'danger' }[level] || 'info'
}

function statusTag(status) {
  return { open: 'danger', acked: 'warning', closed: 'info' }[status] || 'info'
}

/** 后端给的是 ISO 字符串，直接截到分钟，比 new Date 稳妥（不受时区影响） */
function formatTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 16) : '—'
}

async function loadStats() {
  try {
    stats.value = await fetchAlarmStats()
  } catch (e) {
    console.error('[AlarmList] 指标加载失败', e)
  }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchAlarms({ page: page.value, page_size: pageSize.value, ...query.value })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[AlarmList] 加载告警失败', e)
  } finally {
    loading.value = false
  }
}

async function loadEquipments() {
  try {
    const data = await fetchEquipments({ page_size: 100 })
    equipmentOptions.value = (data && data.results) || []
  } catch (e) {
    console.error('[AlarmList] 设备下拉加载失败', e)
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

async function onScan() {
  scanning.value = true
  try {
    const result = await scanAlarms({})
    const created = result.triggered_count || 0
    if (created > 0) {
      const tickets = (result.triggered || []).filter((r) => r.maintenance_code).length
      ElMessage.success(
        tickets
          ? `扫出 ${created} 条新告警，自动开维修工单 ${tickets} 张`
          : `扫出 ${created} 条新告警`
      )
    } else {
      ElMessage.info('读数都在阈值内，没有新告警')
    }
    await Promise.all([load(), loadStats()])
  } catch (e) {
    // request.js 已提示
  } finally {
    scanning.value = false
  }
}

async function onReport() {
  const ok = await reportRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createAlarm({ ...report })
    ElMessage.success('已上报')
    reportVisible.value = false
    Object.assign(report, { equipment: null, level: 'warning', message: '' })
    await Promise.all([load(), loadStats()])
  } catch (e) {
    // 已提示
  } finally {
    saving.value = false
  }
}

async function onAck(row) {
  try {
    await ackAlarm(row.id)
    ElMessage.success('已确认')
    await Promise.all([load(), loadStats()])
  } catch (e) {
    // 已提示
  }
}

async function onClose(row) {
  // 关闭要写一句原因：误报率、规则质量都靠这句话统计
  const { value } = await ElMessageBox.prompt(
    '关闭代表这事结束了。若属于误报，写一句原因便于后续调阈值。',
    '关闭告警',
    {
      confirmButtonText: '关闭',
      cancelButtonText: '取消',
      inputPlaceholder: '如：误报，传感器抖动',
      inputValue: ''
    }
  ).catch(() => ({ value: undefined }))
  if (value === undefined) return
  try {
    await closeAlarm(row.id, { remark: value })
    ElMessage.success('已关闭')
    await Promise.all([load(), loadStats()])
  } catch (e) {
    // 已提示
  }
}

function showDetail(row) {
  current.value = row
  detailVisible.value = true
}

// 告警每 30 秒自动刷新：设备报警要能自己冒出来，不能等人刷新
usePolling(load, 30000)

onMounted(() => {
  load()
  loadStats()
  loadEquipments()
})
</script>
