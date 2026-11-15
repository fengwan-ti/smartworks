<template>
  <div class="page">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">工序模板库</div>
            <div class="card-sub">
              工艺配置三层结构的第一层：模板被工艺路线引用，路线可覆盖工时/参数。
              工序类型取值见 docs/role-b-w1/07-step_type取值字典.md（11 个值，已冻结）。
            </div>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="query.search"
          placeholder="搜索模板编码 / 名称"
          clearable
          style="width: 220px"
          @keyup.enter="reload"
        />
        <el-select v-model="query.step_type" placeholder="工序类型" clearable style="width: 170px">
          <el-option v-for="s in stepOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="query.is_active" placeholder="是否启用" clearable style="width: 130px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-button type="primary" @click="reload">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
        <span class="spacer" />
        <el-button type="primary" @click="openCreate">新增模板</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" border stripe size="default">
        <el-table-column prop="code" label="模板编码" width="100" />
        <el-table-column prop="name" label="模板名称" width="120" />
        <el-table-column label="工序类型" width="130">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ stepTypeLabel(row.step_type) }}</el-tag>
            <div class="cell-sub">{{ row.step_type }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="std_hours" label="标准工时(h)" width="110" align="right" />
        <el-table-column label="所需设备类型" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.is_equipment_free" size="small" type="warning">不占设备</el-tag>
            <span v-else>{{ equipmentLabel(row.required_equipment_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="关键参数" min-width="180">
          <template #default="{ row }">
            <span class="mono cell-ellipsis">{{ jsonBrief(row.key_params) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :current-page="query.page"
        :page-size="query.page_size"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑工序模板' : '新增工序模板'"
      width="640px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="130px">
        <el-form-item label="模板编码" prop="code">
          <el-input
            v-model="form.code"
            placeholder="留空自动生成 PT-###（如 PT-002）"
            :disabled="Boolean(editingId)"
          />
        </el-form-item>
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="form.name" placeholder="如：粗车" />
        </el-form-item>
        <el-form-item label="工序类型" prop="step_type">
          <el-select v-model="form.step_type" placeholder="请选择" style="width: 100%">
            <el-option v-for="s in STEP_TYPES" :key="s.value" :label="`${s.label}（${s.value}）`" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准工时(h)" prop="std_hours">
          <el-input-number v-model="form.std_hours" :min="0.001" :max="24" :step="0.05" :precision="3" style="width: 200px" />
          <span class="form-tip">单件工时，不含换型与准备</span>
        </el-form-item>
        <el-form-item label="不占设备">
          <el-switch v-model="form.is_equipment_free" />
          <span class="form-tip">下料/检验等前置或质检工序：排产只占工时，不匹配设备</span>
        </el-form-item>
        <el-form-item label="所需设备类型" prop="required_equipment_type">
          <el-select v-model="form.required_equipment_type" placeholder="请选择" style="width: 100%" :disabled="form.is_equipment_free">
            <el-option
              v-for="e in equipmentOptions"
              :key="e.value"
              :label="`${e.label}（${e.value}）`"
              :value="e.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键参数(JSON)" prop="key_params_text">
          <el-input v-model="form.key_params_text" type="textarea" :rows="4" class="mono" placeholder='{"spindle_rpm": 800, "feed_mm_per_rev": 0.2}' />
        </el-form-item>
        <el-form-item label="检验要求(JSON)" prop="inspection_rule_text">
          <el-input v-model="form.inspection_rule_text" type="textarea" :rows="3" class="mono" placeholder='{"first_piece": true, "aql": 1.0}' />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createTemplate,
  deleteTemplate,
  fetchProcessEnums,
  fetchTemplates,
  patchTemplate,
  updateTemplate,
} from '@/api/process'

// TODO(W2)：A 把 step_type 写进 core_data_dict 后，改走字典接口（I-02），这里只做兜底
const DEFAULT_STEP_TYPES = [
  { value: 'cutting', label: '下料' },
  { value: 'rough_turning', label: '粗车' },
  { value: 'finish_turning', label: '精车' },
  { value: 'milling', label: '铣削（铣面）' },
  { value: 'slot_milling', label: '铣槽' },
  { value: 'gear_milling', label: '铣齿' },
  { value: 'drilling', label: '钻孔' },
  { value: 'grinding', label: '磨削' },
  { value: 'deburring', label: '去毛刺' },
  { value: 'cleaning', label: '清洗' },
  { value: 'inspection', label: '检验' },
]
const DEFAULT_EQUIPMENT_TYPES = [
  { value: 'lathe', label: '数控车床' },
  { value: 'machining_center', label: '加工中心' },
  { value: 'drill', label: '钻床' },
  { value: 'grinder', label: '磨床' },
  { value: 'washer', label: '清洗机' },
  { value: 'deburr_station', label: '去毛刺台' },
  { value: 'inspection_station', label: '检验工位' },
]

const stepOptions = ref([...DEFAULT_STEP_TYPES])
const equipmentOptions = ref([...DEFAULT_EQUIPMENT_TYPES])

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, search: '', step_type: '', is_active: '' })

const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref()
const emptyForm = () => ({
  code: '',
  name: '',
  step_type: '',
  std_hours: 0.5,
  required_equipment_type: '',
  key_params_text: '{}',
  inspection_rule_text: '{}',
  is_active: true,
  is_equipment_free: false,
  remark: '',
})
const form = reactive(emptyForm())

const rules = {
  name: [{ required: true, message: '请填写模板名称', trigger: 'blur' }],
  step_type: [{ required: true, message: '请选择工序类型', trigger: 'change' }],
  std_hours: [{ required: true, message: '请填写标准工时', trigger: 'change' }],
  key_params_text: [{ validator: jsonValidator, trigger: 'blur' }],
  inspection_rule_text: [{ validator: jsonValidator, trigger: 'blur' }],
}

function jsonValidator(rule, value, callback) {
  try {
    const parsed = value ? JSON.parse(value) : {}
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      callback(new Error('必须是 JSON 对象，如 {"spindle_rpm": 800}'))
      return
    }
    callback()
  } catch (e) {
    callback(new Error('JSON 格式错误：' + e.message))
  }
}

function stepTypeLabel(value) {
  return stepOptions.value.find((s) => s.value === value)?.label || value || '—'
}

function equipmentLabel(value) {
  return equipmentOptions.value.find((e) => e.value === value)?.label || value || '—'
}

function jsonBrief(value) {
  if (!value || !Object.keys(value).length) return '—'
  const text = JSON.stringify(value)
  return text.length > 60 ? text.slice(0, 60) + '…' : text
}

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size, ordering: 'code' }
    if (query.search) params.search = query.search
    if (query.step_type) params.step_type = query.step_type
    if (query.is_active !== '') params.is_active = query.is_active
    const data = await fetchTemplates(params)
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

function reload() {
  query.page = 1
  load()
}

function resetQuery() {
  query.search = ''
  query.step_type = ''
  query.is_active = ''
  reload()
}

function onPageChange(page) {
  query.page = page
  load()
}

function onSizeChange(size) {
  query.page_size = size
  query.page = 1
  load()
}

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    code: row.code,
    name: row.name,
    step_type: row.step_type,
    std_hours: Number(row.std_hours),
    required_equipment_type: row.required_equipment_type,
    key_params_text: JSON.stringify(row.key_params || {}, null, 2),
    inspection_rule_text: JSON.stringify(row.inspection_rule || {}, null, 2),
    is_active: row.is_active,
    is_equipment_free: Boolean(row.is_equipment_free),
    remark: row.remark || '',
  })
  dialogVisible.value = true
}

function buildPayload() {
  return {
    code: form.code || undefined,
    name: form.name,
    step_type: form.step_type,
    std_hours: String(form.std_hours),
    required_equipment_type: form.is_equipment_free ? '' : form.required_equipment_type,
    is_equipment_free: form.is_equipment_free,
    key_params: JSON.parse(form.key_params_text || '{}'),
    inspection_rule: JSON.parse(form.inspection_rule_text || '{}'),
    is_active: form.is_active,
    remark: form.remark,
  }
}

async function submit() {
  await formRef.value.validate()
  if (!form.is_equipment_free && !form.required_equipment_type) {
    ElMessage.error('请选择所需设备类型，或打开“不占设备”')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateTemplate(editingId.value, buildPayload())
      ElMessage.success('已保存')
    } else {
      await createTemplate(buildPayload())
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  await patchTemplate(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确认删除工序模板「${row.code} ${row.name}」？被路线引用时后端会拒绝（12008）。`,
    '删除确认',
    { type: 'warning' },
  )
  await deleteTemplate(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  try {
    const enums = await fetchProcessEnums()
    if (enums?.step_types?.length) stepOptions.value = enums.step_types
    if (enums?.equipment_types?.length) equipmentOptions.value = enums.equipment_types
  } catch (e) {
    // 字典接口不可用时退回本地常量，保证页面仍可用
  }
  load()
})
</script>

<style scoped>
.page {
  padding: 16px;
}
.page-card {
  border-radius: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--sw-primary);
}
.card-sub {
  margin-top: 2px;
  font-size: 12px;
  color: #8a8f99;
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}
.spacer {
  flex: 1;
}
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
.cell-sub {
  font-size: 11px;
  color: #a0a4ad;
}
.cell-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono :deep(textarea),
.mono {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}
.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #8a8f99;
}
</style>
