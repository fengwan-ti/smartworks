<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增领料单</el-button>
        <el-button @click="orderDialog = true">按工单生成</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <StatusTag :value="row.status" :map="statusMap" />
        </template>
        <template #work_order_id="{ row }">
          <span>{{ row.work_order_id || '—' }}</span>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openDetail(row)">明细</el-button>
          <el-button v-if="row.status === 'draft'" link type="success" @click="onConfirm(row)">确认出库</el-button>
        </template>
      </BaseTable>
    </div>

    <!-- 手工创建 -->
    <el-dialog v-model="dialogVisible" title="新增领料单" width="680px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="仓库" prop="warehouse">
          <el-select v-model="form.warehouse" filterable style="width: 100%">
            <el-option v-for="o in warehouseList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单ID">
          <el-input-number v-model="form.work_order_id" :min="1" placeholder="B 的工单 id" style="width: 160px" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
        <el-form-item label="领料明细" required>
          <div class="item-rows">
            <div v-for="(item, i) in form.items" :key="i" class="item-row">
              <el-select v-model="item.material" filterable placeholder="物料" style="width: 180px">
                <el-option v-for="o in materialList" :key="o.id" :label="o.name" :value="o.id" />
              </el-select>
              <el-input-number v-model="item.qty" :min="0.001" :precision="3" placeholder="数量" style="width: 140px" />
              <span class="tip">批次留空 = 确认时按 FIFO 自动分配</span>
              <el-button link type="danger" @click="form.items.splice(i, 1)">删</el-button>
            </div>
            <el-button size="small" @click="form.items.push({ material: null, qty: undefined })">+ 加一行</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- 按工单生成（契约 77） -->
    <el-dialog v-model="orderDialog" title="按工单生成领料单" width="460px">
      <el-form label-width="90px">
        <el-form-item label="工单ID" required>
          <el-input-number v-model="orderWorkOrderId" :min="1" style="width: 200px" />
        </el-form-item>
        <el-alert type="info" :closable="false"
          title="B 的 BOM 展开接口未就绪前，此操作可能返回 12000 段错误" />
      </el-form>
      <template #footer>
        <el-button @click="orderDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onFromWorkOrder">生成</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="`领料明细 - ${detailRow?.code || ''}`" size="560px">
      <el-table :data="detailItems" border size="small">
        <el-table-column prop="material_name" label="物料" />
        <el-table-column prop="batch_no" label="批次号" width="130" />
        <el-table-column prop="qty" label="数量" width="100" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
/** 领料出库 —— 契约 77（from-work-order）+ {id}/confirm/（FIFO 扣减）。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  confirmOutbound, createOutbound, listOutbounds,
  outboundFromWorkOrder, warehouseOptions
} from '@/api/inventory'
import { materialOptions } from '@/api/masterdata'

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
const materialList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '领料单号' },
  { prop: 'warehouse', label: '仓库', type: 'select', options: [] },
  { prop: 'status', label: '状态', type: 'select', options: [
    { value: 'draft', label: '草稿' }, { value: 'confirmed', label: '已确认' }
  ] }
])

const columns = [
  { prop: 'code', label: '领料单号', width: 150 },
  { prop: 'warehouse_name', label: '仓库', width: 120 },
  { prop: 'work_order_id', label: '工单', width: 90, slot: 'work_order_id' },
  { prop: 'status', label: '状态', width: 90, slot: 'status' },
  { prop: 'confirmed_at', label: '确认时间', width: 160 },
  { prop: 'remark', label: '备注' },
  { prop: 'actions', label: '操作', width: 160, slot: 'actions' }
]

const dialogVisible = ref(false)
const orderDialog = ref(false)
const orderWorkOrderId = ref(null)
const formRef = ref()
const form = reactive({ warehouse: null, work_order_id: null, remark: '', items: [{ material: null, qty: undefined }] })
const rules = {
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }]
}

const detailVisible = ref(false)
const detailRow = ref(null)
const detailItems = ref([])

async function load() {
  loading.value = true
  try {
    const data = await listOutbounds({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { warehouse: null, work_order_id: null, remark: '', items: [{ material: null, qty: undefined }] })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  const validItems = form.items.filter((it) => it.material && it.qty > 0)
  if (!validItems.length) {
    ElMessage.warning('至少填写一行完整明细（物料+数量）')
    return
  }
  saving.value = true
  try {
    await createOutbound({
      warehouse: form.warehouse,
      work_order_id: form.work_order_id || null,
      remark: form.remark,
      items: validItems
    })
    ElMessage.success('领料单已创建（草稿）')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onFromWorkOrder() {
  if (!orderWorkOrderId.value) {
    ElMessage.warning('请输入工单ID')
    return
  }
  saving.value = true
  try {
    await outboundFromWorkOrder({ work_order_id: orderWorkOrderId.value })
    ElMessage.success('已按工单生成领料单')
    orderDialog.value = false
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
    `确认领料单「${row.code}」？未指定批次的明细将按 FIFO 自动分配并扣减库存。`,
    '确认出库', { type: 'warning' }
  )
  await confirmOutbound(row.id)
  ElMessage.success('已确认出库')
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
.item-rows {
  width: 100%;
}
.item-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
