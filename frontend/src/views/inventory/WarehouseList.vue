<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增仓库</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #type="{ row }">
          <el-tag size="small" :type="{ raw: 'warning', finished: 'success', wip: 'info' }[row.type] || 'info'">
            {{ row.type_display || row.type }}
          </el-tag>
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑仓库' : '新增仓库'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="仓库编码" prop="code">
          <el-input v-model="form.code" :disabled="Boolean(form.id)" placeholder="如 WH-RAW-01" />
        </el-form-item>
        <el-form-item label="仓库名称" prop="name">
          <el-input v-model="form.name" placeholder="如 原料仓一号" />
        </el-form-item>
        <el-form-item label="仓库类型" prop="type">
          <el-select v-model="form.type" style="width: 100%">
            <el-option label="原料仓" value="raw" />
            <el-option label="成品仓" value="finished" />
            <el-option label="在制品仓" value="wip" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置说明">
          <el-input v-model="form.address" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
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
/** 仓库管理 —— in_warehouse（A 的共享表）。 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  createWarehouse, deleteWarehouse, listWarehouses, updateWarehouse
} from '@/api/inventory'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', placeholder: '编码/名称' },
  {
    prop: 'type', label: '类型', type: 'select',
    options: [
      { value: 'raw', label: '原料仓' },
      { value: 'finished', label: '成品仓' },
      { value: 'wip', label: '在制品仓' }
    ]
  }
])

const columns = [
  { prop: 'code', label: '仓库编码', width: 140 },
  { prop: 'name', label: '仓库名称' },
  { prop: 'type', label: '类型', width: 100, slot: 'type' },
  { prop: 'address', label: '位置说明' },
  { prop: 'is_active', label: '状态', width: 80, slot: 'is_active' },
  { prop: 'remark', label: '备注' },
  { prop: 'actions', label: '操作', width: 130, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, code: '', name: '', type: 'raw', address: '', is_active: true, remark: '' })
const rules = {
  code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listWarehouses({ page: page.value, page_size: pageSize.value, ...query.value })
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
  Object.assign(form, { id: null, code: '', name: '', type: 'raw', address: '', is_active: true, remark: '' })
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
      await updateWarehouse(form.id, payload)
    } else {
      await createWarehouse(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确定删除仓库「${row.name}」？`, '删除确认', { type: 'warning' })
  await deleteWarehouse(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>
