<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增标准</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #is_active="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openItems(row)">检验项</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑标准' : '新增标准'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="标准编码" prop="code">
          <el-input v-model="form.code" :disabled="Boolean(form.id)" />
        </el-form-item>
        <el-form-item label="标准名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="适用产品">
          <el-select v-model="form.product" filterable clearable style="width: 100%">
            <el-option v-for="o in productList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
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

    <!-- 检验项维护 -->
    <el-drawer v-model="itemsVisible" :title="`检验项 - ${current?.name || ''}`" size="600px">
      <div class="item-toolbar">
        <el-button type="primary" size="small" @click="itemDialog = true">添加检验项</el-button>
      </div>
      <el-table :data="itemRows" border size="small">
        <el-table-column prop="name" label="检验项" min-width="120" />
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="lower_limit" label="下限" width="90" />
        <el-table-column prop="upper_limit" label="上限" width="90" />
        <el-table-column prop="sample_size" label="抽检数" width="80" />
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button link type="danger" @click="onDeleteItem(row)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="itemDialog" title="添加检验项" width="460px" append-to-body>
      <el-form :model="itemForm" label-width="90px">
        <el-form-item label="检验项名" required>
          <el-input v-model="itemForm.name" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="itemForm.unit" style="width: 120px" />
        </el-form-item>
        <el-form-item label="下限">
          <el-input-number v-model="itemForm.lower_limit" :precision="3" style="width: 160px" />
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="itemForm.upper_limit" :precision="3" style="width: 160px" />
        </el-form-item>
        <el-form-item label="抽检数">
          <el-input-number v-model="itemForm.sample_size" :min="1" style="width: 160px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/** 检验标准 —— 契约 2.8：/quality/standards/ + {id}/items/。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  createStandard, createStandardItem, deleteStandardItem,
  listStandardItems, listStandards, updateStandard
} from '@/api/quality'
import { productOptions } from '@/api/masterdata'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})
const productList = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '标准编码/名称' },
  { prop: 'is_active', label: '状态', type: 'select',
    options: [{ value: true, label: '启用' }, { value: false, label: '停用' }] }
])

const columns = [
  { prop: 'code', label: '标准编码', width: 140 },
  { prop: 'name', label: '标准名称' },
  { prop: 'product_name', label: '适用产品', width: 130 },
  { prop: 'is_active', label: '状态', width: 80, slot: 'is_active' },
  { prop: 'actions', label: '操作', width: 200, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, code: '', name: '', product: null, is_active: true })
const rules = {
  code: [{ required: true, message: '请输入标准编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入标准名称', trigger: 'blur' }]
}

const itemsVisible = ref(false)
const itemDialog = ref(false)
const current = ref(null)
const itemRows = ref([])
const itemForm = reactive({ name: '', unit: '', lower_limit: undefined, upper_limit: undefined, sample_size: 3 })

async function load() {
  loading.value = true
  try {
    const data = await listStandards({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { id: null, code: '', name: '', product: null, is_active: true })
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
      await updateStandard(form.id, payload)
    } else {
      await createStandard(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确定删除标准「${row.name}」？`, '删除确认', { type: 'warning' })
  await updateStandard(row.id, { is_active: false })
  ElMessage.success('已停用（历史检验单引用，物理删除已禁用）')
  load()
}

async function openItems(row) {
  current.value = row
  itemsVisible.value = true
  const data = await listStandardItems(row.id)
  itemRows.value = data.results || data || []
}

async function onSaveItem() {
  if (!itemForm.name) {
    ElMessage.warning('请输入检验项名')
    return
  }
  saving.value = true
  try {
    await createStandardItem(current.value.id, { ...itemForm })
    ElMessage.success('已添加')
    itemDialog.value = false
    await openItems(current.value)
  } finally {
    saving.value = false
  }
}

async function onDeleteItem(row) {
  await ElMessageBox.confirm(`删除检验项「${row.name}」？`, '删除确认', { type: 'warning' })
  await deleteStandardItem(row.id)
  await openItems(current.value)
}

onMounted(async () => {
  load()
  productList.value = await productOptions()
})
</script>

<style scoped>
.item-toolbar {
  margin-bottom: 12px;
}
</style>
