<template>
  <div class="sw-page">
    <div class="sw-card">
      <div class="vw-toolbar">
        <el-radio-group v-model="mode">
          <el-radio-button value="detect">缺陷检测（任务4）</el-radio-button>
          <el-radio-button value="recognize">物体识别（任务5）</el-radio-button>
        </el-radio-group>
        <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" :on-change="onPickFile">
          <el-button type="primary">选择图片</el-button>
        </el-upload>
        <el-button type="success" :loading="loading" :disabled="!file" @click="onRun">
          {{ mode === 'detect' ? '开始检测' : '开始识别' }}
        </el-button>
        <span v-if="elapsed" class="elapsed">耗时 {{ elapsed }} ms</span>
      </div>
      <el-alert type="info" :closable="false" style="margin-top: 10px"
        title="支持 NEU-DET 六类表面缺陷：crazing / inclusion / patches / pitted_surface / rolled-in_scale / scratches" />
    </div>

    <div class="vw-body">
      <div class="sw-card vw-canvas-card">
        <h5 class="block-title">图片与结果叠加</h5>
        <canvas ref="canvasRef" class="vw-canvas" />
        <div v-if="!file" class="vw-empty">尚未选择图片</div>
      </div>

      <div class="sw-card vw-result-card">
        <h5 class="block-title">结果</h5>
        <template v-if="mode === 'detect' && result">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="判定">{{ result.is_defect ? '存在缺陷' : '正常' }}</el-descriptions-item>
            <el-descriptions-item label="缺陷框数">{{ result.boxes?.length ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="面积阈值">{{ result.params?.area_threshold ?? '—' }}</el-descriptions-item>
          </el-descriptions>
        </template>
        <template v-else-if="mode === 'recognize' && result">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="目标数">{{ result.targets?.length ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="mean IoU">{{ result.mean_iou ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="耗时">{{ result.elapsed_ms ?? '—' }} ms</el-descriptions-item>
          </el-descriptions>
        </template>
        <el-empty v-else description="先选图再点击运行" :image-size="60" />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 视觉工作台 —— 任务4 /vision/detect/、任务5 /vision/recognize/（multipart）。
 * 结果框直接画在 canvas 上：检测画缺陷外接框，识别画预测框+类别。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { visionDetect, visionRecognize } from '@/api/quality'

const COLORS = ['#f56c6c', '#e6a23c', '#67c23a', '#409eff', '#909399', '#b37feb']

const mode = ref('detect')
const file = ref(null)
const loading = ref(false)
const result = ref(null)
const elapsed = ref('')
const canvasRef = ref()
const imgEl = ref(null)

function onPickFile(uploadFile) {
  file.value = uploadFile.raw
  result.value = null
  elapsed.value = ''
  const url = URL.createObjectURL(file.value)
  const img = new Image()
  img.onload = () => {
    imgEl.value = img
    drawBase(img)
  }
  img.src = url
}

function drawBase(img) {
  const canvas = canvasRef.value
  if (!canvas) return
  canvas.width = img.width
  canvas.height = img.height
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, 0, 0)
}

function drawBoxes(boxes) {
  const canvas = canvasRef.value
  const img = imgEl.value
  if (!canvas || !img) return
  drawBase(img)
  const ctx = canvas.getContext('2d')
  ctx.lineWidth = 2
  ctx.font = '12px sans-serif'
  ;(boxes || []).forEach((b, i) => {
    const color = COLORS[i % COLORS.length]
    ctx.strokeStyle = color
    const [x1, y1, x2, y2] = [b.x1 ?? b[0], b.y1 ?? b[1], b.x2 ?? b[2], b.y2 ?? b[3]]
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
    if (b.label || b.class_name) {
      ctx.fillStyle = color
      ctx.fillText(b.label || b.class_name, x1, Math.max(y1 - 4, 12))
    }
  })
}

async function onRun() {
  if (!file.value) return
  loading.value = true
  const fd = new FormData()
  fd.append('image', file.value)
  try {
    const t0 = performance.now()
    result.value = mode.value === 'detect'
      ? await visionDetect(fd)
      : await visionRecognize(fd)
    elapsed.value = Math.round(performance.now() - t0)
    const boxes = mode.value === 'detect' ? result.value.boxes : result.value.targets
    drawBoxes(boxes)
    ElMessage.success('完成')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.vw-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}
.elapsed {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.vw-body {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  align-items: flex-start;
}
.vw-canvas-card {
  flex: 1;
}
.vw-result-card {
  width: 320px;
  flex-shrink: 0;
}
.vw-canvas {
  max-width: 100%;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.vw-empty {
  padding: 60px 0;
  text-align: center;
  color: var(--el-text-color-placeholder);
}
.block-title {
  margin: 0 0 10px;
  font-size: 14px;
}
</style>
