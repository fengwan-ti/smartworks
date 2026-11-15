<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增库位</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #is_receiving="{ row }">
          <el-tag v-if="row.is_receiving" size="small" type="success">收料口</el-tag>
        </template>
        <template #is_shipping="{ row }">
          <el-tag v-if="row.is_shipping" size="small" type="warning">发货口</el-tag>
        </template>
        <template #is_active="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑库位' : '新增库位'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="所属仓库" prop="warehouse">
          <el-select v-model="form.warehouse" filterable style="width: 100%">
            <el-option v-for="o in warehouseList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="库位编码" prop="code">
          <el-input v-model="form.code" :disabled="Boolean(form.id)" placeholder="如 A-01-01" />
        </el-form-item>
        <el-form-item label="库位名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="form.area" placeholder="如 原料区 / 成品区 / 发货区" />
        </el-form-item>
        <el-form-item label="收料口">
          <el-switch v-model="form.is_receiving" />
        </el-form-item>
        <el-form-item label="发货口">
          <el-switch v-model="form.is_shipping" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
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
/** 库位管理 —— in_location（A 的共享表，字段 area/is_receiving/is_shipping）。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { createLocation, deleteLocation, listLocations, updateLocation, warehouseOptions } from '@/api/inventory'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const warehouseList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '库位编码/名称' },
  { prop: 'warehouse', label: '仓库', type: 'select', options: [] }
])

const columns = [
  { prop: 'warehouse_name', label: '仓库', width: 130 },
  { prop: 'code', label: '库位编码', width: 120 },
  { prop: 'name', label: '库位名称' },
  { prop: 'area', label: '区域', width: 110 },
  { prop: 'is_receiving', label: '收料', width: 80, slot: 'is_receiving' },
  { prop: 'is_shipping', label: '发货', width: 80, slot: 'is_shipping' },
  { prop: 'is_active', label: '状态', width: 80, slot: 'is_active' },
  { prop: 'actions', label: '操作', width: 130, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, warehouse: null, code: '', name: '', area: '',
  is_receiving: false, is_shipping: false, is_active: true
})
const rules = {
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }],
  code: [{ required: true, message: '请输入库位编码', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listLocations({ page: page.value, page_size: pageSize.value, ...query.value })
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
    id: null, warehouse: null, code: '', name: '', area: '',
    is_receiving: false, is_shipping: false, is_active: true
  })
  dialogVisible.value = true
}
function openEdit(row) {
  Object.assign(form, row)
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.id
    if (form.id) {
      await updateLocation(form.id, payload)
    } else {
      await createLocation(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确定删除库位「${row.code}」？`, '删除确认', { type: 'warning' })
  await deleteLocation(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  load()
  warehouseList.value = await warehouseOptions()
  searchFields.value[1].options = warehouseList.value.map((o) => ({ value: o.id, label: o.name }))
})
</script>
