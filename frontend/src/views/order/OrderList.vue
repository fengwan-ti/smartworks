<template>
  <div class="o-page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <div>
            <div class="title">销售订单</div>
            <div class="sub">订单状态：草稿 → 已确认 → 已排产 → 生产中 → 已发货 → 关闭（异常可取消）</div>
          </div>
          <div class="actions">
            <el-button type="primary" @click="openCreate">新增订单</el-button>
            <el-button @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-input v-model="query.search" placeholder="订单号 / 客户" clearable style="width: 200px" @keyup.enter="load" />
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px">
          <el-option v-for="s in STATUS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="query.customer" placeholder="客户" clearable filterable style="width: 170px">
          <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand">
              <el-table :data="row.items || []" size="small" border>
                <el-table-column prop="product_code" label="产品编码" width="130" />
                <el-table-column prop="product_name" label="产品名称" width="130" />
                <el-table-column prop="qty" label="数量" width="100" align="right" />
                <el-table-column prop="product_uom" label="单位" width="70" align="center" />
                <el-table-column prop="due_date" label="明细交期" width="120" />
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="订单号" width="150" />
        <el-table-column prop="customer_name" label="客户" width="130" />
        <el-table-column prop="order_date" label="下单日期" width="110" />
        <el-table-column prop="due_date" label="交期" width="110" />
        <el-table-column prop="priority" label="优先级" width="80" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft'" link type="success" @click="onConfirm(row)">确认</el-button>
            <el-button v-if="row.status !== 'cancelled' && row.status !== 'closed'" link type="warning" @click="onCancel(row)">取消</el-button>
            <el-button link type="primary" @click="showDetail(row)">明细</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        layout="total, sizes, prev, pager, next"
        :total="total"
        :current-page="query.page"
        :page-size="query.page_size"
        :page-sizes="[10, 20, 50]"
        @current-change="(p) => { query.page = p; load() }"
        @size-change="(s) => { query.page_size = s; query.page = 1; load() }"
      />
    </el-card>

    <el-dialog v-model="createVisible" title="新增销售订单" width="760px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="客户">
          <el-select v-model="form.customer" placeholder="请选择客户" filterable clearable style="width: 100%">
            <el-option v-for="c in customers" :key="c.id" :label="`${c.code} ${c.name}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="下单日期" prop="order_date">
          <el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" style="width: 180px" />
        </el-form-item>
        <el-form-item label="交期" prop="due_date">
          <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width: 180px" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="9" />
          <span class="tip">1 最高</span>
        </el-form-item>
        <el-form-item label="订单明细" required>
          <div class="items-box">
            <div v-for="(it, i) in form.items" :key="i" class="item-row">
              <el-select v-model="it.product" placeholder="产品" filterable style="width: 260px">
                <el-option v-for="p in products" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
              </el-select>
              <el-input-number v-model="it.qty" :min="0.001" :precision="0" :step="1" style="width: 140px" />
              <el-button link type="danger" @click="form.items.splice(i, 1)">删除</el-button>
            </div>
            <el-button size="small" @click="form.items.push({ product: null, qty: 10 })">+ 添加明细</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="订单明细" width="640px">
      <div v-if="detailRow" class="detail-head">
        <b>{{ detailRow.code }}</b> · {{ detailRow.customer_name }} · 交期 {{ detailRow.due_date }}
        <el-tag size="small" :type="statusType(detailRow.status)">{{ statusLabel(detailRow.status) }}</el-tag>
      </div>
      <el-table :data="detailRow?.items || []" border size="small">
        <el-table-column prop="product_code" label="产品编码" width="130" />
        <el-table-column prop="product_name" label="产品" width="120" />
        <el-table-column prop="qty" label="数量" align="right" />
        <el-table-column prop="product_uom" label="单位" width="70" align="center" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { customerOptions, productOptions } from '@/api/masterdata'
import { createOrder, fetchOrders, confirmOrder, cancelOrder } from '@/api/order'

const STATUS = [
  { value: 'draft', label: '草稿' }, { value: 'confirmed', label: '已确认' },
  { value: 'scheduled', label: '已排产' }, { value: 'in_production', label: '生产中' },
  { value: 'shipped', label: '已发货' }, { value: 'closed', label: '关闭' },
  { value: 'cancelled', label: '取消' },
]
const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, search: '', status: '', customer: '' })
const customers = ref([])
const products = ref([])

const createVisible = ref(false)
const formRef = ref()
const form = reactive({ customer: null, order_date: '', due_date: '', priority: 5, remark: '', items: [] })
const rules = {
  order_date: [{ required: true, message: '请选择下单日期', trigger: 'change' }],
  due_date: [{ required: true, message: '请选择交期', trigger: 'change' }],
}
const detailVisible = ref(false)
const detailRow = ref(null)

function statusType(s) {
  return { draft: 'info', confirmed: 'primary', scheduled: 'warning', in_production: 'warning',
    shipped: 'success', closed: 'success', cancelled: 'danger' }[s] || 'info'
}
function statusLabel(s) { return STATUS.find((x) => x.value === s)?.label || s }

async function load() {
  loading.value = true
  try {
    const params = { page: query.page, page_size: query.page_size, ordering: 'due_date' }
    if (query.search) params.search = query.search
    if (query.status) params.status = query.status
    if (query.customer) params.customer = query.customer
    const data = await fetchOrders(params)
    rows.value = data.results || []
    total.value = data.count || 0
  } finally { loading.value = false }
}
function resetQuery() { query.search = ''; query.status = ''; query.customer = ''; query.page = 1; load() }

function openCreate() {
  Object.assign(form, { customer: null, order_date: '', due_date: '', priority: 5, remark: '',
    items: [{ product: null, qty: 10 }] })
  createVisible.value = true
}
async function submitCreate() {
  await formRef.value.validate()
  const items = form.items.filter((i) => i.product && i.qty > 0)
  if (!items.length) { ElMessage.warning('至少一条订单明细'); return }
  saving.value = true
  try {
    await createOrder({ ...form, items })
    ElMessage.success('已创建')
    createVisible.value = false
    await load()
  } finally { saving.value = false }
}

async function onConfirm(row) {
  await ElMessageBox.confirm(`确认订单 ${row.code}？确认后才能转 MPS。`, '确认', { type: 'warning' })
  await confirmOrder(row.id)
  ElMessage.success('已确认')
  await load()
}
async function onCancel(row) {
  const { value } = await ElMessageBox.prompt('取消订单必须填写原因：', '取消订单', { inputPattern: /\S+/, inputErrorMessage: '原因不能为空' })
  await cancelOrder(row.id, { reason: value })
  ElMessage.success('已取消')
  await load()
}
function showDetail(row) { detailRow.value = row; detailVisible.value = true }

onMounted(async () => {
  [customers.value, products.value] = await Promise.all([customerOptions(), productOptions()])
  await load()
})
</script>

<style scoped>
.o-page { padding: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 16px; font-weight: 600; color: var(--sw-primary); }
.sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.actions { display: flex; gap: 8px; }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.expand { padding: 8px 20px; background: #fafafa; }
.items-box { width: 100%; }
.item-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.tip { margin-left: 8px; font-size: 12px; color: #8a8f99; }
.detail-head { margin-bottom: 10px; display: flex; gap: 8px; align-items: center; }
</style>
