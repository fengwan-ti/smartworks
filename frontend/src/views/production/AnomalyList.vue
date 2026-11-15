<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">上报异常</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <StatusTag :value="row.status" :map="statusMap" />
        </template>
        <template #level="{ row }">
          <el-tag size="small" :type="levelMap[row.level]?.type || 'info'">
            {{ levelMap[row.level]?.label || row.level }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button v-if="row.status !== 'closed'" link type="success" @click="onClose(row)">关闭</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" title="上报异常" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工单ID" prop="work_order_id">
          <el-input-number v-model="form.work_order_id" :min="1" style="width: 180px" />
        </el-form-item>
        <el-form-item label="工序序号">
          <el-input-number v-model="form.operation_seq" :min="1" style="width: 180px" />
        </el-form-item>
        <el-form-item label="级别" prop="level">
          <el-select v-model="form.level" style="width: 180px">
            <el-option v-for="(v, k) in levelMap" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="发生了什么、影响范围" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/** 异常上报 —— /production/anomalies/ + {id}/close/。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import { closeAnomaly, createAnomaly, listAnomalies } from '@/api/production'

const statusMap = {
  open: { label: '待处理', type: 'danger' },
  closed: { label: '已关闭', type: 'info' }
}
const levelMap = {
  low: { label: '一般', type: 'info' },
  middle: { label: '较重', type: 'warning' },
  high: { label: '严重', type: 'danger' }
}

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '异常描述' },
  { prop: 'status', label: '状态', type: 'select',
    options: [{ value: 'open', label: '待处理' }, { value: 'closed', label: '已关闭' }] }
])

const columns = [
  { prop: 'code', label: '异常编号', width: 150 },
  { prop: 'work_order_id', label: '工单', width: 80 },
  { prop: 'operation_seq', label: '工序', width: 70 },
  { prop: 'level', label: '级别', width: 80, slot: 'level' },
  { prop: 'description', label: '描述' },
  { prop: 'status', label: '状态', width: 90, slot: 'status' },
  { prop: 'created_at', label: '上报时间', width: 160 },
  { prop: 'actions', label: '操作', width: 80, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ work_order_id: null, operation_seq: 1, level: 'middle', description: '' })
const rules = {
  work_order_id: [{ required: true, message: '请输入工单ID', trigger: 'change' }],
  description: [{ required: true, message: '请输入异常描述', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listAnomalies({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { work_order_id: null, operation_seq: 1, level: 'middle', description: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    await createAnomaly({ ...form })
    ElMessage.success('已上报')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onClose(row) {
  await ElMessageBox.confirm(`确定关闭异常「${row.code}」？`, '关闭确认', { type: 'warning' })
  await closeAnomaly(row.id, { remark: '' })
  ElMessage.success('已关闭')
  load()
}

onMounted(load)
</script>
