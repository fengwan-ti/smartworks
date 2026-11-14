<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增角色</el-button>
      </SearchForm>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="tip"
        title="角色的作用是决定「谁能看到哪些菜单」。点每行的「分配菜单」改完即可生效，用户下次登录或刷新页面后菜单随之变化。"
      />

      <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
        <template #status="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" @click="openAssign(row)">分配菜单</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </BaseTable>
    </div>

    <!-- 新增 / 编辑角色 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑角色' : '新增角色'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="form.code" :disabled="Boolean(form.id)" placeholder="如 PLANNER" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="如 计划员" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
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

    <!-- 分配菜单 -->
    <el-dialog v-model="assignVisible" :title="`分配菜单 · ${assignRole.name || ''}`" width="560px">
      <div class="assign-head">
        <span class="dim">勾选该角色可以访问的菜单。父目录会自动跟着勾选。</span>
        <el-button link type="primary" @click="toggleAll">
          {{ allChecked ? '全不选' : '全选' }}
        </el-button>
      </div>
      <el-tree
        ref="treeRef"
        :data="menuTree"
        node-key="id"
        show-checkbox
        default-expand-all
        :props="{ label: 'label', children: 'children' }"
        class="assign-tree"
      />
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assigning" @click="onAssignSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 角色管理页。
 *
 * 为什么这页值得单独做（答辩会问）：
 *   菜单、按钮权限都挂在角色上，这里是「权限体系」唯一可视化的地方。
 *   改了角色 → 用户菜单变化 → 不用改一行代码，这就是元数据驱动。
 *
 * 后端接口：
 *   GET/POST      /core/roles/
 *   PATCH/DELETE  /core/roles/{id}/
 *   GET/POST      /core/roles/{id}/menus/   （整体覆盖，不是增量）
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import {
  allMenus,
  createRole,
  deleteRole,
  getRoleMenus,
  listRoles,
  updateRole
} from '@/api/core'

const loading = ref(false)
const saving = ref(false)
const assigning = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '编码 / 名称' },
  {
    prop: 'is_active',
    label: '状态',
    type: 'select',
    options: [{ value: true, label: '启用' }, { value: false, label: '停用' }]
  }
])

const columns = [
  { prop: 'code', label: '角色编码', width: 150 },
  { prop: 'name', label: '角色名称', width: 160 },
  { prop: 'description', label: '说明' },
  { prop: 'user_count', label: '用户数', width: 90 },
  { prop: 'menu_count', label: '菜单数', width: 90 },
  { prop: 'is_active', label: '状态', width: 90, slot: 'status' },
  { prop: 'actions', label: '操作', width: 220, slot: 'actions' }
]

// ---------------- 新增/编辑 ----------------
const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, code: '', name: '', description: '', is_active: true })

const rules = {
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await listRoles({
      page: page.value,
      page_size: pageSize.value,
      ...query.value
    })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[RoleList] 加载角色失败', e)
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
  Object.assign(form, { id: null, code: '', name: '', description: '', is_active: true })
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    code: row.code,
    name: row.name,
    description: row.description || '',
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
      code: form.code,
      name: form.name,
      description: form.description,
      is_active: form.is_active
    }
    if (form.id) {
      await updateRole(form.id, payload)
      ElMessage.success('已保存')
    } else {
      await createRole(payload)
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    console.error('[RoleList] 保存失败', e)
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除角色「${row.name}」吗？`, '确认删除', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await deleteRole(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    console.error('[RoleList] 删除失败', e)
  }
}

// ---------------- 分配菜单 ----------------
const assignVisible = ref(false)
const assignRole = ref({})
const menuTree = ref([])
const treeRef = ref()
const checkedIds = ref([])

const allChecked = computed(() => {
  const flat = []
  const walk = (list) => list.forEach((n) => {
    flat.push(n.id)
    if (n.children && n.children.length) walk(n.children)
  })
  walk(menuTree.value)
  return flat.length > 0 && checkedIds.value.length >= flat.length
})

function buildTree(menus) {
  // 只把目录与菜单放进树；按钮类作为叶子挂在父节点下
  const byId = {}
  menus.forEach((m) => {
    byId[m.id] = {
      id: m.id,
      label: `${m.name}${m.permission_code ? '  ·  ' + m.permission_code : ''}`,
      children: [],
      raw: m
    }
  })
  const roots = []
  menus.forEach((m) => {
    const node = byId[m.id]
    const parentId = m.parent
    if (parentId && byId[parentId]) byId[parentId].children.push(node)
    else roots.push(node)
  })
  return roots
}

async function openAssign(row) {
  assignRole.value = row
  assignVisible.value = true
  try {
    const [menuPage, assigned] = await Promise.all([allMenus(), getRoleMenus(row.id)])
    menuTree.value = buildTree((menuPage && menuPage.results) || [])
    const ids = (assigned && assigned.menu_ids) || []
    checkedIds.value = ids
    // el-tree 需要等渲染后设置勾选
    requestAnimationFrame(() => {
      if (treeRef.value) treeRef.value.setCheckedKeys(ids, false)
    })
  } catch (e) {
    console.error('[RoleList] 加载菜单或已分配项失败', e)
  }
}

function toggleAll() {
  if (!treeRef.value) return
  if (allChecked.value) {
    treeRef.value.setCheckedKeys([], false)
  } else {
    const flat = []
    const walk = (list) => list.forEach((n) => {
      flat.push(n.id)
      if (n.children && n.children.length) walk(n.children)
    })
    walk(menuTree.value)
    treeRef.value.setCheckedKeys(flat, false)
  }
}

async function onAssignSave() {
  if (!treeRef.value) return
  assigning.value = true
  try {
    // 半选的父节点也要提交，否则子菜单会父级缺失
    const checked = treeRef.value.getCheckedKeys()
    const half = treeRef.value.getHalfCheckedKeys()
    const ids = [...new Set([...checked, ...half])]
    await setRoleMenusSafe(assignRole.value.id, ids)
    ElMessage.success(`已保存，共 ${ids.length} 条菜单`)
    assignVisible.value = false
    load()
  } catch (e) {
    console.error('[RoleList] 保存菜单分配失败', e)
  } finally {
    assigning.value = false
  }
}

async function setRoleMenusSafe(id, ids) {
  const { setRoleMenus } = await import('@/api/core')
  return setRoleMenus(id, ids)
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.tip {
  margin: 4px 0 14px;
}
.assign-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.assign-head .dim {
  font-size: 12px;
  color: #6b7280;
}
.assign-tree {
  max-height: 380px;
  overflow: auto;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  padding: 8px;
}
</style>
