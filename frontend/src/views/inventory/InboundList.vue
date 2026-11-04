<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增入库单</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <StatusTag :value="row.status" :map="statusMap" />
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openDetail(row)">明细</el-button>
          <el-button v-if="row.status === 'draft'" link type="success" @click="onConfirm(row)">确认入库</el-button>
        </template>
      </BaseTable>
    </div>

    <!-- 新增：单头 + 动态明细行 -->
    <el-dialog v-model="dialogVisible" title="新增入库单" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="仓库" prop="warehouse">
          <el-select v-model="form.warehouse" filterable style="width: 100%">
            <el-option v-for="o in warehouseList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="form.supplier" filterable clearable style="width: 100%">
            <el-option v-for="o in supplierList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库日期">
          <el-date-picker v-model="form.in_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
        <el-form-item label="入库明细" required>
          <div class="item-rows">
            <div v-for="(item, i) in form.items" :key="i" class="item-row">
              <el-select v-model="item.material" filterable placeholder="物料" style="width: 180px">
                <el-option v-for="o in materialList" :key="o.id" :label="o.name" :value="o.id" />
              </el-select>
              <el-input v-model="item.batch_no" placeholder="批次号" style="width: 130px" />
              <el-input-number v-model="item.qty" :min="0.001" :precision="3" placeholder="数量" style="width: 140px" />
              <el-date-picker v-model="item.expire_date" type="date" value-format="YYYY-MM-DD" placeholder="有效期" style="width: 140px" />
              <el-button link type="danger" @click="form.items.splice(i, 1)">删</el-button>
            </div>
            <el-button size="small" @click="addItemRow">+ 加一行</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" :title="`入库明细 - ${detailRow?.code || ''}`" size="560px">
      <el-table :data="detailItems" border size="small">
        <el-table-column prop="material_name" label="物料" />
        <el-table-column prop="batch_no" label="批次号" width="130" />
        <el-table-column prop="qty" label="数量" width="100" />
        <el-table-column prop="expire_date" label="有效期至" width="110" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
/** 入库单 —— 契约 2.6：POST /inventory/inbounds/（code 自动生成），{id}/confirm/。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import { confirmInbound, createInbound, listInbounds, warehouseOptions } from '@/api/inventory'
import { materialOptions, supplierOptions } from '@/api/masterdata'

const statusMap = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '已确认', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' }
}

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const warehouseList = ref([])
const supplierList = ref([])
const materialList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '入库单号' },
  { prop: 'warehouse', label: '仓库', type: 'select', options: [] },
  { prop: 'in_date', label: '入库日期', type: 'date' }
])

const columns = [
  { prop: 'code', label: '入库单号', width: 150 },
  { prop: 'warehouse_name', label: '仓库', width: 120 },
  { prop: 'supplier_name', label: '供应商' },
  { prop: 'status', label: '状态', width: 90, slot: 'status' },
  { prop: 'in_date', label: '入库日期', width: 110 },
  { prop: 'confirmed_at', label: '确认时间', width: 160 },
  { prop: 'remark', label: '备注' },
  { prop: 'actions', label: '操作', width: 160, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  warehouse: null, supplier: null, in_date: '', remark: '',
  items: [newItemRow()]
})
const rules = {
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }]
}

const detailVisible = ref(false)
const detailRow = ref(null)
const detailItems = ref([])

function newItemRow() {
  return { material: null, batch_no: '', qty: undefined, expire_date: '' }
}
function addItemRow() {
  form.items.push(newItemRow())
}

async function load() {
  loading.value = true
  try {
    const data = await listInbounds({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { warehouse: null, supplier: null, in_date: '', remark: '', items: [newItemRow()] })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  const validItems = form.items.filter((it) => it.material && it.batch_no && it.qty > 0)
  if (!validItems.length) {
    ElMessage.warning('至少填写一行完整明细（物料+批次号+数量）')
    return
  }
  saving.value = true
  try {
    await createInbound({
      warehouse: form.warehouse,
      supplier: form.supplier || null,
      in_date: form.in_date || null,
      remark: form.remark,
      items: validItems
    })
    ElMessage.success('入库单已创建（草稿）')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openDetail(row) {
  detailRow.value = row
  detailItems.value = row.items || []
  detailVisible.value = true
}

async function onConfirm(row) {
  await ElMessageBox.confirm(
    `确认入库单「${row.code}」？确认后按明细生成批次并写库存流水，不可撤销。`,
    '确认入库', { type: 'warning' }
  )
  await confirmInbound(row.id)
  ElMessage.success('已确认入库')
  load()
}

onMounted(async () => {
  load()
  const [ws, ss, ms] = await Promise.all([warehouseOptions(), supplierOptions(), materialOptions()])
  warehouseList.value = ws
  supplierList.value = ss
  materialList.value = ms
  searchFields.value[1].options = ws.map((o) => ({ value: o.id, label: o.name }))
})
</script>

<style scoped>
.item-rows {
  width: 100%;
}
.item-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
</style>
