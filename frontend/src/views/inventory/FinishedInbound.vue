<template>
  <div class="sw-page">
    <!-- 指标：成品入库是"钱变成库存"的那一步，四个数足够看一眼 -->
    <div class="sw-metrics">
      <div class="sw-metric">
        <div class="sw-metric__label">入库单</div>
        <div class="sw-metric__value">{{ stats.total }}<span class="sw-metric__unit">张</span></div>
        <div class="sw-metric__foot">当前筛选条件下</div>
      </div>
      <div class="sw-metric" :class="{ 'sw-metric--warn': stats.draft > 0 }">
        <div class="sw-metric__label">待确认</div>
        <div class="sw-metric__value">{{ stats.draft }}<span class="sw-metric__unit">张</span></div>
        <div class="sw-metric__foot">草稿未写库存流水</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">已入库数量</div>
        <div class="sw-metric__value">{{ stats.confirmedQty }}<span class="sw-metric__unit">件</span></div>
        <div class="sw-metric__foot">只算已确认单</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">发货单</div>
        <div class="sw-metric__value">{{ stats.shipments }}<span class="sw-metric__unit">张</span></div>
        <div class="sw-metric__foot">见下方"发货出库"标签</div>
      </div>
    </div>

    <div class="sw-card">
      <el-tabs v-model="tab" @tab-change="onTabChange">
        <!-- ── 成品入库 ────────────────────────────────────────────── -->
        <el-tab-pane label="成品入库" name="inbound">
          <div class="sw-toolbar">
            <el-button type="primary" @click="openCreate">新增入库单</el-button>
            <el-button :loading="loading" @click="loadInbounds">刷新</el-button>
            <span class="sw-sub" style="margin-left: auto; align-self: center">
              单号 PI-YYYYMMDD-NNN 自动生成；确认后才写库存流水，草稿可删可改
            </span>
          </div>

          <BaseTable :columns="inboundColumns" :rows="inboundRows" :total="inboundTotal"
                     @change="onInboundPage">
            <template #status="{ row }">
              <StatusTag :value="row.status" :map="statusMap" />
            </template>
            <template #actions="{ row }">
              <el-button v-if="row.status === 'draft'" link type="success" @click="onConfirmInbound(row)">
                确认入库
              </el-button>
              <el-button v-if="row.status === 'draft'" link type="danger" @click="onCancelInbound(row)">
                作废
              </el-button>
              <span v-if="row.status !== 'draft'" class="sw-sub">已定稿</span>
            </template>
          </BaseTable>
        </el-tab-pane>

        <!-- ── 发货出库 ────────────────────────────────────────────── -->
        <el-tab-pane label="发货出库" name="shipment">
          <div class="sw-toolbar">
            <el-button type="primary" @click="openShipment">新增发货单</el-button>
            <el-button :loading="shipmentLoading" @click="loadShipments">刷新</el-button>
            <span class="sw-sub" style="margin-left: auto; align-self: center">
              确认发货按批次先进先出扣减；库存不足会指出是哪个批次不够
            </span>
          </div>

          <BaseTable :columns="shipmentColumns" :rows="shipmentRows" :total="shipmentTotal"
                     @change="onShipmentPage">
            <template #status="{ row }">
              <StatusTag :value="row.status" :map="statusMap" />
            </template>
            <template #actions="{ row }">
              <el-button v-if="row.status === 'draft'" link type="success" @click="onConfirmShipment(row)">
                确认发货
              </el-button>
              <el-button link type="primary" @click="openShipmentDetail(row)">明细</el-button>
            </template>
          </BaseTable>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 新增入库单 -->
    <el-dialog v-model="dialogVisible" title="新增成品入库单" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="产品" prop="product">
          <el-select v-model="form.product" filterable style="width: 100%" @change="onProductChange">
            <el-option v-for="o in productList" :key="o.id"
                       :label="`${o.code} ${o.name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次" prop="batch">
          <el-select v-model="form.batch" filterable style="width: 100%"
                     :placeholder="form.product ? '只列出该产品的批次' : '先选产品'">
            <el-option v-for="o in filteredBatches" :key="o.id"
                       :label="`${o.batch_no}（可用 ${o.qty}）`" :value="o.id" />
          </el-select>
          <div class="sw-sub" style="margin-top: 4px">
            批次的归属产品必须和上面选的产品一致，否则后端报 14104
          </div>
        </el-form-item>
        <el-form-item label="数量" prop="qty">
          <el-input-number v-model="form.qty" :min="0.001" :precision="3" :step="10" />
          <span class="sw-sub" style="margin-left: 8px">单位与产品一致（件/套）</span>
        </el-form-item>
        <el-form-item label="仓库" prop="warehouse">
          <el-select v-model="form.warehouse" filterable style="width: 100%">
            <el-option v-for="o in finishedWarehouses" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库日期">
          <el-date-picker v-model="form.inbound_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="工单号">
          <el-input v-model="form.work_order_code" placeholder="来自 B 的工单，可为空" />
        </el-form-item>
        <el-form-item label="检验单号">
          <el-input v-model="form.inspection_code" placeholder="来自 C 的检验单，可为空" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveInbound">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- 新增发货单 -->
    <el-dialog v-model="shipmentVisible" title="新增发货单" width="720px">
      <el-form ref="shipmentFormRef" :model="shipmentForm" :rules="shipmentRules" label-width="96px">
        <el-form-item label="客户" prop="customer">
          <el-select v-model="shipmentForm.customer" filterable style="width: 100%">
            <el-option v-for="o in customerList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库" prop="warehouse">
          <el-select v-model="shipmentForm.warehouse" filterable style="width: 100%">
            <el-option v-for="o in finishedWarehouses" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="发货日期">
          <el-date-picker v-model="shipmentForm.ship_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="订单号">
          <el-input v-model="shipmentForm.order_code" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="明细" required>
          <div class="item-rows">
            <div v-for="(item, i) in shipmentForm.items" :key="i" class="item-row">
              <el-select v-model="item.batch" filterable placeholder="批次" style="width: 240px">
                <el-option v-for="o in batchList" :key="o.id"
                           :label="`${o.batch_no}（${o.product_name || o.material_name || '-'}）`"
                           :value="o.id" />
              </el-select>
              <el-input-number v-model="item.qty" :min="0.001" :precision="3" placeholder="数量" style="width: 140px" />
              <el-button link type="danger" @click="shipmentForm.items.splice(i, 1)">删</el-button>
            </div>
            <el-button size="small" @click="shipmentForm.items.push({ batch: null, qty: undefined })">
              + 加一行
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipmentVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveShipment">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- 发货明细 -->
    <el-drawer v-model="shipmentDetailVisible" :title="`发货明细 - ${shipmentDetailRow?.code || ''}`" size="520px">
      <el-table :data="shipmentDetailItems" border size="small">
        <el-table-column prop="batch_no" label="批次" width="150" />
        <el-table-column prop="qty" label="数量" width="100" />
        <el-table-column prop="available_qty" label="该批当前可用" width="120" />
        <el-table-column prop="remark" label="备注" />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * 成品入库 / 发货出库（D 的成品仓）。
 *
 * 为什么要"草稿 → 确认"两步：确认才写库存流水。
 * 一步到位的话，填错一个批次数量就要写反冲流水，账更难对。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BaseTable from '@/components/BaseTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  cancelFinishedInbound, confirmFinishedInbound, confirmShipment,
  createFinishedInbound, createShipment, listBatches, listFinishedInbounds,
  listShipments, listWarehouses
} from '@/api/inventory'
import { customerOptions, productOptions } from '@/api/masterdata'

const statusMap = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '已确认', type: 'success' },
  cancelled: { label: '已作废', type: 'danger' }
}

const tab = ref('inbound')
const loading = ref(false)
const shipmentLoading = ref(false)
const saving = ref(false)

const inboundRows = ref([])
const inboundTotal = ref(0)
const inboundPage = ref(1)
const inboundPageSize = ref(10)

const shipmentRows = ref([])
const shipmentTotal = ref(0)
const shipmentPage = ref(1)
const shipmentPageSize = ref(10)

const productList = ref([])
const batchList = ref([])
const filteredBatches = computed(() =>
  form.product
    ? batchList.value.filter((b) => b.product === form.product)
    : batchList.value
)
const warehouseList = ref([])
const customerList = ref([])

// warehouseOptions() 只回 id/code/name，没有 type，没法筛"成品仓"，
// 所以这里用列表接口拿全字段。没有成品仓时退化成全部仓库，不让页面卡住。
const finishedWarehouses = computed(() => {
  const finished = warehouseList.value.filter((w) => w.type === 'finished')
  return finished.length ? finished : warehouseList.value
})

const stats = computed(() => {
  const rows = inboundRows.value
  return {
    total: inboundTotal.value,
    draft: rows.filter((r) => r.status === 'draft').length,
    confirmedQty: rows
      .filter((r) => r.status === 'confirmed')
      .reduce((sum, r) => sum + Number(r.qty || 0), 0)
      .toFixed(0),
    shipments: shipmentTotal.value
  }
})

const inboundColumns = [
  { prop: 'code', label: '入库单号', width: 160, fixed: 'left' },
  { prop: 'product_name', label: '产品', minWidth: 180 },
  { prop: 'batch_no', label: '批次', width: 130 },
  { prop: 'qty', label: '数量', width: 90 },
  { prop: 'warehouse_name', label: '仓库', width: 140 },
  { prop: 'work_order_code', label: '工单号', width: 140 },
  { prop: 'inbound_date', label: '入库日期', width: 116 },
  { prop: 'status', label: '状态', width: 92, slot: 'status' },
  { prop: 'actions', label: '操作', width: 160, slot: 'actions', fixed: 'right' }
]

const shipmentColumns = [
  { prop: 'code', label: '发货单号', width: 160, fixed: 'left' },
  { prop: 'customer_name', label: '客户', width: 150 },
  { prop: 'warehouse_name', label: '仓库', width: 150 },
  { prop: 'order_code', label: '订单号', width: 140 },
  { prop: 'ship_date', label: '发货日期', width: 116 },
  { prop: 'status', label: '状态', width: 92, slot: 'status' },
  { prop: 'actions', label: '操作', width: 160, slot: 'actions', fixed: 'right' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  product: null, batch: null, qty: undefined, warehouse: null,
  inbound_date: '', work_order_code: '', inspection_code: '', remark: ''
})
const rules = {
  product: [{ required: true, message: '请选择产品', trigger: 'change' }],
  batch: [{ required: true, message: '请选择批次', trigger: 'change' }],
  qty: [{ required: true, message: '请填写数量', trigger: 'blur' }],
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }]
}

const shipmentVisible = ref(false)
const shipmentFormRef = ref()
const shipmentForm = reactive({
  customer: null, warehouse: null, ship_date: '', order_code: '',
  items: [{ batch: null, qty: undefined }]
})
const shipmentRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }]
}

const shipmentDetailVisible = ref(false)
const shipmentDetailRow = ref(null)
const shipmentDetailItems = ref([])

async function loadInbounds() {
  loading.value = true
  try {
    const data = await listFinishedInbounds({
      page: inboundPage.value, page_size: inboundPageSize.value
    })
    inboundRows.value = data.results || []
    inboundTotal.value = data.count || 0
  } catch (e) {
    ElMessage.error('入库单加载失败：' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

async function loadShipments() {
  shipmentLoading.value = true
  try {
    const data = await listShipments({
      page: shipmentPage.value, page_size: shipmentPageSize.value
    })
    shipmentRows.value = data.results || []
    shipmentTotal.value = data.count || 0
  } catch (e) {
    ElMessage.error('发货单加载失败：' + (e?.message || e))
  } finally {
    shipmentLoading.value = false
  }
}

function onInboundPage({ page, pageSize }) {
  inboundPage.value = page
  inboundPageSize.value = pageSize
  loadInbounds()
}
function onShipmentPage({ page, pageSize }) {
  shipmentPage.value = page
  shipmentPageSize.value = pageSize
  loadShipments()
}
function onTabChange(name) {
  if (name === 'shipment') loadShipments()
}

async function loadOptions() {
  try {
    const [products, batches, warehouses, customers] = await Promise.all([
      productOptions(),
      listBatches({ page_size: 200 }),
      listWarehouses({ page_size: 100 }),
      customerOptions()
    ])
    productList.value = products || []
    batchList.value = (batches && batches.results) || batches || []
    warehouseList.value = (warehouses && warehouses.results) || warehouses || []
    customerList.value = customers || []
  } catch (e) {
    ElMessage.error('下拉数据加载失败：' + (e?.message || e))
  }
}

function onProductChange() {
  form.batch = null
}

async function openCreate() {
  Object.assign(form, {
    product: null, batch: null, qty: undefined,
    warehouse: finishedWarehouses.value[0]?.id || null,
    inbound_date: new Date().toISOString().slice(0, 10),
    work_order_code: '', inspection_code: '', remark: ''
  })
  dialogVisible.value = true
}

async function onSaveInbound() {
  await formRef.value.validate()
  saving.value = true
  try {
    await createFinishedInbound({
      product: form.product,
      batch: form.batch,
      qty: form.qty,
      warehouse: form.warehouse,
      inbound_date: form.inbound_date || null,
      work_order_code: form.work_order_code || '',
      inspection_code: form.inspection_code || '',
      remark: form.remark || ''
    })
    ElMessage.success('入库单已创建（草稿），确认后才写库存流水')
    dialogVisible.value = false
    loadInbounds()
  } catch (e) {
    ElMessage.error('创建失败：' + (e?.message || e))
  } finally {
    saving.value = false
  }
}

async function onConfirmInbound(row) {
  await ElMessageBox.confirm(
    `确认入库单「${row.code}」？确认后写库存流水，不可撤销。`, '确认入库', { type: 'warning' }
  )
  try {
    await confirmFinishedInbound(row.id)
    ElMessage.success('已入库')
    loadInbounds()
  } catch (e) {
    ElMessage.error('确认失败：' + (e?.message || e))
  }
}

async function onCancelInbound(row) {
  await ElMessageBox.confirm(`作废入库单「${row.code}」？`, '作废', { type: 'warning' })
  try {
    await cancelFinishedInbound(row.id)
    ElMessage.success('已作废')
    loadInbounds()
  } catch (e) {
    ElMessage.error('作废失败：' + (e?.message || e))
  }
}

function openShipment() {
  Object.assign(shipmentForm, {
    customer: null,
    warehouse: finishedWarehouses.value[0]?.id || null,
    ship_date: new Date().toISOString().slice(0, 10),
    order_code: '',
    items: [{ batch: null, qty: undefined }]
  })
  shipmentVisible.value = true
}

async function onSaveShipment() {
  await shipmentFormRef.value.validate()
  const items = shipmentForm.items.filter((it) => it.batch && it.qty > 0)
  if (!items.length) {
    ElMessage.warning('至少填一行完整明细（批次 + 数量）')
    return
  }
  saving.value = true
  try {
    await createShipment({
      customer: shipmentForm.customer,
      warehouse: shipmentForm.warehouse,
      ship_date: shipmentForm.ship_date || null,
      order_code: shipmentForm.order_code || '',
      items
    })
    ElMessage.success('发货单已创建（草稿）')
    shipmentVisible.value = false
    loadShipments()
  } catch (e) {
    ElMessage.error('创建失败：' + (e?.message || e))
  } finally {
    saving.value = false
  }
}

async function onConfirmShipment(row) {
  await ElMessageBox.confirm(
    `确认发货单「${row.code}」？确认后按批次扣减库存，不可撤销。`, '确认发货', { type: 'warning' }
  )
  try {
    await confirmShipment(row.id)
    ElMessage.success('已发货')
    loadShipments()
  } catch (e) {
    ElMessage.error('确认失败：' + (e?.message || e))
  }
}

function openShipmentDetail(row) {
  shipmentDetailRow.value = row
  shipmentDetailItems.value = row.items || []
  shipmentDetailVisible.value = true
}

onMounted(async () => {
  await loadOptions()
  await loadInbounds()
})
</script>
