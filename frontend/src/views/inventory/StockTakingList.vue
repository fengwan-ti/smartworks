<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新建盘点</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <StatusTag :value="row.status" :map="statusMap" />
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openDetail(row)">录入/查看</el-button>
          <el-button v-if="row.status === 'draft'" link type="success" @click="onConfirm(row)">确认盘点</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" title="新建盘点单" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="仓库" prop="warehouse">
          <el-select v-model="form.warehouse" filterable style="width: 100%">
            <el-option v-for="o in warehouseList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="留空自动生成单号" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">创建</el-button>
      </template>
    </el-dialog>

    <!-- 明细抽屉：录入实盘数 -->
    <el-drawer v-model="detailVisible" :title="`盘点明细 - ${detailRow?.code || ''}`" size="640px">
      <div class="detail-toolbar">
        <el-select v-model="pickMaterial" filterable placeholder="选择物料添加" style="width: 220px">
          <el-option v-for="o in materialList" :key="o.id" :label="o.name" :value="o.id" />
        </el-select>
        <el-button type="primary" :disabled="!pickMaterial" @click="onAddItem">添加</el-button>
      </div>
      <el-table :data="detailItems" border size="small">
        <el-table-column prop="material_name" label="物料" min-width="120" />
        <el-table-column prop="batch_no" label="批次" width="110" />
        <el-table-column prop="system_qty" label="系统数" width="90" />
        <el-table-column label="实盘数" width="130">
          <template #default="{ row }">
            <el-input-number
              v-if="detailRow?.status === 'draft'"
              v-model="row.actual_qty" :min="0" :precision="3" size="small"
              @change="onQtyChange(row)"
            />
            <span v-else>{{ row.actual_qty }}</span>
          </template>
        </el-table-column>
        <el-table-column label="差异" width="90">
          <template #default="{ row }">
            <span :style="{ color: Number(row.diff_qty) < 0 ? 'var(--el-color-danger)' : 'var(--el-color-success)' }">
              {{ row.diff_qty }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
/** 盘点管理 —— {id}/items/ 录实盘数（diff 后端算），{id}/confirm/ 写 adjust 流水。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  confirmStockTaking, createTakingItem, createStockTaking,
  listStockTakings, listTakingItems, warehouseOptions
} from '@/api/inventory'
import { materialOptions } from '@/api/masterdata'

const statusMap = {
  draft: { label: '盘点中', type: 'warning' },
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
const materialList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '盘点单号' },
  { prop: 'warehouse', label: '仓库', type: 'select', options: [] }
])

const columns = [
  { prop: 'code', label: '盘点单号', width: 150 },
  { prop: 'warehouse_name', label: '仓库', width: 130 },
  { prop: 'status', label: '状态', width: 90, slot: 'status' },
  { prop: 'operator_name', label: '盘点人', width: 100 },
  { prop: 'confirmed_at', label: '确认时间', width: 160 },
  { prop: 'remark', label: '备注' },
  { prop: 'actions', label: '操作', width: 180, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ warehouse: null, name: '', remark: '' })
const rules = {
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }]
}

const detailVisible = ref(false)
const detailRow = ref(null)
const detailItems = ref([])
const pickMaterial = ref(null)

async function load() {
  loading.value = true
  try {
    const data = await listStockTakings({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { warehouse: null, name: '', remark: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    await createStockTaking({ warehouse: form.warehouse, name: form.name, remark: form.remark })
    ElMessage.success('盘点单已创建')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function openDetail(row) {
  detailRow.value = row
  detailVisible.value = true
  const data = await listTakingItems(row.id)
  detailItems.value = data.results || data || []
}

async function onAddItem() {
  if (!detailRow.value) return
  await createTakingItem(detailRow.value.id, { material: pickMaterial.value, actual_qty: 0 })
  pickMaterial.value = null
  await openDetail(detailRow.value)
}

function onQtyChange() {
  // diff_qty 后端在确认时统一算，这里仅展示
}

async function onConfirm(row) {
  await ElMessageBox.confirm(
    `确认盘点单「${row.code}」？将按差异数量生成 adjust 库存流水。`,
    '确认盘点', { type: 'warning' }
  )
  await confirmStockTaking(row.id)
  ElMessage.success('盘点已确认')
  load()
}

onMounted(async () => {
  load()
  const [ws, ms] = await Promise.all([warehouseOptions(), materialOptions()])
  warehouseList.value = ws
  materialList.value = ms
  searchFields.value[1].options = ws.map((o) => ({ value: o.id, label: o.name }))
})
</script>

<style scoped>
.detail-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
