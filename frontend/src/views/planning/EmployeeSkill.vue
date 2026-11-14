<template>
  <div class="sw-page">
    <div class="sw-card">
      <SearchForm :fields="searchFields" :loading="loading" @search="onSearch" @reset="onReset">
        <el-button type="primary" @click="openCreate">新增技能</el-button>
      </SearchForm>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="tip"
        title="技能矩阵是「按工序找合格的人」的依据。B 的排产派工校验调用 /planning/employee-skills/qualified/?step_type=xxx 来确认这个工位有没有人能干。"
      />

      <el-tabs v-model="tab">
        <el-tab-pane label="技能明细" name="list">
          <BaseTable :columns="columns" :rows="rows" :total="total" @change="onPageChange">
            <template #level="{ row }">
              <el-tag :type="levelTag(row.level)" size="small" effect="light">
                {{ row.level_label }}
              </el-tag>
            </template>
            <template #cert="{ row }">
              <el-tag :type="row.is_certified ? 'success' : 'info'" size="small" effect="plain">
                {{ row.is_certified ? '持证' : '未持证' }}
              </el-tag>
            </template>
            <template #actions="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </BaseTable>
        </el-tab-pane>

        <el-tab-pane label="技能矩阵" name="matrix">
          <div class="mx-wrap">
            <table class="mx">
              <thead>
                <tr>
                  <th class="sticky">员工</th>
                  <th v-for="s in matrix.step_types" :key="s.value">{{ s.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in matrix.users" :key="u.user_id">
                  <td class="sticky">{{ u.name || u.username }}</td>
                  <td v-for="s in matrix.step_types" :key="s.value">
                    <span v-if="u.skills[s.value]" :class="['cell', u.skills[s.value]]">
                      {{ levelShort(u.skills[s.value]) }}
                    </span>
                    <span v-else class="cell empty">—</span>
                  </td>
                </tr>
                <tr v-if="!matrix.users.length">
                  <td :colspan="matrix.step_types.length + 1" class="empty-row">
                    还没有任何技能记录，点右上「新增技能」开始录入
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="mx-legend">
            <span><i class="cell junior">初</i>初级</span>
            <span><i class="cell mid">中</i>中级</span>
            <span><i class="cell senior">高</i>高级</span>
          </div>
          <div class="mx-note">
            矩阵由 <code>GET /planning/employee-skills/matrix/</code> 返回，等级排序逻辑在后端，
            与「按工序找合格人员」用同一套口径，避免两处判断不一致。
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑技能' : '新增技能'" width="540px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="员工" prop="user">
          <el-select v-model="form.user" filterable placeholder="选择员工" style="width: 100%">
            <el-option
              v-for="u in userOptions"
              :key="u.id"
              :label="`${u.name || u.username}（${u.username}）`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工序类型" prop="step_type">
          <el-select v-model="form.step_type" placeholder="选择工序" style="width: 100%">
            <el-option v-for="s in stepTypes" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="技能等级">
          <el-select v-model="form.level" style="width: 100%">
            <el-option label="初级" value="junior" />
            <el-option label="中级" value="mid" />
            <el-option label="高级" value="senior" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否持证">
          <el-switch v-model="form.is_certified" />
        </el-form-item>
        <el-form-item label="认证日期">
          <el-date-picker
            v-model="form.certified_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
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
/**
 * 员工技能页（A 负责）。
 *
 * 两个视图：
 *   技能明细 —— 增删改查，一人一工序一条记录
 *   技能矩阵 —— 人员 × 11 种工序 的等级热力表，答辩时一眼能看出"哪道工序没人"
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SearchForm from '@/components/SearchForm.vue'
import BaseTable from '@/components/BaseTable.vue'
import { listUsers } from '@/api/core'
import {
  createSkill,
  deleteSkill,
  listSkills,
  skillMatrix,
  stepTypeOptions,
  updateSkill
} from '@/api/planning'

const tab = ref('list')
const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = ref({})

const stepTypes = ref([])
const userOptions = ref([])
const matrix = ref({ step_types: [], users: [] })

const searchFields = ref([
  { prop: 'search', label: '关键字', type: 'input', placeholder: '员工 / 工序' },
  { prop: 'step_type', label: '工序', type: 'select', options: [], width: '180px' },
  { prop: 'level', label: '等级', type: 'select', width: '140px', options: [
    { value: 'junior', label: '初级' }, { value: 'mid', label: '中级' }, { value: 'senior', label: '高级' }
  ] }
])

const columns = [
  { prop: 'user_name', label: '员工', width: 140 },
  { prop: 'username', label: '登录名', width: 130 },
  { prop: 'step_type_label', label: '工序', width: 130 },
  { prop: 'level', label: '等级', width: 100, slot: 'level' },
  { prop: 'is_certified', label: '持证', width: 100, slot: 'cert' },
  { prop: 'certified_date', label: '认证日期', width: 130 },
  { prop: 'remark', label: '备注' },
  { prop: 'actions', label: '操作', width: 130, slot: 'actions' }
]

function levelTag(lv) {
  return lv === 'senior' ? 'success' : lv === 'mid' ? 'warning' : 'info'
}
function levelShort(lv) {
  return lv === 'senior' ? '高' : lv === 'mid' ? '中' : '初'
}

async function load() {
  loading.value = true
  try {
    const data = await listSkills({ page: page.value, page_size: pageSize.value, ...query.value })
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
  } catch (e) {
    console.error('[EmployeeSkill] 加载失败', e)
  } finally {
    loading.value = false
  }
}

async function loadMatrix() {
  try {
    const data = await skillMatrix()
    matrix.value = data || { step_types: [], users: [] }
  } catch (e) {
    console.error('[EmployeeSkill] 加载矩阵失败', e)
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

// ---------------- 新增 / 编辑 ----------------
const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null,
  user: null,
  step_type: '',
  level: 'mid',
  is_certified: false,
  certified_date: null,
  remark: ''
})

const rules = {
  user: [{ required: true, message: '请选择员工', trigger: 'change' }],
  step_type: [{ required: true, message: '请选择工序类型', trigger: 'change' }]
}

function openCreate() {
  Object.assign(form, {
    id: null,
    user: null,
    step_type: '',
    level: 'mid',
    is_certified: false,
    certified_date: null,
    remark: ''
  })
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    id: row.id,
    user: row.user,
    step_type: row.step_type,
    level: row.level,
    is_certified: row.is_certified,
    certified_date: row.certified_date || null,
    remark: row.remark || ''
  })
  dialogVisible.value = true
}

async function onSave() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload = {
      user: form.user,
      step_type: form.step_type,
      level: form.level,
      is_certified: form.is_certified,
      certified_date: form.certified_date || null,
      remark: form.remark || '',
      is_active: true
    }
    if (form.id) {
      await updateSkill(form.id, payload)
      ElMessage.success('已保存')
    } else {
      await createSkill(payload)
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    await Promise.all([load(), loadMatrix()])
  } catch (e) {
    console.error('[EmployeeSkill] 保存失败', e)
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.user_name} - ${row.step_type_label}」这条技能吗？`, '确认删除',
      { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await deleteSkill(row.id)
    ElMessage.success('已删除')
    await Promise.all([load(), loadMatrix()])
  } catch (e) {
    console.error('[EmployeeSkill] 删除失败', e)
  }
}

onMounted(async () => {
  try {
    const [sts, users] = await Promise.all([stepTypeOptions(), listUsers({ page_size: 200 })])
    stepTypes.value = sts || []
    userOptions.value = (users && users.results) || []
    searchFields.value[1].options = stepTypes.value.map((x) => ({ value: x.value, label: x.label }))
  } catch (e) {
    console.error('[EmployeeSkill] 加载下拉失败', e)
  }
  await Promise.all([load(), loadMatrix()])
})
</script>

<style scoped>
.tip {
  margin: 4px 0 10px;
}
.mx-wrap {
  overflow: auto;
  max-height: 460px;
  border: 1px solid #eef1f5;
  border-radius: 8px;
}
.mx {
  border-collapse: collapse;
  font-size: 12px;
  width: 100%;
}
.mx th,
.mx td {
  border: 1px solid #eef1f5;
  padding: 6px 8px;
  text-align: center;
  white-space: nowrap;
}
.mx thead th {
  background: #162e58;
  color: #fff;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 2;
}
.mx .sticky {
  position: sticky;
  left: 0;
  background: #f7f9fb;
  text-align: left;
  font-weight: 600;
  color: #162e58;
  z-index: 1;
}
.cell {
  display: inline-block;
  min-width: 26px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.cell.junior {
  background: #e8eef5;
  color: #4a5a70;
}
.cell.mid {
  background: #fdf0e2;
  color: #b3651c;
}
.cell.senior {
  background: #e3f6ec;
  color: #1e7a4c;
}
.cell.empty {
  color: #c7d0da;
}
.empty-row {
  color: #9aa7b4;
  padding: 22px;
}
.mx-legend {
  display: flex;
  gap: 18px;
  margin-top: 10px;
  font-size: 12px;
  color: #6b7280;
}
.mx-legend i {
  margin-right: 6px;
  font-style: normal;
}
.mx-note {
  margin-top: 8px;
  font-size: 12px;
  color: #9aa7b4;
  line-height: 1.7;
}
.mx-note code {
  background: #f2f5f9;
  padding: 1px 5px;
  border-radius: 4px;
}
</style>
