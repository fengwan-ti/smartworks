<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">登记不良</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange" />
    </div>

    <el-dialog v-model="dialogVisible" title="登记不良" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="关联质检单" prop="inspection">
          <el-select v-model="form.inspection" filterable style="width: 100%">
            <el-option v-for="o in inspectionList" :key="o.id"
              :label="o.code + (o.batch_no ? ` / ${o.batch_no}` : '')" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="缺陷代码" prop="defect_code">
          <el-select v-model="form.defect_code" filterable style="width: 100%">
            <el-option v-for="o in codeList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="不良数量" prop="qty">
          <el-input-number v-model="form.qty" :min="0.001" :precision="3" style="width: 180px" />
        </el-form-item>
        <el-form-item label="处置方式">
          <el-select v-model="form.disposition" style="width: 200px">
            <el-option label="返工" value="rework" />
            <el-option label="报废" value="scrap" />
            <el-option label="让步接收" value="concession" />
            <el-option label="退供应商" value="return" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/** 不良记录 —— /quality/defects/，与缺陷代码字典联动（判定结论唯一读质检单 status）。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { createDefect, listDefectCodes, listDefects, listInspections } from '@/api/quality'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const inspectionList = ref([])
const codeList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '批次号/单号' },
  { prop: 'created_at', label: '登记日期', type: 'daterange' }
])

const columns = [
  { prop: 'code', label: '不良编号', width: 150 },
  { prop: 'inspection_code', label: '质检单', width: 150 },
  { prop: 'batch_no', label: '批次号', width: 140 },
  { prop: 'defect_code_name', label: '缺陷类型' },
  { prop: 'qty', label: '不良数量', width: 100 },
  { prop: 'disposition_display', label: '处置方式', width: 100 },
  { prop: 'created_at', label: '登记时间', width: 160 }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ inspection: null, defect_code: null, qty: undefined, disposition: 'rework', remark: '' })
const rules = {
  inspection: [{ required: true, message: '请选择质检单', trigger: 'change' }],
  defect_code: [{ required: true, message: '请选择缺陷代码', trigger: 'change' }],
  qty: [{ required: true, message: '请输入不良数量', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listDefects({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { inspection: null, defect_code: null, qty: undefined, disposition: 'rework', remark: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    await createDefect({ ...form })
    ElMessage.success('已登记')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  load()
  const [ins, codes] = await Promise.all([
    listInspections({ page_size: 100 }),
    listDefectCodes({ page_size: 100 })
  ])
  inspectionList.value = ins.results || ins || []
  codeList.value = codes.results || codes || []
})
</script>
