<template>
  <div class="route-page">
    <el-card shadow="never" class="side-card">
      <template #header>
        <div class="side-head">
          <span class="card-title">BOM 清单</span>
          <el-button type="primary" size="small" @click="openCreateBom">新建</el-button>
        </div>
      </template>
      <div class="side-filter">
        <el-input v-model="query.search" placeholder="BOM 编码 / 产品" clearable size="small" />
        <el-select v-model="query.status" placeholder="状态" clearable size="small" style="width: 110px">
          <el-option label="草稿" value="draft" />
          <el-option label="生效" value="active" />
          <el-option label="停用" value="obsolete" />
        </el-select>
      </div>
      <el-scrollbar height="calc(100vh - 260px)">
        <div v-for="b in boms" :key="b.id" class="route-item" :class="{ active: current && current.id === b.id }" @click="selectBom(b)">
          <div class="route-line1">
            <span class="route-name">{{ b.product_name }}</span>
            <el-tag size="small" :type="statusType(b.status)">{{ statusLabel(b.status) }}</el-tag>
          </div>
          <div class="route-line2">
            <span>{{ b.code }}</span>
            <span>V{{ b.version }} · {{ b.items_count }} 项物料</span>
          </div>
        </div>
        <el-empty v-if="!boms.length" description="还没有 BOM" :image-size="70" />
      </el-scrollbar>
    </el-card>

    <el-card shadow="never" class="main-card">
      <template v-if="current">
        <div class="detail-head">
          <div>
            <div class="detail-title">
              {{ current.product_name }}
              <el-tag size="small" :type="statusType(current.status)">{{ statusLabel(current.status) }}</el-tag>
            </div>
            <div class="detail-sub">{{ current.code }} · {{ current.product_code }} · V{{ current.version }}</div>
          </div>
          <div class="detail-actions">
            <el-button v-if="current.status === 'draft'" type="success" @click="onActivate">生效</el-button>
            <el-button type="primary" @click="openCreateItem">添加物料</el-button>
          </div>
        </div>

        <el-table v-loading="loading" :data="current.items || []" border stripe>
          <el-table-column prop="material_code" label="物料编码" width="130" />
          <el-table-column prop="material_name" label="物料名称" width="140" />
          <el-table-column prop="material_uom" label="单位" width="70" align="center" />
          <el-table-column prop="qty_per" label="单件用量" width="110" align="right" />
          <el-table-column prop="loss_rate" label="损耗率(%)" width="110" align="right" />
          <el-table-column label="替代料" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_substitute" size="small" type="warning">是</el-tag>
              <span v-else>否</span>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="120" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditItem(row)">编辑</el-button>
              <el-button link type="danger" @click="removeItem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="total-line">单件用量合计：<b>{{ totalQty }}</b>（含损耗前）</div>
      </template>
      <el-empty v-else description="从左侧选一条 BOM，或点“新建”" />
    </el-card>

    <el-dialog v-model="bomDialog" title="新建 BOM" width="460px">
      <el-form label-width="90px">
        <el-form-item label="产品" required>
          <el-select v-model="newBomProduct" placeholder="请选择产品" filterable style="width: 100%">
            <el-option v-for="p in productList" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="dialog-tip">系统自动生成编码 BM-&lt;产品编码&gt;-V&lt;版本&gt;，初始为草稿；同一产品只能有一个生效 BOM。</div>
      <template #footer>
        <el-button @click="bomDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitBom">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="itemDialog" :title="itemForm.id ? '编辑物料' : '添加物料'" width="520px" destroy-on-close>
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-width="110px">
        <el-form-item label="物料" prop="material">
          <el-select v-model="itemForm.material" placeholder="请选择物料" filterable style="width: 100%">
            <el-option v-for="m in materialList" :key="m.id" :label="`${m.code} ${m.name}`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="单件用量" prop="qty_per">
          <el-input-number v-model="itemForm.qty_per" :min="0.001" :precision="3" :step="0.1" style="width: 180px" />
          <span class="form-tip">每 1 件产品消耗量</span>
        </el-form-item>
        <el-form-item label="损耗率(%)">
          <el-input-number v-model="itemForm.loss_rate" :min="0" :max="100" :precision="2" style="width: 180px" />
        </el-form-item>
        <el-form-item label="替代料">
          <el-switch v-model="itemForm.is_substitute" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="itemForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { materialOptions, productOptions } from '@/api/masterdata'
import {
  createBom, createBomItem, deleteBomItem, fetchBomItems, fetchBoms,
  patchBom, patchBomItem,
} from '@/api/process'

const loading = ref(false)
const saving = ref(false)
const boms = ref([])
const current = ref(null)
const productList = ref([])
const materialList = ref([])
const query = reactive({ search: '', status: '' })

const bomDialog = ref(false)
const newBomProduct = ref(null)
const itemDialog = ref(false)
const itemFormRef = ref()
const emptyItem = () => ({ id: null, material: null, qty_per: 1, loss_rate: 0, is_substitute: false, remark: '' })
const itemForm = reactive(emptyItem())
const itemRules = {
  material: [{ required: true, message: '请选择物料', trigger: 'change' }],
  qty_per: [{ required: true, message: '请填写用量', trigger: 'change' }],
}

const totalQty = computed(() => {
  const items = current.value?.items || []
  return items.reduce((s, i) => s + Number(i.qty_per || 0), 0).toFixed(3)
})

function statusType(s) { return { draft: 'info', active: 'success', obsolete: 'danger' }[s] || 'info' }
function statusLabel(s) { return { draft: '草稿', active: '生效', obsolete: '停用' }[s] || s }

async function loadBoms() {
  const params = { page: 1, page_size: 50, ordering: 'code' }
  if (query.search) params.search = query.search
  if (query.status) params.status = query.status
  const data = await fetchBoms(params)
  boms.value = data.results || []
  if (current.value && boms.value.some((b) => b.id === current.value.id)) {
    await selectBom(boms.value.find((b) => b.id === current.value.id))
  }
}

async function selectBom(row) {
  loading.value = true
  try {
    const data = await fetchBoms({ search: row.code })
    current.value = (data.results || []).find((b) => b.id === row.id) || row
    current.value.items = await fetchBomItems(row.id)
  } finally {
    loading.value = false
  }
}

function openCreateBom() { newBomProduct.value = null; bomDialog.value = true }
async function submitBom() {
  if (!newBomProduct.value) { ElMessage.warning('请选择产品'); return }
  saving.value = true
  try {
    const bom = await createBom({ product: newBomProduct.value })
    ElMessage.success('已创建草稿 BOM')
    bomDialog.value = false
    await loadBoms()
    await selectBom(bom)
  } finally { saving.value = false }
}

async function onActivate() {
  await ElMessageBox.confirm('生效后参与齐套检查与领料，同一产品只能有一个生效 BOM。继续？', '生效确认', { type: 'warning' })
  await patchBom(current.value.id, { status: 'active' })
  ElMessage.success('已生效')
  await loadBoms()
}

function openCreateItem() { Object.assign(itemForm, emptyItem()); itemDialog.value = true }
function openEditItem(row) {
  Object.assign(itemForm, {
    id: row.id, material: row.material, qty_per: Number(row.qty_per),
    loss_rate: Number(row.loss_rate), is_substitute: row.is_substitute, remark: row.remark || '',
  })
  itemDialog.value = true
}
async function submitItem() {
  await itemFormRef.value.validate()
  const payload = {
    material: itemForm.material, qty_per: String(itemForm.qty_per),
    loss_rate: String(itemForm.loss_rate), is_substitute: itemForm.is_substitute,
    remark: itemForm.remark,
  }
  saving.value = true
  try {
    if (itemForm.id) {
      await patchBomItem(current.value.id, itemForm.id, payload)
      ElMessage.success('已保存')
    } else {
      await createBomItem(current.value.id, payload)
      ElMessage.success('已添加')
    }
    itemDialog.value = false
    await selectBom(current.value)
    await loadBoms()
  } finally { saving.value = false }
}
async function removeItem(row) {
  await ElMessageBox.confirm(`确认从 BOM 移除「${row.material_code}」？`, '删除确认', { type: 'warning' })
  await deleteBomItem(current.value.id, row.id)
  ElMessage.success('已移除')
  await selectBom(current.value)
  await loadBoms()
}

onMounted(async () => {
  [productList.value, materialList.value] = await Promise.all([productOptions(), materialOptions()])
  await loadBoms()
})
</script>

<style scoped>
.route-page { display: flex; gap: 14px; padding: 14px; height: calc(100vh - 56px); box-sizing: border-box; }
.side-card { width: 330px; flex: none; }
.side-head { display: flex; align-items: center; justify-content: space-between; }
.side-filter { display: flex; gap: 8px; margin-bottom: 10px; }
.card-title { font-weight: 600; color: var(--sw-primary); }
.route-item { padding: 10px; border: 1px solid #e6e8eb; border-radius: 6px; margin-bottom: 8px; cursor: pointer; }
.route-item:hover { border-color: var(--sw-primary); }
.route-item.active { border-color: var(--sw-primary); background: #eef3ff; }
.route-line1 { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.route-name { font-weight: 600; }
.route-line2 { display: flex; justify-content: space-between; font-size: 12px; color: #8a8f99; }
.main-card { flex: 1; overflow: auto; }
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.detail-title { font-size: 16px; font-weight: 600; color: var(--sw-primary); display: flex; align-items: center; gap: 8px; }
.detail-sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.detail-actions { display: flex; gap: 8px; }
.total-line { margin-top: 10px; text-align: right; font-size: 13px; color: #606266; }
.form-tip { margin-left: 10px; font-size: 12px; color: #8a8f99; }
.dialog-tip { font-size: 12px; color: #8a8f99; }
</style>
