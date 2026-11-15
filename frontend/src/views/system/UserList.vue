<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增用户</el-button>
      </SearchForm>

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #roles="{ row }">
          <el-tag v-for="r in row.role_names" :key="r" size="small" class="tag" effect="light">
            {{ r }}
          </el-tag>
          <span v-if="!row.role_names || !row.role_names.length" class="dim">—</span>
        </template>
        <template #status="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
          <el-tag v-if="row.is_superuser" type="warning" size="small" class="tag" effect="light">
            超管
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </BaseTable>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑用户' : '新增用户'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="Boolean(form.id)" placeholder="登录名，如 zhangsan" />
        </el-form-item>
        <el-form-item :label="form.id ? '重置密码' : '初始密码'" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="form.id ? '留空表示不修改' : '不填默认 123456'"
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.name" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="工号">
          <el-input v-model="form.employee_no" />
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.department" clearable style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位">
          <el-select v-model="form.position" clearable style="width: 100%">
            <el-option v-for="p in positionOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.roles" multiple clearable style="width: 100%">
            <el-option v-for="r in roleOptions" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" />
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
 * 用户管理页。
 *
 * 与角色页的区别（答辩会问）：
 *   角色决定「能看到什么」，用户决定「谁是这个角色」。
 *   所以新建用户后要在这里给他挂角色，菜单才会出现。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  createUser,
  deleteUser,
  listRoles,
  listUsers,
  updateUser
} from '@/api/core'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const roleOptions = ref([])
const deptOptions = ref([])
const positionOptions = ref([])

const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '用户名 / 姓名 / 工号' },
  {
    prop: 'is_active',
    label: '状态',
    type: 'select',
    options: [{ value: true, label: '启用' }, { value: false, label: '停用' }]
  }
])

const columns = [
  { prop: 'username', label: '用户名', width: 130 },
  { prop: 'name', label: '姓名', width: 100 },
  { prop: 'employee_no', label: '工号', width: 100 },
  { prop: 'department_name', label: '部门', width: 110 },
  { prop: 'position_name', label: '岗位', width: 120 },
  { prop: 'roles', label: '角色', slot: 'roles' },
  { prop: 'is_active', label: '状态', width: 140, slot: 'status' },
  { prop: 'actions', label: '操作', width: 130, slot: 'actions' }
]

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null,
  username: '',
  password: '',
  name: '',
  employee_no: '',
  department: null,
  position: null,
  roles: [],
  phone: '',
  is_active: true
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listUsers({ page: page.value, page_size: pageSize.value, ...query.value })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[UserList] 加载用户失败', e)
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

function openCreate() {
  Object.assign(form, {
    id: null,
    username: '',
    password: '',
    name: '',
    employee_no: '',
    department: null,
    position: null,
    roles: [],
    phone: '',
    is_active: true
  })
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    username: row.username,
    password: '',
    name: row.name,
    employee_no: row.employee_no,
    department: row.department,
    position: row.position,
    roles: Array.isArray(row.roles) ? [...row.roles] : [],
    phone: row.phone || '',
    is_active: row.is_active
  })
  dialogVisible.value = true
}

async function onSave() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload = {
      username: form.username,
      name: form.name,
      employee_no: form.employee_no || '',
      department: form.department,
      position: form.position,
      roles: form.roles,
      phone: form.phone || '',
      is_active: form.is_active
    }
    if (form.password) payload.password = form.password

    if (form.id) {
      await updateUser(form.id, payload)
      ElMessage.success('已保存')
    } else {
      await createUser(payload)
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    console.error('[UserList] 保存失败', e)
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.name || row.username}」吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    await deleteUser(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    console.error('[UserList] 删除失败', e)
  }
}

onMounted(async () => {
  try {
    const [rolePage, deptPage, posPage] = await Promise.all([
      listRoles({ page_size: 100 }),
      request.get('/core/departments/', { params: { page_size: 100 } }).catch(() => null),
      request.get('/core/positions/', { params: { page_size: 100 } }).catch(() => null)
    ])
    roleOptions.value = (rolePage && rolePage.results) || []
    deptOptions.value = (deptPage && deptPage.results) || []
    positionOptions.value = (posPage && posPage.results) || []
  } catch (e) {
    console.error('[UserList] 加载下拉选项失败', e)
  }
  load()
})
</script>

<style scoped>
.tag {
  margin-right: 4px;
}
.dim {
  color: #9aa7b4;
}
</style>
