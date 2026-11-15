<template>
  <div class="sw-page">
    <!-- 台账顶部只放"有多少台、状态怎么分布"，不放产量 —— 产量在 OEE 页 -->
    <div class="sw-metrics">
      <div class="sw-metric">
        <div class="sw-metric__label">设备总数</div>
        <div class="sw-metric__value">{{ total }}<span class="sw-metric__unit">台</span></div>
        <div class="sw-metric__foot">{{ activeCount }} 台在用 · {{ total - activeCount }} 台停用</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">正常</div>
        <div class="sw-metric__value">{{ statusCount.normal || 0 }}<span class="sw-metric__unit">台</span></div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--warn': statusCount.wearing > 0 }">
        <div class="sw-metric__label">磨损</div>
        <div class="sw-metric__value">{{ statusCount.wearing || 0 }}<span class="sw-metric__unit">台</span></div>
        <div class="sw-metric__foot">还能干活，排产优先级要往后排</div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--danger': statusCount.abnormal > 0 }">
        <div class="sw-metric__label">异常</div>
        <div class="sw-metric__value">{{ statusCount.abnormal || 0 }}<span class="sw-metric__unit">台</span></div>
        <div class="sw-metric__foot">不参与排产，需先修</div>
      </div>
    </div>

    <div class="sw-card">
      <div class="sw-toolbar">
        <span style="font-weight: 600">设备台账</span>
        <el-button :loading="loading" style="margin-left: auto" @click="load">刷新</el-button>
        <span class="sw-sub" style="align-self: center">
          状态由运行监测/维修流程改，这里不能直接编辑
        </span>
      </div>

      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button @click="openEdit()">新增设备</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <el-tag :type="statusTag(row.status)" size="small" effect="light">
            {{ row.status_label }}
          </el-tag>
        </template>
        <template #name="{ row }">
          <div>{{ row.name }}</div>
          <div class="sw-sub">{{ row.model || '未填型号' }}</div>
        </template>
        <template #workshop="{ row }">
          <div>{{ row.workshop_name || '—' }}</div>
          <div class="sw-sub">{{ row.workstation_name || '' }}</div>
        </template>
        <template #capabilities="{ row }">
          <template v-if="row.capabilities && row.capabilities.length">
            <el-tag v-for="c in row.capabilities" :key="c.id" size="small" effect="plain"
                    style="margin: 1px 4px 1px 0">
              {{ c.step_type_label }}
            </el-tag>
          </template>
          <span v-else class="sw-sub">未登记能力</span>
        </template>
        <template #active="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
            {{ row.is_active ? '在用' : '停用' }}
          </el-tag>
          <el-tag v-if="row.oee_excluded" type="warning" size="small" effect="plain"
                  style="margin-left: 4px" title="不参与 OEE 统计">
            不计 OEE
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="showDetail(row)">能力</el-button>
          <el-button link @click="openEdit(row)">编辑</el-button>
        </template>
      </BaseTable>
    </div>

    <!-- 能力抽屉：一台设备能干什么，是排产能不能用它的唯一依据 -->
    <el-drawer v-model="detailVisible" :title="`设备能力 · ${current?.code || ''}`" size="560px">
      <template v-if="current">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 14px">
          <el-descriptions-item label="名称">{{ current.name }}</el-descriptions-item>
          <el-descriptions-item label="型号">{{ current.model || '—' }}</el-descriptions-item>
          <el-descriptions-item label="厂商">{{ current.manufacturer || '—' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ current.status_label }}</el-descriptions-item>
          <el-descriptions-item label="车间">{{ current.workshop_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="工位">{{ current.workstation_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="AGV 装卸点">{{ current.agv_load_point || '—' }}</el-descriptions-item>
          <el-descriptions-item label="投用日期">{{ current.install_date || '—' }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="current.capabilities || []" border size="small" empty-text="该设备还没有登记能力">
          <el-table-column prop="step_type_label" label="工序" width="100" />
          <el-table-column prop="precision_level_label" label="精度" width="90" />
          <el-table-column prop="capacity_per_hour" label="产能(件/h)" width="110" />
          <el-table-column prop="setup_minutes" label="换型(min)" width="100" />
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
                {{ row.is_active ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <p class="sw-sub" style="margin-top: 10px">
          换型时间在这里叫 setup_minutes，排产接口出口叫 changeover_minutes，
          同一个数、不是两列。
        </p>
      </template>
    </el-drawer>

    <el-dialog v-model="editVisible" :title="form.id ? '编辑设备' : '新增设备'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="设备编码" prop="code">
          <el-input v-model="form.code" :disabled="!!form.id" placeholder="如 EQ-CNC-01" />
        </el-form-item>
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="form.name" placeholder="如 1# 数控车床" />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="form.model" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-input v-model="form.manufacturer" />
        </el-form-item>
        <el-form-item label="投用日期">
          <el-date-picker v-model="form.install_date" type="date" value-format="YYYY-MM-DD"
                          style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-tag :type="statusTag(form.status)" size="small">{{ statusLabel(form.status) }}</el-tag>
          <span class="sw-sub" style="margin-left: 8px">状态不在这里改</span>
        </el-form-item>
        <el-form-item label="在用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="不计 OEE">
          <el-switch v-model="form.oee_excluded" />
          <span class="sw-sub" style="margin-left: 8px">纯手工工位（如去毛刺台）勾上</span>
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
 * 设备台账（角色 D）。
 *
 * 这张表回答两个问题：
 *   ① 车间里到底有几台什么设备、在哪（工位 + AGV 装卸点）；
 *   ② 每台能干什么（11 种工序里的哪几种、什么精度、多少产能）。
 * 排产读的就是第 ② 项，所以能力做成抽屉而不是塞进表格 —— 一台设备 2~3 条能力，
 * 摊平在表格里会把行高撑成两屏。
 *
 * status 是只读的：它由监测流程和维修工单改（设备异常 → 修好 → 回 normal），
 * 台账页给个下拉直接改，就会出现"没修好但状态是正常"的假数据。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import request from '@/utils/request'
import { fetchEquipments, fetchStepTypes } from '@/api/equipment'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const allRows = ref([])          // 只用来算顶部指标，和表格分页的数据分开
const stepTypes = ref([])

const detailVisible = ref(false)
const current = ref(null)

const searchFields = ref([
  { prop: 'keyword', label: '编码/名称', type: 'input', placeholder: '如 EQ-CNC' },
  {
    prop: 'status', label: '状态', type: 'select',
    options: [
      { value: 'normal', label: '正常' },
      { value: 'wearing', label: '磨损' },
      { value: 'abnormal', label: '异常' }
    ]
  },
  { prop: 'step_type', label: '可执行工序', type: 'select', options: [] }
])

const columns = [
  { prop: 'code', label: '设备编码', width: 120, fixed: 'left' },
  { prop: 'name', label: '设备名称 / 型号', minWidth: 150, slot: 'name' },
  { prop: 'workshop', label: '车间/工位', width: 160, slot: 'workshop' },
  { prop: 'agv_load_point', label: 'AGV 装卸点', width: 110 },
  { prop: 'status', label: '状态', width: 90, slot: 'status' },
  { prop: 'capabilities', label: '可执行工序', minWidth: 210, slot: 'capabilities' },
  { prop: 'is_active', label: '在用', width: 130, slot: 'active' },
  { prop: 'actions', label: '操作', width: 120, slot: 'actions', fixed: 'right' }
]

const statusCount = computed(() => {
  const map = { normal: 0, wearing: 0, abnormal: 0 }
  allRows.value.forEach((row) => {
    if (row.status in map) map[row.status] += 1
  })
  return map
})
const activeCount = computed(() => allRows.value.filter((r) => r.is_active).length)

const editVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, code: '', name: '', model: '', manufacturer: '',
  install_date: '', status: 'normal', is_active: true, oee_excluded: false, remark: ''
})
const rules = {
  code: [{ required: true, message: '请填设备编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填设备名称', trigger: 'blur' }]
}

function statusTag(status) {
  return { normal: 'success', wearing: 'warning', abnormal: 'danger' }[status] || 'info'
}

function statusLabel(status) {
  return { normal: '正常', wearing: '磨损', abnormal: '异常' }[status] || status || '—'
}

async function load() {
  loading.value = true
  try {
    const data = await fetchEquipments({
      page: page.value, page_size: pageSize.value, ...query.value
    })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    // request 拦截器已弹过提示，这里只留日志，避免一次失败弹两条
    console.error('[EquipmentList] 加载失败', e)
  } finally {
    loading.value = false
  }
}

/** 顶部指标按全量算，不受当前筛选影响（筛选后指标跟着跳会让人以为总数变了） */
async function loadMetrics() {
  try {
    const data = await fetchEquipments({ page: 1, page_size: 200 })
    allRows.value = (data && data.results) || []
  } catch (e) {
    console.warn('[EquipmentList] 指标加载失败', e)
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

function showDetail(row) {
  current.value = row
  detailVisible.value = true
}

function openEdit(row) {
  Object.assign(form, row
    ? {
        id: row.id, code: row.code, name: row.name, model: row.model || '',
        manufacturer: row.manufacturer || '', install_date: row.install_date || '',
        status: row.status, is_active: row.is_active,
        oee_excluded: row.oee_excluded, remark: row.remark || ''
      }
    : {
        id: null, code: '', name: '', model: '', manufacturer: '',
        install_date: '', status: 'normal', is_active: true,
        oee_excluded: false, remark: ''
      })
  editVisible.value = true
}

async function onSave() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    // status 不进 body：后端 read_only，传了也会被忽略，干脆不传
    const payload = {
      code: form.code, name: form.name, model: form.model,
      manufacturer: form.manufacturer, install_date: form.install_date || null,
      is_active: form.is_active, oee_excluded: form.oee_excluded, remark: form.remark
    }
    if (form.id) {
      await request.patch(`/equipment/equipments/${form.id}/`, payload)
    } else {
      await request.post('/equipment/equipments/', payload)
    }
    ElMessage.success(form.id ? '已保存' : '已新增')
    editVisible.value = false
    await Promise.all([load(), loadMetrics()])
  } catch (e) {
    // request 拦截器已提示
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const dict = await fetchStepTypes()
    stepTypes.value = (dict && dict.step_types) || []
    const field = searchFields.value.find((f) => f.prop === 'step_type')
    if (field) field.options = stepTypes.value
  } catch (e) {
    console.warn('[EquipmentList] 工序字典加载失败', e)
  }
  await Promise.all([load(), loadMetrics()])
})
</script>
