<template>
  <div class="sw-page">
    <div class="sw-card">
      <el-alert type="info" :closable="false" style="margin-bottom: 12px"
        title="逆向：成品批次 → 报工 → 领料单 → 原料批次；正向：原料批次 → 领料 → 报工 → 成品批次" />
      <div class="trace-bar">
        <el-radio-group v-model="direction">
          <el-radio-button value="reverse">逆向追溯</el-radio-button>
          <el-radio-button value="forward">正向追溯</el-radio-button>
        </el-radio-group>
        <el-input v-model="batchNo" placeholder="输入批次号" style="width: 260px" @keyup.enter="onTrace" />
        <el-button type="primary" :loading="loading" @click="onTrace">追溯</el-button>
      </div>
    </div>

    <div v-if="result" class="sw-card">
      <h4 class="block-title">批次 {{ result.batch_no }}</h4>

      <!-- 逆向：报工链 -->
      <template v-if="direction === 'reverse'">
        <h5 class="block-title">① 生产报工</h5>
        <el-table :data="result.reports" border size="small" style="margin-bottom: 16px">
          <el-table-column prop="code" label="报工单号" width="150" />
          <el-table-column prop="operation_seq" label="工序" width="70" />
          <el-table-column prop="good_qty" label="合格数" width="90" />
          <el-table-column prop="defect_qty" label="不良数" width="90" />
          <el-table-column prop="end_time" label="完工时间" />
        </el-table>
        <h5 class="block-title">② 领料消耗的原料批次</h5>
        <el-table :data="result.material_batches" border size="small">
          <el-table-column prop="outbound_code" label="领料单号" width="150" />
          <el-table-column prop="work_order_id" label="工单" width="80" />
          <el-table-column prop="material_name" label="物料" />
          <el-table-column prop="batch_no" label="原料批次" width="140" />
          <el-table-column prop="qty" label="数量" width="100" />
        </el-table>
      </template>

      <!-- 正向 -->
      <template v-else>
        <h5 class="block-title">① 被领用的领料单</h5>
        <el-table :data="outboundRows" border size="small" style="margin-bottom: 16px">
          <el-table-column prop="code" label="领料单号" />
        </el-table>
        <h5 class="block-title">② 生产报工</h5>
        <el-table :data="result.reports" border size="small" style="margin-bottom: 16px">
          <el-table-column prop="code" label="报工单号" width="150" />
          <el-table-column prop="work_order_id" label="工单" width="80" />
          <el-table-column prop="operation_seq" label="工序" width="70" />
        </el-table>
        <h5 class="block-title">③ 产出的成品批次</h5>
        <el-table :data="result.product_batches" border size="small">
          <el-table-column prop="batch_no" label="成品批次" width="150" />
          <el-table-column prop="work_order_id" label="工单" width="80" />
          <el-table-column prop="report_code" label="报工单号" width="150" />
          <el-table-column prop="good_qty" label="合格数" width="100" />
        </el-table>
      </template>
    </div>
  </div>
</template>

<script setup>
/** 批次追溯 —— 契约 94/95：traceability/reverse|forward。 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { traceForward, traceReverse } from '@/api/production'

const direction = ref('reverse')
const batchNo = ref('')
const loading = ref(false)
const result = ref(null)

const outboundRows = computed(() =>
  (result.value?.outbound_codes || []).map((code) => ({ code }))
)

async function onTrace() {
  if (!batchNo.value.trim()) {
    ElMessage.warning('请输入批次号')
    return
  }
  loading.value = true
  try {
    const params = { batch_no: batchNo.value.trim() }
    result.value = direction.value === 'reverse'
      ? await traceReverse(params)
      : await traceForward(params)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.trace-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}
.block-title {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--el-text-color-primary);
}
h4.block-title {
  margin-bottom: 16px;
}
</style>
