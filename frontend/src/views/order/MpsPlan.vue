<template>
  <div class="o-page">
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <div>
            <div class="title">主生产计划 MPS</div>
            <div class="sub">由已确认销售订单聚合生成；齐套检查按生效 BOM 展开到物料（库存接口未接入时按 0 计算）</div>
          </div>
          <div class="actions">
            <el-date-picker v-model="period" type="date" value-format="YYYY-MM-DD" placeholder="计划期" style="width: 150px" />
            <el-button type="primary" @click="generate">从已确认订单生成</el-button>
            <el-button @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="rows" border stripe highlight-current-row @current-change="selectMps">
        <el-table-column prop="code" label="MPS 编码" width="160" />
        <el-table-column prop="period" label="计划期" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="items_count" label="明细数" width="90" align="center" />
        <el-table-column prop="remark" label="备注" min-width="160" />
        <el-table-column prop="created_at" label="生成时间" width="170" />
      </el-table>

      <template v-if="current">
        <el-divider content-position="left">{{ current.code }} 明细</el-divider>
        <el-table :data="current.items || []" border size="small">
          <el-table-column prop="product_code" label="产品编码" width="130" />
          <el-table-column prop="product_name" label="产品" width="130" />
          <el-table-column prop="qty" label="计划数量" align="right" width="120" />
          <el-table-column prop="source" label="来源" width="100" />
        </el-table>
        <div class="kit-bar">
          <el-button type="warning" :loading="checking" @click="checkKit">齐套检查</el-button>
          <span v-if="kitResult" class="kit-source">{{ kitResult.availability_source }}</span>
        </div>

        <template v-if="kitResult">
          <el-alert
            :type="kitResult.ready ? 'success' : 'error'"
            :title="kitResult.ready ? '物料齐套，可以排产' : '存在缺口，排产前需补料'"
            :closable="false" show-icon style="margin-bottom: 10px"
          />
          <el-table :data="kitResult.items || []" border size="small">
            <el-table-column prop="material_code" label="物料编码" width="130" />
            <el-table-column prop="material_name" label="物料" width="140" />
            <el-table-column prop="required_qty" label="需求" align="right" />
            <el-table-column prop="available_qty" label="可用" align="right" />
            <el-table-column label="缺口" align="right">
              <template #default="{ row }">
                <span :class="{ danger: Number(row.shortage_qty) > 0 }">{{ row.shortage_qty }}</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { checkKit as runKitCheck, fetchMpsList, mpsFromOrders } from '@/api/order'

const loading = ref(false)
const checking = ref(false)
const rows = ref([])
const current = ref(null)
const kitResult = ref(null)
const period = ref(new Date().toISOString().slice(0, 10))

async function load() {
  loading.value = true
  try {
    const data = await fetchMpsList({ page: 1, page_size: 50 })
    rows.value = data.results || []
    if (!current.value || !rows.value.some((r) => r.id === current.value.id)) {
      current.value = null
      kitResult.value = null
    }
  } finally { loading.value = false }
}

async function generate() {
  if (!period.value) { ElMessage.warning('请选择计划期'); return }
  try {
    const mps = await mpsFromOrders({ period: period.value })
    ElMessage.success(`已生成 ${mps.code}`)
    await load()
    current.value = mps
  } catch (e) {
    // 错误提示由 request.js 统一处理
  }
}

function selectMps(row) {
  current.value = row
  kitResult.value = null
}

async function checkKit() {
  if (!current.value) { ElMessage.warning('先选一条 MPS'); return }
  checking.value = true
  try {
    kitResult.value = await runKitCheck(current.value.id)
  } finally { checking.value = false }
}

onMounted(load)
</script>

<style scoped>
.o-page { padding: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 16px; font-weight: 600; color: var(--sw-primary); }
.sub { font-size: 12px; color: #8a8f99; margin-top: 4px; }
.actions { display: flex; gap: 8px; align-items: center; }
.kit-bar { margin: 12px 0; display: flex; gap: 12px; align-items: center; }
.kit-source { font-size: 12px; color: #e6a23c; }
.danger { color: #f56c6c; font-weight: 600; }
</style>
