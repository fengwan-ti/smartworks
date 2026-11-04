<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增报工</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #step_type="{ row }">
          <el-tag size="small" type="info">{{ row.step_type }}</el-tag>
        </template>
        <template #defect_qty="{ row }">
          <span :style="{ color: Number(row.defect_qty) > 0 ? 'var(--el-color-danger)' : '' }">
            {{ row.defect_qty }}
          </span>
        </template>
        <template #actions="{ row }">
          <el-button link type="danger" @click="onRevoke(row)">撤销</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" title="新增报工" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工单ID" prop="work_order_id">
          <el-input-number v-model="form.work_order_id" :min="1" style="width: 180px" />
        </el-form-item>
        <el-form-item label="工序序号" prop="operation_seq">
          <el-input-number v-model="form.operation_seq" :min="1" style="width: 180px" />
        </el-form-item>
        <el-form-item label="工序类型" prop="step_type">
          <el-select v-model="form.step_type" filterable style="width: 220px">
            <el-option v-for="v in stepTypes" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="成品批次号" prop="batch_no">
          <el-input v-model="form.batch_no" placeholder="如 PC-20261104-001" style="width: 220px" />
        </el-form-item>
        <el-form-item label="合格数" prop="good_qty">
          <el-input-number v-model="form.good_qty" :min="0" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="不良数">
          <el-input-number v-model="form.defect_qty" :min="0" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="开工时间">
          <el-date-picker v-model="form.start_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item label="完工时间">
          <el-date-picker v-model="form.end_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-alert type="info" :closable="false" title="完工时间是 B 计算换型 K2 的计时起点，请如实填写" />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/** 报工记录 —— pd_report_record，四人数据交汇点。契约 2.7 /production/reports/。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { createReport, listReports, revokeReport } from '@/api/production'

// 与 B 已定口径一致：11 种 step_type，走常量不硬编码在下拉里
const stepTypes = [
  'cutting', 'rough_turning', 'finish_turning', 'milling', 'slot_milling',
  'gear_milling', 'drilling', 'grinding', 'deburring', 'cleaning', 'inspection'
]

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '报工单号/批次号' },
  { prop: 'work_order_id', label: '工单ID', type: 'input' },
  { prop: 'step_type', label: '工序类型', type: 'select',
    options: stepTypes.map((v) => ({ value: v, label: v })) },
  { prop: 'created_at', label: '报工日期', type: 'daterange' }
])

const columns = [
  { prop: 'code', label: '报工单号', width: 150 },
  { prop: 'work_order_id', label: '工单', width: 80 },
  { prop: 'operation_seq', label: '工序', width: 70 },
  { prop: 'step_type', label: '工序类型', width: 130, slot: 'step_type' },
  { prop: 'batch_no', label: '批次号', width: 140 },
  { prop: 'good_qty', label: '合格数', width: 90 },
  { prop: 'defect_qty', label: '不良数', width: 90, slot: 'defect_qty' },
  { prop: 'work_hours', label: '工时(h)', width: 90 },
  { prop: 'end_time', label: '完工时间', width: 160 },
  { prop: 'operator_name', label: '报工人', width: 100 },
  { prop: 'actions', label: '操作', width: 80, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  work_order_id: null, operation_seq: 1, step_type: 'cutting',
  batch_no: '', good_qty: 0, defect_qty: 0, start_time: '', end_time: ''
})
const rules = {
  work_order_id: [{ required: true, message: '请输入工单ID', trigger: 'change' }],
  operation_seq: [{ required: true, message: '请输入工序序号', trigger: 'change' }],
  step_type: [{ required: true, message: '请选择工序类型', trigger: 'change' }],
  batch_no: [{ required: true, message: '请输入成品批次号', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listReports({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, {
    work_order_id: null, operation_seq: 1, step_type: 'cutting',
    batch_no: '', good_qty: 0, defect_qty: 0, start_time: '', end_time: ''
  })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  if (form.good_qty + form.defect_qty <= 0) {
    ElMessage.warning('合格数+不良数必须大于 0')
    return
  }
  saving.value = true
  try {
    await createReport({ ...form, batch_no: form.batch_no })
    ElMessage.success('报工成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onRevoke(row) {
  await ElMessageBox.confirm(`确定撤销报工「${row.code}」？将回滚追溯记录与在制品统计。`, '撤销确认', { type: 'warning' })
  await revokeReport(row.id)
  ElMessage.success('已撤销')
  load()
}

onMounted(load)
</script>
