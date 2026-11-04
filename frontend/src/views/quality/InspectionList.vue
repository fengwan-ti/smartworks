<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新建质检单</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <!-- 判定结论唯一读 status：pending/inspecting/passed/failed/concession -->
          <StatusTag :value="row.status" :map="statusMap" />
        </template>
        <template #actions="{ row }">
          <el-button v-if="row.status === 'pending'" link type="primary" @click="onStart(row)">开始检验</el-button>
          <el-button v-if="row.status === 'inspecting'" link type="success" @click="openSubmit(row)">提交判定</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" title="新建质检单" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="检验对象" prop="target_type">
          <el-select v-model="form.target_type" style="width: 200px">
            <el-option label="来料检验" value="incoming" />
            <el-option label="过程检验" value="process" />
            <el-option label="成品检验" value="final" />
          </el-select>
        </el-form-item>
        <el-form-item label="物料/产品" prop="target_id">
          <el-select v-model="form.target_id" filterable style="width: 100%">
            <el-option v-for="o in materialList" :key="`m${o.id}`" :label="'[物料] ' + o.name" :value="`m${o.id}`" />
            <el-option v-for="o in productList" :key="`p${o.id}`" :label="'[产品] ' + o.name" :value="`p${o.id}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次号" prop="batch_no">
          <el-input v-model="form.batch_no" style="width: 220px" />
        </el-form-item>
        <el-form-item label="数量" prop="qty">
          <el-input-number v-model="form.qty" :min="0.001" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="检验标准">
          <el-select v-model="form.standard" filterable clearable style="width: 100%">
            <el-option v-for="o in standardList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="submitDialog" title="提交判定" width="480px">
      <el-alert type="warning" :closable="false" style="margin-bottom: 12px"
        title="判定结论由后端状态机按合格/不良数量给出，前端不手选结论" />
      <el-form label-width="110px">
        <el-form-item label="合格数量" required>
          <el-input-number v-model="submitForm.qualified_qty" :min="0" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="不良数量" required>
          <el-input-number v-model="submitForm.defect_qty" :min="0" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="让步理由">
          <el-input v-model="submitForm.concession_reason" type="textarea" :rows="2"
            placeholder="仅当走让步接收时填写" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="submitDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSubmit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/** 质检单 —— 状态机 pending→inspecting→passed/failed/concession，判定走 {id}/submit/。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  createInspection, listInspections, listStandards,
  startInspection, submitInspection
} from '@/api/quality'
import { materialOptions, productOptions } from '@/api/masterdata'

const statusMap = {
  pending: { label: '待检', type: 'info' },
  inspecting: { label: '检验中', type: 'warning' },
  passed: { label: '合格', type: 'success' },
  failed: { label: '不合格', type: 'danger' },
  concession: { label: '让步接收', type: 'warning' }
}

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const materialList = ref([])
const productList = ref([])
const standardList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '质检单号/批次号' },
  { prop: 'status', label: '状态', type: 'select',
    options: Object.entries(statusMap).map(([value, v]) => ({ value, label: v.label })) },
  { prop: 'created_at', label: '创建日期', type: 'daterange' }
])

const columns = [
  { prop: 'code', label: '质检单号', width: 150 },
  { prop: 'target_type_display', label: '检验类型', width: 100 },
  { prop: 'batch_no', label: '批次号', width: 140 },
  { prop: 'qty', label: '数量', width: 90 },
  { prop: 'qualified_qty', label: '合格', width: 80 },
  { prop: 'defect_qty', label: '不良', width: 80 },
  { prop: 'status', label: '判定结论', width: 100, slot: 'status' },
  { prop: 'inspector_name', label: '检验员', width: 90 },
  { prop: 'actions', label: '操作', width: 160, slot: 'actions' }
]

const dialogVisible = ref(false)
const submitDialog = ref(false)
const currentRow = ref(null)
const formRef = ref()
const form = reactive({
  target_type: 'incoming', target_id: null, batch_no: '', qty: undefined, standard: null
})
const submitForm = reactive({ qualified_qty: 0, defect_qty: 0, concession_reason: '' })
const rules = {
  target_type: [{ required: true, message: '请选择检验类型', trigger: 'change' }],
  target_id: [{ required: true, message: '请选择物料/产品', trigger: 'change' }],
  batch_no: [{ required: true, message: '请输入批次号', trigger: 'blur' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listInspections({ page: page.value, page_size: pageSize.value, ...query.value })
    rows.value = data.results || []
    total.value = data.count || 0
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
}
function onPageChange({ page: p, pageSize: s }) {
  page.value = p
  pageSize.value = s
  load()
}

function openCreate() {
  Object.assign(form, { target_type: 'incoming', target_id: null, batch_no: '', qty: undefined, standard: null })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const prefix = form.target_id.startsWith('p') ? 'product' : 'material'
    const id = Number(form.target_id.slice(1))
    await createInspection({
      target_type: form.target_type,
      [prefix]: id,
      batch_no: form.batch_no,
      qty: form.qty,
      standard: form.standard || null
    })
    ElMessage.success('质检单已创建')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onStart(row) {
  await startInspection(row.id)
  ElMessage.success('已开始检验')
  load()
}

function openSubmit(row) {
  currentRow.value = row
  Object.assign(submitForm, { qualified_qty: 0, defect_qty: 0, concession_reason: '' })
  submitDialog.value = true
}

async function onSubmit() {
  if (submitForm.qualified_qty + submitForm.defect_qty <= 0) {
    ElMessage.warning('合格数+不良数必须大于 0')
    return
  }
  if (submitForm.qualified_qty + submitForm.defect_qty > Number(currentRow.value.qty)) {
    ElMessage.warning('合格+不良不能大于送检数量')
    return
  }
  saving.value = true
  try {
    await submitInspection(currentRow.value.id, { ...submitForm })
    ElMessage.success('判定已提交')
    submitDialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  load()
  const [ms, ps, ss] = await Promise.all([materialOptions(), productOptions(), listStandards({ page_size: 100 })])
  materialList.value = ms
  productList.value = ps
  standardList.value = ss.results || ss || []
})
</script>
