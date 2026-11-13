<template>
  <div class="route-page">
    <!-- 左：路线列表 -->
    <el-card shadow="never" class="side-card">
      <template #header>
        <div class="side-head">
          <span class="card-title">工艺路线</span>
          <el-button type="primary" size="small" @click="openCreateRoute">新建</el-button>
        </div>
      </template>

      <div class="side-filter">
        <el-input v-model="routeQuery.search" placeholder="编码 / 产品" clearable size="small" />
        <el-select v-model="routeQuery.status" placeholder="状态" clearable size="small" style="width: 110px">
          <el-option label="草稿" value="draft" />
          <el-option label="生效" value="active" />
          <el-option label="停用" value="obsolete" />
        </el-select>
      </div>

      <el-scrollbar height="calc(100vh - 260px)">
        <div
          v-for="r in routes"
          :key="r.id"
          class="route-item"
          :class="{ active: current && current.id === r.id }"
          @click="selectRoute(r)"
        >
          <div class="route-line1">
            <span class="route-name">{{ r.product_name }}</span>
            <el-tag size="small" :type="statusType(r.status)">{{ statusLabel(r.status) }}</el-tag>
          </div>
          <div class="route-line2">
            <span>{{ r.code }}</span>
            <span>V{{ r.version }} · {{ r.steps_count }} 道工序</span>
          </div>
        </div>
        <el-empty v-if="!routes.length" description="还没有工艺路线" :image-size="70" />
      </el-scrollbar>
    </el-card>

    <!-- 右：路线详情 -->
    <el-card shadow="never" class="main-card">
      <template v-if="current">
        <div class="detail-head">
          <div>
            <div class="detail-title">
              {{ current.product_name }}
              <el-tag size="small" :type="statusType(current.status)">{{ statusLabel(current.status) }}</el-tag>
            </div>
            <div class="detail-sub">
              {{ current.code }} · {{ current.product_code }} · V{{ current.version }}
              <span v-if="current.family_name"> · {{ current.family_name }}</span>
            </div>
          </div>
          <div class="detail-actions">
            <el-button v-if="current.status === 'draft'" type="success" @click="onActivate">生效</el-button>
            <el-button @click="openCopyRoute">复制同族路线</el-button>
            <el-button type="primary" @click="openCreateStep">添加工序</el-button>
          </div>
        </div>

        <el-alert
          v-if="current.status === 'active'"
          type="warning"
          :closable="false"
          show-icon
          title="该路线已生效：修改会直接影响排产结果，建议先复制新版本再改。"
          style="margin-bottom: 12px"
        />

        <el-table v-loading="loading" :data="current.steps || []" border stripe size="default">
          <el-table-column prop="seq" label="序号" width="80" align="center" />
          <el-table-column prop="template_code" label="模板" width="100" />
          <el-table-column prop="template_name" label="工序名称" width="110" />
          <el-table-column label="工序类型" width="140">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ stepLabel(row.step_type) }}</el-tag>
              <div class="cell-sub">{{ row.step_type }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="std_hours" label="工时(h)" width="90" align="right" />
          <el-table-column label="设备" width="150">
            <template #default="{ row }">
              <el-tag v-if="row.is_equipment_free" size="small" type="warning">不占设备</el-tag>
              <span v-else>{{ equipmentLabel(row.required_equipment_type) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="参数" min-width="150">
            <template #default="{ row }">
              <span class="mono">{{ jsonBrief(row.key_params) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row, $index }">
              <el-button link :disabled="$index === 0" @click="moveStep($index, -1)">上移</el-button>
              <el-button link :disabled="$index === (current.steps.length - 1)" @click="moveStep($index, 1)">下移</el-button>
              <el-button link type="primary" @click="openEditStep(row)">编辑</el-button>
              <el-button link type="danger" @click="removeStep(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="total-line">
          合计工时：<b>{{ totalHours }}</b> 小时/件（不含换型与准备）
        </div>
      </template>
      <el-empty v-else description="从左侧选一条工艺路线，或点“新建”" />
    </el-card>

    <!-- 新建路线 -->
    <el-dialog v-model="createVisible" title="新建工艺路线" width="460px">
      <el-form label-width="90px">
        <el-form-item label="产品" required>
          <el-select v-model="createProductId" placeholder="请选择产品" filterable style="width: 100%">
            <el-option v-for="p in productList" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="dialog-tip">系统自动生成编码 PR-&lt;产品编码&gt;-V&lt;版本&gt;，初始为草稿。</div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreateRoute">创建</el-button>
      </template>
    </el-dialog>

    <!-- 复制路线 -->
    <el-dialog v-model="copyVisible" title="复制路线到新产品" width="460px">
      <el-form label-width="90px">
        <el-form-item label="目标产品" required>
          <el-select v-model="copyProductId" placeholder="请选择产品" filterable style="width: 100%">
            <el-option v-for="p in productList" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="dialog-tip">复制后生成草稿版本，工序与参数原样带过去，可再微调。</div>
      <template #footer>
        <el-button @click="copyVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCopyRoute">复制</el-button>
      </template>
    </el-dialog>

    <!-- 工序表单 -->
    <el-dialog v-model="stepVisible" :title="stepForm.id ? '编辑工序' : '添加工序'" width="620px" destroy-on-close>
      <el-form ref="stepFormRef" :model="stepForm" :rules="stepRules" label-width="120px">
        <el-form-item label="工序模板" prop="template">
          <el-select v-model="stepForm.template" placeholder="从模板库选择" filterable style="width: 100%" @change="onTemplateChange">
            <el-option v-for="t in templates" :key="t.id" :label="`${t.code} ${t.name}（${t.std_hours}h）`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="序号" prop="seq">
          <el-input-number v-model="stepForm.seq" :min="1" :step="10" />
          <span class="form-tip">建议 10/20/30…，留插入余量</span>
        </el-form-item>
        <el-form-item label="工序类型" prop="step_type">
          <el-select v-model="stepForm.step_type" style="width: 100%">
            <el-option v-for="s in stepOptions" :key="s.value" :label="`${s.label}（${s.value}）`" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准工时(h)" prop="std_hours">
          <el-input-number v-model="stepForm.std_hours" :min="0.001" :max="24" :step="0.05" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="不占设备">
          <el-switch v-model="stepForm.is_equipment_free" />
          <span class="form-tip">下料/检验等：排产只占工时</span>
        </el-form-item>
        <el-form-item v-if="!stepForm.is_equipment_free" label="设备类型">
          <el-select v-model="stepForm.required_equipment_type" placeholder="请选择" style="width: 100%">
            <el-option v-for="e in equipmentOptions" :key="e.value" :label="e.label" :value="e.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="专用工序">
          <el-switch v-model="stepForm.is_special" />
          <span class="form-tip">模板库之外的一次性工序</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stepForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stepVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitStep">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { productOptions } from '@/api/masterdata'
import {
  activateRoute, copyRoute, createRoute, createRouteStep, deleteRouteStep,
  fetchProcessEnums, fetchRoute, fetchRoutes, fetchTemplates, patchRouteStep,
} from '@/api/process'

const loading = ref(false)
const saving = ref(false)
const routes = ref([])
const current = ref(null)
const templates = ref([])
const productList = ref([])
const stepOptions = ref([])
const equipmentOptions = ref([])

const routeQuery = reactive({ search: '', status: '' })

const createVisible = ref(false)
const createProductId = ref(null)
const copyVisible = ref(false)
const copyProductId = ref(null)

const stepVisible = ref(false)
const stepFormRef = ref()
const emptyStep = () => ({
  id: null, template: null, seq: 10, step_type: '', std_hours: 0.3,
  required_equipment_type: '', is_equipment_free: false, is_special: false, remark: '',
})
const stepForm = reactive(emptyStep())
const stepRules = {
  seq: [{ required: true, message: '请填写序号', trigger: 'change' }],
  step_type: [{ required: true, message: '请选择工序类型', trigger: 'change' }],
  std_hours: [{ required: true, message: '请填写工时', trigger: 'change' }],
}

const totalHours = computed(() => {
  const steps = current.value?.steps || []
  return steps.reduce((sum, s) => sum + Number(s.std_hours || 0), 0).toFixed(3)
})

function statusType(status) {
  return { draft: 'info', active: 'success', obsolete: 'danger' }[status] || 'info'
}
function statusLabel(status) {
  return { draft: '草稿', active: '生效', obsolete: '停用' }[status] || status
}
function stepLabel(value) {
  return stepOptions.value.find((s) => s.value === value)?.label || value
}
function equipmentLabel(value) {
  return equipmentOptions.value.find((e) => e.value === value)?.label || value || '—'
}
function jsonBrief(value) {
  if (!value || !Object.keys(value).length) return '—'
  const text = JSON.stringify(value)
  return text.length > 50 ? text.slice(0, 50) + '…' : text
}

async function loadRoutes() {
  const params = { page: 1, page_size: 50, ordering: 'code' }
  if (routeQuery.search) params.search = routeQuery.search
  if (routeQuery.status) params.status = routeQuery.status
  const data = await fetchRoutes(params)
  routes.value = data.results || []
  if (current.value) {
    const still = routes.value.find((r) => r.id === current.value.id)
    if (still) await selectRoute(still)
  }
}

async function selectRoute(row) {
  loading.value = true
  try {
    current.value = await fetchRoute(row.id)
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [tplData, products, enums] = await Promise.all([
    fetchTemplates({ page: 1, page_size: 200, ordering: 'code' }),
    productOptions(),
    fetchProcessEnums(),
  ])
  templates.value = tplData.results || []
  productList.value = products || []
  stepOptions.value = enums.step_types || []
  equipmentOptions.value = enums.equipment_types || []
}

function openCreateRoute() {
  createProductId.value = null
  createVisible.value = true
}
async function submitCreateRoute() {
  if (!createProductId.value) {
    ElMessage.warning('请选择产品')
    return
  }
  saving.value = true
  try {
    const route = await createRoute({ product: createProductId.value })
    ElMessage.success('已创建草稿路线')
    createVisible.value = false
    await loadRoutes()
    await selectRoute(route)
  } finally {
    saving.value = false
  }
}

function openCopyRoute() {
  copyProductId.value = null
  copyVisible.value = true
}
async function submitCopyRoute() {
  if (!copyProductId.value) {
    ElMessage.warning('请选择目标产品')
    return
  }
  saving.value = true
  try {
    const route = await copyRoute(current.value.id, copyProductId.value)
    ElMessage.success('已复制为草稿')
    copyVisible.value = false
    await loadRoutes()
    await selectRoute(route)
  } finally {
    saving.value = false
  }
}

async function onActivate() {
  await ElMessageBox.confirm('生效后该路线参与排产，且同一产品只能有一个生效版本。继续？', '生效确认', { type: 'warning' })
  await activateRoute(current.value.id)
  ElMessage.success('已生效')
  await loadRoutes()
  await selectRoute(current.value)
}

function nextSeq() {
  const steps = current.value?.steps || []
  return steps.length ? Math.max(...steps.map((s) => s.seq)) + 10 : 10
}

function openCreateStep() {
  Object.assign(stepForm, emptyStep(), { seq: nextSeq() })
  stepVisible.value = true
}
function openEditStep(row) {
  Object.assign(stepForm, {
    id: row.id,
    template: row.template,
    seq: row.seq,
    step_type: row.step_type,
    std_hours: Number(row.std_hours),
    required_equipment_type: row.required_equipment_type || '',
    is_equipment_free: row.is_equipment_free,
    is_special: row.is_special,
    remark: row.remark || '',
  })
  stepVisible.value = true
}

function onTemplateChange(templateId) {
  const tpl = templates.value.find((t) => t.id === templateId)
  if (!tpl) return
  stepForm.step_type = tpl.step_type
  stepForm.std_hours = Number(tpl.std_hours)
  stepForm.required_equipment_type = tpl.required_equipment_type || ''
  stepForm.is_equipment_free = Boolean(tpl.is_equipment_free)
}

async function submitStep() {
  await stepFormRef.value.validate()
  const payload = {
    seq: stepForm.seq,
    template: stepForm.template,
    step_type: stepForm.step_type,
    std_hours: String(stepForm.std_hours),
    required_equipment_type: stepForm.is_equipment_free ? '' : stepForm.required_equipment_type,
    is_equipment_free: stepForm.is_equipment_free,
    is_special: stepForm.is_special,
    remark: stepForm.remark,
  }
  saving.value = true
  try {
    if (stepForm.id) {
      await patchRouteStep(current.value.id, stepForm.id, payload)
      ElMessage.success('已保存')
    } else {
      await createRouteStep(current.value.id, payload)
      ElMessage.success('已添加')
    }
    stepVisible.value = false
    await selectRoute(current.value)
    await loadRoutes()
  } finally {
    saving.value = false
  }
}

async function removeStep(row) {
  await ElMessageBox.confirm(`确认删除第 ${row.seq} 道工序「${row.template_name || row.step_type}」？`, '删除确认', { type: 'warning' })
  await deleteRouteStep(current.value.id, row.id)
  ElMessage.success('已删除')
  await selectRoute(current.value)
  await loadRoutes()
}

async function moveStep(index, direction) {
  const steps = current.value.steps
  const a = steps[index]
  const b = steps[index + direction]
  if (!b) return
  const tempSeq = 9000 + Math.floor(Math.random() * 500)
  await patchRouteStep(current.value.id, a.id, { seq: tempSeq })
  await patchRouteStep(current.value.id, b.id, { seq: a.seq })
  await patchRouteStep(current.value.id, a.id, { seq: b.seq })
  await selectRoute(current.value)
}

onMounted(async () => {
  await loadOptions()
  await loadRoutes()
})
</script>

<style scoped>
.route-page {
  display: flex;
  gap: 14px;
  padding: 14px;
  height: calc(100vh - 56px);
  box-sizing: border-box;
}
.side-card {
  width: 330px;
  flex: none;
  display: flex;
  flex-direction: column;
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.side-filter {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.card-title {
  font-weight: 600;
  color: var(--sw-primary);
}
.route-item {
  padding: 10px;
  border: 1px solid #e6e8eb;
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.route-item:hover {
  border-color: var(--sw-primary);
}
.route-item.active {
  border-color: var(--sw-primary);
  background: #eef3ff;
}
.route-line1 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.route-name {
  font-weight: 600;
}
.route-line2 {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #8a8f99;
}
.main-card {
  flex: 1;
  overflow: auto;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--sw-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-sub {
  font-size: 12px;
  color: #8a8f99;
  margin-top: 4px;
}
.detail-actions {
  display: flex;
  gap: 8px;
}
.cell-sub {
  font-size: 11px;
  color: #a0a4ad;
}
.mono {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
}
.total-line {
  margin-top: 10px;
  text-align: right;
  font-size: 13px;
  color: #606266;
}
.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #8a8f99;
}
.dialog-tip {
  font-size: 12px;
  color: #8a8f99;
}
</style>
