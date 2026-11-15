<template>
  <div class="mx-page">
    <el-card shadow="never" class="mx-card">
      <template #header>
        <div class="mx-head">
          <div>
            <div class="card-title">换型时间矩阵</div>
            <div class="card-sub">
              单位：分钟/次 · 行 = 前产品（from），列 = 后产品（to）· 有方向、不假设对称 ·
              <span class="warn">当前全部为 estimated（D 复核前不改成实测）</span>
            </div>
          </div>
          <div class="mx-actions">
            <el-button @click="openAdd">新增产品对</el-button>
            <el-upload :show-file-list="false" :http-request="doImport" accept=".xlsx">
              <el-button type="primary" :loading="importing">Excel 导入</el-button>
            </el-upload>
            <el-button @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="products" border size="default" class="mx-table">
        <el-table-column prop="name" label="from \\ to" width="150" fixed>
          <template #default="{ row }">{{ row.name }}<div class="cell-sub">{{ row.code }}</div></template>
        </el-table-column>
        <el-table-column
          v-for="to in products"
          :key="to.id"
          :label="to.name"
          min-width="110"
          align="center"
        >
          <template #header>
            <div>{{ to.name }}</div>
            <div class="cell-sub">{{ to.code }}</div>
          </template>
          <template #default="{ row }">
            <span v-if="row.id === to.id" class="diag">—</span>
            <el-link v-else type="primary" @click="openEdit(row, to)">
              {{ cellText(row.id, to.id) }}
            </el-link>
          </template>
        </el-table-column>
      </el-table>

      <div class="legend">
        <el-tag size="small" type="info">点击格子可修改分钟数</el-tag>
        <span class="legend-text">共 {{ cells.length }} 个产品对；同族 15/18，跨族 45，涉及板类 55/50（见 03 文档）</span>
      </div>
    </el-card>

    <el-dialog v-model="dialog" :title="editing ? '修改换型时间' : '新增产品对'" width="460px">
      <el-form label-width="100px">
        <el-form-item label="前产品">
          <el-select v-model="form.from_product" :disabled="editing" filterable style="width: 100%">
            <el-option v-for="p in products" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="后产品">
          <el-select v-model="form.to_product" :disabled="editing" filterable style="width: 100%">
            <el-option v-for="p in products" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="换型分钟">
          <el-input-number v-model="form.changeover_minutes" :min="0" :max="480" :step="1" />
        </el-form-item>
        <el-form-item label="数据来源">
          <el-select v-model="form.source" style="width: 100%">
            <el-option label="估值 estimated" value="estimated" />
            <el-option label="工艺标准 standard" value="standard" />
            <el-option label="实测 measured" value="measured" />
            <el-option label="导入 imported" value="imported" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createChangeover, fetchChangeoverMatrix, importChangeovers, patchChangeover,
} from '@/api/process'

const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const products = ref([])
const cells = ref([])
const dialog = ref(false)
const editing = ref(false)
const form = reactive({ id: null, from_product: null, to_product: null, changeover_minutes: 15, source: 'estimated', remark: '' })

const cellMap = ref({})

function key(f, t) { return `${f}-${t}` }

function cellText(f, t) {
  const c = cellMap.value[key(f, t)]
  return c ? `${c.changeover_minutes} 分` : '未登记'
}

async function load() {
  loading.value = true
  try {
    const data = await fetchChangeoverMatrix()
    products.value = data.products || []
    cells.value = data.cells || []
    const map = {}
    for (const c of cells.value) map[key(c.from_product_id, c.to_product_id)] = c
    cellMap.value = map
  } finally { loading.value = false }
}

function openAdd() {
  editing.value = false
  Object.assign(form, { id: null, from_product: null, to_product: null, changeover_minutes: 15, source: 'estimated', remark: '' })
  dialog.value = true
}

function openEdit(from, to) {
  const existing = cellMap.value[key(from.id, to.id)]
  editing.value = true
  Object.assign(form, {
    id: existing ? existing.id : null,
    from_product: from.id,
    to_product: to.id,
    changeover_minutes: existing ? existing.changeover_minutes : 15,
    source: existing ? existing.source : 'estimated',
    remark: '',
  })
  dialog.value = true
}

async function submit() {
  if (!form.from_product || !form.to_product) { ElMessage.warning('请选择前后产品'); return }
  if (form.from_product === form.to_product) { ElMessage.warning('前后产品不能相同'); return }
  saving.value = true
  try {
    const payload = { from_product: form.from_product, to_product: form.to_product, changeover_minutes: form.changeover_minutes, source: form.source, remark: form.remark }
    if (form.id) {
      await patchChangeover(form.id, payload)
    } else {
      await createChangeover(payload)
    }
    ElMessage.success('已保存')
    dialog.value = false
    await load()
  } finally { saving.value = false }
}

async function doImport({ file }) {
  importing.value = true
  try {
    const result = await importChangeovers(file)
    ElMessage.success(`导入完成：新建 ${result.created}，更新 ${result.updated}，失败 ${result.failed.length}`)
    await load()
  } finally { importing.value = false }
}

onMounted(load)
</script>

<style scoped>
.mx-page { padding: 14px; }
.mx-head { display: flex; justify-content: space-between; align-items: flex-start; }
.card-title { font-weight: 600; color: var(--sw-primary); }
.card-sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.warn { color: #e6a23c; }
.mx-actions { display: flex; gap: 8px; align-items: center; }
.mx-table { margin-top: 8px; }
.cell-sub { font-size: 11px; color: #a0a4ad; }
.diag { color: #c0c4cc; }
.legend { margin-top: 12px; display: flex; gap: 10px; align-items: center; }
.legend-text { font-size: 12px; color: #8a8f99; }
</style>
