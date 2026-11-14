<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增菜单</el-button>
      </SearchForm>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="tip"
        title="菜单决定侧边栏显示什么、点击后打开哪个前端路由。菜单存在数据库里而不是写死在代码里，所以加一个页面不用改代码（元数据驱动）。"
      />

      <el-table
        :data="tree"
        row-key="id"
        border
        default-expand-all
        :tree-props="{ children: 'children' }"
        size="default"
      >
        <el-table-column prop="name" label="名称" min-width="200">
          <template #default="{ row }">
            <span :class="['nm', row.menu_type]">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="编码" width="180">
          <template #default="{ row }">
            <code class="mono">{{ row.code }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="menu_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.menu_type)" size="small" effect="plain">
              {{ typeLabel(row.menu_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路由" min-width="170">
          <template #default="{ row }">
            <code class="mono path">{{ row.path || '—' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="permission_code" label="权限码" min-width="180">
          <template #default="{ row }">
            <code class="mono perm">{{ row.permission_code || '—' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column prop="is_active" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑菜单' : '新增菜单'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" :disabled="Boolean(form.id)" placeholder="如 md_product，全局唯一" />
        </el-form-item>
        <el-form-item label="显示名称" prop="name">
          <el-input v-model="form.name" placeholder="如 产品管理" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.menu_type">
            <el-radio label="dir">目录</el-radio>
            <el-radio label="menu">菜单</el-radio>
            <el-radio label="button">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="上级菜单">
          <el-select v-model="form.parent" clearable placeholder="不选表示顶级" style="width: 100%">
            <el-option
              v-for="m in parentOptions"
              :key="m.id"
              :label="`${m.name}（${m.code}）`"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="前端路由">
          <el-input v-model="form.path" placeholder="如 /masterdata/products" />
        </el-form-item>
        <el-form-item label="权限码">
          <el-input v-model="form.permission_code" placeholder="如 masterdata:product:read" />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="form.icon" placeholder="Element Plus 图标名，如 Box" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="999" />
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
 * 菜单管理页（树表）。
 *
 * 答辩会被问：「加一个新页面要改代码吗？」
 * 答：不用。在菜单表加一条记录 + 在路由表注册页面组件即可，
 *     菜单的显示与权限都来自数据，不是写死的。
 *
 * 注意：新增菜单后要给角色分配才能看到（角色管理 → 分配菜单）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import { allMenus, createMenu, deleteMenu, updateMenu } from '@/api/core'

const loading = ref(false)
const saving = ref(false)
const menus = ref([])
const query = ref({})

const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '编码 / 名称 / 权限码' },
  {
    prop: 'menu_type',
    label: '类型',
    type: 'select',
    width: '140px',
    options: [
      { value: 'dir', label: '目录' },
      { value: 'menu', label: '菜单' },
      { value: 'button', label: '按钮' }
    ]
  }
])

const tree = computed(() => {
  const kw = (query.value.search || '').trim().toLowerCase()
  const type = query.value.menu_type
  let list = menus.value
  if (type) list = list.filter((m) => m.menu_type === type)
  if (kw) {
    list = list.filter((m) =>
      [m.code, m.name, m.permission_code].some((v) => String(v || '').toLowerCase().includes(kw)))
  }
  const byId = {}
  list.forEach((m) => {
    byId[m.id] = { ...m, children: [] }
  })
  const roots = []
  list.forEach((m) => {
    const node = byId[m.id]
    if (m.parent && byId[m.parent]) byId[m.parent].children.push(node)
    else roots.push(node)
  })
  const sortRec = (arr) => {
    arr.sort((a, b) => (a.sort - b.sort) || a.code.localeCompare(b.code))
    arr.forEach((x) => sortRec(x.children))
  }
  sortRec(roots)
  return roots
})

const parentOptions = computed(() =>
  menus.value.filter((m) => m.menu_type === 'dir' || m.menu_type === 'menu'))

function typeLabel(t) {
  return t === 'dir' ? '目录' : t === 'menu' ? '菜单' : '按钮'
}
function typeTag(t) {
  return t === 'dir' ? 'warning' : t === 'menu' ? '' : 'info'
}

async function load() {
  loading.value = true
  try {
    const data = await allMenus()
    menus.value = (data && data.results) || []
  } catch (e) {
    console.error('[MenuList] 加载菜单失败', e)
  } finally {
    loading.value = false
  }
}

function onSearch(params) {
  query.value = params
}
function onReset() {
  query.value = {}
}

// ---------------- 新增 / 编辑 ----------------
const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null,
  code: '',
  name: '',
  menu_type: 'menu',
  parent: null,
  path: '',
  permission_code: '',
  icon: '',
  sort: 50,
  is_active: true
})

const rules = {
  code: [{ required: true, message: '请输入菜单编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }]
}

function openCreate() {
  Object.assign(form, {
    id: null,
    code: '',
    name: '',
    menu_type: 'menu',
    parent: null,
    path: '',
    permission_code: '',
    icon: '',
    sort: 50,
    is_active: true
  })
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    code: row.code,
    name: row.name,
    menu_type: row.menu_type,
    parent: row.parent || null,
    path: row.path || '',
    permission_code: row.permission_code || '',
    icon: row.icon || '',
    sort: row.sort || 0,
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
      menu_type: form.menu_type,
      parent: form.parent || null,
      path: form.path || '',
      permission_code: form.permission_code || '',
      icon: form.icon || '',
      sort: form.sort,
      is_active: form.is_active
    }
    if (form.id) {
      await updateMenu(form.id, payload)
      ElMessage.success('已保存')
    } else {
      await createMenu(payload)
      ElMessage.success('已新增（记得去角色管理里分配给角色，否则看不到）')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    console.error('[MenuList] 保存失败', e)
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  const kids = (row.children && row.children.length) || 0
  try {
    await ElMessageBox.confirm(
      kids
        ? `「${row.name}」下面还有 ${kids} 个子项，删除会一并影响。确定删除吗？`
        : `确定删除菜单「${row.name}」吗？`,
      '确认删除',
      { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await deleteMenu(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    console.error('[MenuList] 删除失败', e)
  }
}

onMounted(load)
</script>

<style scoped>
.tip {
  margin: 4px 0 14px;
}
.mono {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
}
.path {
  color: #0f9da8;
}
.perm {
  color: #b3651c;
}
.nm {
  font-weight: 500;
}
.nm.dir {
  font-weight: 700;
  color: #162e58;
}
</style>
