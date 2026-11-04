<template>
  <div class="mobile-page">
    <div class="m-header">
      <span class="m-title">扫码报工</span>
      <span class="m-user">{{ userStore.user?.username || '未登录' }}</span>
    </div>

    <div class="m-card">
      <div class="m-field">
        <label>工单ID</label>
        <el-input v-model="workOrderId" size="large" inputmode="numeric" placeholder="扫码或输入" />
      </div>
      <div class="m-field">
        <label>工序序号</label>
        <el-input-number v-model="seq" size="large" :min="1" style="width: 100%" />
      </div>
      <div class="m-status">
        <el-tag :type="started ? 'success' : 'info'" size="large">
          {{ started ? '工序进行中' : '未开工' }}
        </el-tag>
        <span v-if="startTime" class="m-time">开工：{{ startTime }}</span>
      </div>
    </div>

    <div class="m-actions">
      <el-button type="primary" size="large" class="m-btn" :disabled="started" :loading="acting"
        @click="onStart">开工</el-button>
      <el-button type="warning" size="large" class="m-btn" :disabled="!started" :loading="acting"
        @click="onComplete">完工</el-button>
    </div>

    <div v-if="started" class="m-card">
      <div class="m-field">
        <label>合格数</label>
        <el-input-number v-model="goodQty" size="large" :min="0" :precision="0" style="width: 100%" />
      </div>
      <div class="m-field">
        <label>不良数</label>
        <el-input-number v-model="defectQty" size="large" :min="0" :precision="0" style="width: 100%" />
      </div>
      <el-button type="success" size="large" class="m-btn full" :loading="submitting" @click="onReport">
        提交报工
      </el-button>
    </div>

    <el-alert type="info" :closable="false" title="完工/报工时间自动取服务器时间，作为 B 换型 K2 的计时起点" />
  </div>
</template>

<script setup>
/**
 * 手机端扫码报工页。桌面路由也会挂，样式按 375px 宽度设计。
 * 流程：开工（operation_start，记 start_time）→ 完工 → 提交报工。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { operationComplete, operationStart, createReport } from '@/api/production'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const workOrderId = ref('')
const seq = ref(1)
const started = ref(false)
const startTime = ref('')
const acting = ref(false)
const submitting = ref(false)
const goodQty = ref(0)
const defectQty = ref(0)

function checkInput() {
  if (!workOrderId.value) {
    ElMessage.warning('请先输入工单ID')
    return false
  }
  return true
}

async function onStart() {
  if (!checkInput()) return
  acting.value = true
  try {
    const data = await operationStart(workOrderId.value, seq.value, {})
    startTime.value = data?.start_time || new Date().toLocaleString()
    started.value = true
    ElMessage.success('已开工')
  } finally {
    acting.value = false
  }
}

async function onComplete() {
  if (!checkInput()) return
  acting.value = true
  try {
    await operationComplete(workOrderId.value, seq.value, {})
    ElMessage.success('已完工，请填写数量并提交报工')
  } finally {
    acting.value = false
  }
}

async function onReport() {
  if (goodQty.value + defectQty.value <= 0) {
    ElMessage.warning('合格数+不良数必须大于 0')
    return
  }
  submitting.value = true
  try {
    await createReport({
      work_order_id: Number(workOrderId.value),
      operation_seq: seq.value,
      step_type: 'inspection', // 手机端快捷报工默认按报检工序，可在桌面端补改
      batch_no: `PC-${Date.now()}`,
      good_qty: goodQty.value,
      defect_qty: defectQty.value
    })
    ElMessage.success('报工成功')
    started.value = false
    startTime.value = ''
    goodQty.value = 0
    defectQty.value = 0
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.mobile-page {
  max-width: 420px;
  margin: 0 auto;
  padding: 16px;
}
.m-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.m-title {
  font-size: 20px;
  font-weight: 700;
}
.m-user {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.m-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgb(0 0 0 / 8%);
}
.m-field {
  margin-bottom: 14px;
}
.m-field label {
  display: block;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.m-status {
  display: flex;
  align-items: center;
  gap: 12px;
}
.m-time {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.m-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.m-btn {
  flex: 1;
  height: 56px;
  font-size: 17px;
  border-radius: 10px;
}
.m-btn.full {
  width: 100%;
}
</style>
