<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm
        :fields="searchFields"
        :loading="loading"
        @search="onSearch"
        @reset="onReset"
      >
        <el-button type="primary" @click="openCreate">新增产品</el-button>
      </SearchForm>

      <BaseTable
        :columns="columns"
        :rows="rows"
        :total="total"
        @change="onPageChange"
      >
        <template #status="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑产品' : '新增产品'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="产品编码" prop="code">
          <el-input v-model="form.code" :disabled="Boolean(form.id)" placeholder="如 PF-PL-001" />
        </el-form-item>
        <el-form-item label="产品名称" prop="name">
          <el-input v-model="form.name" placeholder="如 法兰盘 A" />
        </el-form-item>
        <el-form-item label="图号">
          <el-input v-model="form.drawing_no" />
        </el-form-item>
        <el-form-item label="产品族">
          <el-select v-model="form.family" placeholder="请选择" clearable style="width: 100%">
            <el-option v-for="o in familyOptionsList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="主材料">
          <el-select v-model="form.material" placeholder="请选择" clearable filterable style="width: 100%">
            <el-option v-for="o in materialOptionsList" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.spec" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.uom" style="width: 120px" />
        </el-form-item>
        <el-form-item label="标准成本">
          <el-input-number v-model="form.std_cost" :min="0" :precision="2" :step="1" style="width: 160px" />
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
/**
 * 产品管理页 —— 全项目第一个"标准页"，其余模块照这个结构写即可。
 *
 * 标准结构：SearchForm 查询区 → BaseTable 列表 → el-dialog 表单
 * 关键约定：
 *   1. 页面里不写接口地址，全部走 @/api
 *   2. 表格与分页交给 BaseTable，页面只管取数
 *   3. 删除一律二次确认
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  createProduct,
  deleteProduct,
  familyOptions,
  listProducts,
  materialOptions,
  updateProduct
} from '@/api/masterdata'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const familyOptionsList = ref([])
const materialOptionsList = ref([])

// 注意：必须是 ref。产品族选项是异步加载的，
// 用普通数组改 options 不会触发视图更新，下拉会一直空白。
const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '编码/名称/图号' },
  { prop: 'family', label: '产品族', type: 'select', options: [] },
  {
    prop: 'is_active', label: '状态', type: 'select',
    options: [{ value: true, label: '启用' }, { value: false, label: '停用' }]
  }
])

const columns = [
  { prop: 'code', label: '产品编码', width: 130 },
  { prop: 'name', label: '产品名称' },
  { prop: 'drawing_no', label: '图号', width: 120 },
  { prop: 'family_name', label: '产品族', width: 110 },
  { prop: 'material_name', label: '主材料', width: 110 },
  { prop: 'uom', label: '单位', width: 70 },
  { prop: 'std_cost', label: '标准成本', width: 100 },
  { prop: 'is_active', label: '状态', width: 90, slot: 'status' },
  { prop: 'actions', label: '操作', width: 130, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, code: '', name: '', drawing_no: '', family: null, material: null,
  spec: '', uom: '件', std_cost: 0, is_active: true
})

const rules = {
  code: [{ required: true, message: '请输入产品编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listProducts({ page: page.value, page_size: pageSize.value, ...query.value })
    rows.value = data.results
    total.value = data.count
  } catch (e) {
    // 错误提示已由 request.js 统一处理
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
  page.value = 1
  load()
}

function onPageChange({ page: p, pageSize: s }) {
  page.value = p
  pageSize.value = s
  load()
}

function resetForm() {
  Object.assign(form, {
    id: null, code: '', name: '', drawing_no: '', family: null, material: null,
    spec: '', uom: '件', std_cost: 0, is_active: true
  })
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    code: row.code,
    name: row.name,
    drawing_no: row.drawing_no,
    family: row.family,
    material: row.material,
    spec: row.spec,
    uom: row.uom,
    std_cost: Number(row.std_cost || 0),
    is_active: row.is_active
  })
  dialogVisible.value = true
}

async function onSave() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.id
    if (form.id) {
      await updateProduct(form.id, payload)
      ElMessage.success('已保存')
    } else {
      await createProduct(payload)
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // 已由 request.js 提示
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除产品「${row.name}」吗？`, '确认删除', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await deleteProduct(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    // 已提示
  }
}

onMounted(async () => {
  const [families, materials] = await Promise.all([familyOptions(), materialOptions()])
  familyOptionsList.value = families
  materialOptionsList.value = materials
  searchFields.value[1].options = families.map((x) => ({ value: x.id, label: x.name }))
  load()
})
</script>
