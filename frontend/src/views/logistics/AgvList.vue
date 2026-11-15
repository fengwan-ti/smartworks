<template>
  <div class="sw-page">
    <div class="sw-metrics">
      <div class="sw-metric">
        <div class="sw-metric__label">车辆总数</div>
        <div class="sw-metric__value">{{ agvs.length }}<span class="sw-metric__unit">台</span></div>
        <div class="sw-metric__foot">载重分别是
          {{ agvs.map((a) => a.capacity_kg).join(' / ') || '—' }} kg</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">空闲</div>
        <div class="sw-metric__value">{{ countBy('idle') }}<span class="sw-metric__unit">台</span></div>
        <div class="sw-metric__foot">只有空闲车能被派活</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">运行中</div>
        <div class="sw-metric__value">{{ countBy('running') }}<span class="sw-metric__unit">台</span></div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--danger': lowBattery.length > 0 }">
        <div class="sw-metric__label">低电量（&lt;30%）</div>
        <div class="sw-metric__value">{{ lowBattery.length }}<span class="sw-metric__unit">台</span></div>
        <div class="sw-metric__foot">
          {{ lowBattery.length ? lowBattery.map((a) => a.code).join('、') : '都还有电' }}
        </div>
      </div>
    </div>

    <div class="sw-card">
      <div class="sw-toolbar">
        <span style="font-weight: 600">AGV 台账</span>
        <el-select v-model="filter.status" clearable placeholder="全部状态"
                   style="width: 140px; margin-left: 12px" @change="load">
          <el-option label="空闲" value="idle" />
          <el-option label="运行中" value="running" />
          <el-option label="充电中" value="charging" />
          <el-option label="维护中" value="maintenance" />
        </el-select>
        <el-button :loading="loading" style="margin-left: auto" @click="refreshAll">刷新</el-button>
        <el-button @click="openEdit()">新增车辆</el-button>
      </div>

      <BaseTable :columns="columns" :rows="agvs" :total="agvs.length" :show-pagination="false">
        <template #name="{ row }">
          <div>{{ row.name }}</div>
          <div class="sw-sub remark" :title="row.remark">{{ row.remark || '—' }}</div>
        </template>
        <template #battery="{ row }">
          <div class="battery-cell">
            <el-progress :percentage="Number(row.battery)" :stroke-width="10"
                         :status="batteryStatus(row.battery)" :show-text="false"
                         style="flex: 1" />
            <span class="battery-num">{{ Number(row.battery).toFixed(0) }}%</span>
          </div>
        </template>
        <template #status="{ row }">
          <el-tag :type="statusTag(row.status)" size="small" effect="light">
            {{ row.status_label }}
          </el-tag>
        </template>
        <template #active="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" :disabled="row.status === 'running'"
                     @click="onCharge(row)">
            充电
          </el-button>
          <el-button link @click="openEdit(row)">编辑</el-button>
        </template>
      </BaseTable>
    </div>

    <!-- 工作量：答辩问「这几台车到底跑了多少」时看这张 -->
    <div class="sw-card">
      <div class="sw-toolbar">
        <span style="font-weight: 600">累计工作量</span>
        <span class="sw-sub" style="align-self: center">
          空驶里程 ÷（空驶 + 载货）就是这台车的空驶率，W5 调度要压的就是它
        </span>
      </div>
      <BaseTable :columns="workloadColumns" :rows="workload" :total="workload.length"
                 :show-pagination="false">
        <template #status="{ row }">
          <el-tag :type="statusTag(row.status)" size="small" effect="plain">
            {{ row.status_label }}
          </el-tag>
        </template>
        <template #loaded="{ row }">{{ toKm(row.loaded_mm) }}</template>
        <template #empty="{ row }">{{ toKm(row.empty_mm) }}</template>
        <template #ratio="{ row }">
          <span :class="{ 'sw-danger-text': row.empty_ratio >= 0.5 }">
            {{ (row.empty_ratio * 100).toFixed(1) }}%
          </span>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="editVisible" :title="form.id ? '编辑 AGV' : '新增 AGV'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
        <el-form-item label="车辆编码" prop="code">
          <el-input v-model="form.code" :disabled="!!form.id" placeholder="如 AGV-04" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 4# 举升式 AGV" />
        </el-form-item>
        <el-form-item label="载重(kg)" prop="capacity_kg">
          <el-input-number v-model="form.capacity_kg" :min="1" :step="100" />
        </el-form-item>
        <el-form-item label="速度(mm/s)" prop="speed">
          <el-input-number v-model="form.speed" :min="1" :step="100" />
          <span class="sw-sub" style="margin-left: 8px">1000 mm/s = 3.6 km/h</span>
        </el-form-item>
        <el-form-item label="电量/状态">
          <span class="sw-sub">电量 {{ form.battery }}% · {{ statusLabel(form.status) }}</span>
          <span class="sw-sub" style="margin-left: 8px">这两项由充电和跑任务改</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * AGV 台账（角色 D，W3/W5）。
 *
 * 只看三件事：每台车**能拉多重**、**还有多少电**、**现在在哪个节点**。
 * 派车逻辑（logistics/services.py::assign_agv）算空驶距离就是从这个节点起算的，
 * 所以 current_node 显示成节点号而不是工位名 —— 工位名在路网上对不到点。
 *
 * 「充电」现在是直接充满（W6 才换成插桩后慢慢充），
 * 正在跑任务的车后端会拒（14506），前端也先禁用，避免点了才知道不行。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BaseTable from '@/components/BaseTable.vue'
import request from '@/utils/request'
import { fetchAgvs, fetchAgvWorkload, chargeAgv } from '@/api/logistics'

const loading = ref(false)
const saving = ref(false)
const agvs = ref([])
const workload = ref([])
const filter = reactive({ status: '' })

const columns = [
  { prop: 'code', label: '编码', width: 100, fixed: 'left' },
  { prop: 'name', label: '名称 / 备注', minWidth: 170, slot: 'name' },
  { prop: 'capacity_kg', label: '载重(kg)', width: 100 },
  { prop: 'speed', label: '速度(mm/s)', width: 115 },
  { prop: 'battery', label: '电量', width: 170, slot: 'battery' },
  { prop: 'status', label: '状态', width: 95, slot: 'status' },
  { prop: 'current_node_code', label: '当前节点', width: 105 },
  { prop: 'is_active', label: '启用', width: 85, slot: 'active' },
  { prop: 'actions', label: '操作', width: 125, slot: 'actions', fixed: 'right' }
]

const workloadColumns = [
  { prop: 'code', label: '编码', width: 110 },
  { prop: 'name', label: '名称', minWidth: 150 },
  { prop: 'status', label: '当前状态', width: 110, slot: 'status' },
  { prop: 'done_tasks', label: '已完成', width: 100 },
  { prop: 'running_tasks', label: '进行中', width: 100 },
  { prop: 'loaded_mm', label: '载货里程', width: 120, slot: 'loaded' },
  { prop: 'empty_mm', label: '空驶里程', width: 120, slot: 'empty' },
  { prop: 'ratio', label: '空驶率', width: 100, slot: 'ratio' }
]

const lowBattery = computed(() =>
  agvs.value.filter((a) => Number(a.battery) < 30 && a.is_active))

function countBy(status) {
  return agvs.value.filter((a) => a.status === status).length
}

function statusTag(status) {
  return {
    idle: 'success', running: 'primary', charging: 'warning', maintenance: 'info'
  }[status] || 'info'
}

function statusLabel(status) {
  return {
    idle: '空闲', running: '运行中', charging: '充电中', maintenance: '维护中'
  }[status] || status || '—'
}

function batteryStatus(battery) {
  const v = Number(battery)
  if (v < 20) return 'exception'
  if (v < 30) return 'warning'
  return 'success'
}

/** 毫米 → 米（车间尺度，用 km 全是 0.0x，看不出差别） */
function toKm(mm) {
  if (!mm) return '0 m'
  return Math.round(Number(mm) / 1000) + ' m'
}

async function load() {
  loading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    if (filter.status) params.status = filter.status
    const data = await fetchAgvs(params)
    agvs.value = (data && data.results) || data || []
  } catch (e) {
    // request 拦截器已弹过提示，这里只留日志，避免一次失败弹两条
    console.error('[AgvList] 加载失败', e)
  } finally {
    loading.value = false
  }
}

async function loadWorkload() {
  try {
    const data = await fetchAgvWorkload()
    workload.value = (data || []).map((row) => {
      const loaded = Number(row.loaded_mm || 0)
      const empty = Number(row.empty_mm || 0)
      const total = loaded + empty
      return { ...row, empty_ratio: total ? empty / total : 0 }
    })
  } catch (e) {
    console.warn('[AgvList] 工作量加载失败', e)
  }
}

async function refreshAll() {
  await Promise.all([load(), loadWorkload()])
}

const editVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, code: '', name: '', capacity_kg: 500, speed: 1000,
  battery: 100, status: 'idle', is_active: true, remark: ''
})
const rules = {
  code: [{ required: true, message: '请填车辆编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填车辆名称', trigger: 'blur' }]
}

function openEdit(row) {
  Object.assign(form, row
    ? {
        id: row.id, code: row.code, name: row.name,
        capacity_kg: Number(row.capacity_kg), speed: Number(row.speed),
        battery: Number(row.battery), status: row.status,
        is_active: row.is_active, remark: row.remark || ''
      }
    : {
        id: null, code: '', name: '', capacity_kg: 500, speed: 1000,
        battery: 100, status: 'idle', is_active: true, remark: ''
      })
  editVisible.value = true
}

async function onSave() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    // battery / status 不进 body：充放电和派车才是它们的唯一入口
    const payload = {
      code: form.code, name: form.name,
      capacity_kg: form.capacity_kg, speed: form.speed,
      is_active: form.is_active, remark: form.remark
    }
    if (form.id) {
      await request.patch(`/logistics/agvs/${form.id}/`, payload)
    } else {
      await request.post('/logistics/agvs/', payload)
    }
    ElMessage.success(form.id ? '已保存' : '已新增')
    editVisible.value = false
    await refreshAll()
  } catch (e) {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

async function onCharge(row) {
  const confirmed = await ElMessageBox.confirm(
    `给 ${row.code} 充电？电量会直接补到 100%，状态回到空闲。`,
    '充电',
    { confirmButtonText: '充电', cancelButtonText: '取消' }
  ).catch(() => false)
  if (!confirmed) return
  try {
    await chargeAgv(row.id)
    ElMessage.success(`${row.code} 已充满`)
    await refreshAll()
  } catch (e) {
    // 拦截器已提示（跑任务中会报 14506）
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.battery-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 备注是说明性文字，一行放不下就省略，鼠标停上去看全文（换行会把三行表撑到五行的厚度） */
.remark {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.battery-num {
  width: 42px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-size: 13px;
}
.sw-danger-text {
  color: #d9534f;
  font-weight: 600;
}
</style>
