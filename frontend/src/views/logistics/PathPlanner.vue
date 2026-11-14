<template>
  <div class="sw-page">
    <div class="sw-card">
      <div class="pp-head">
        <div>
          <div class="pp-title">车间路网与路径规划</div>
          <div class="pp-sub">
            任务 3 · 给定起终点计算最短路径　｜　数据来源：路网 29 节点 / 48 边，距离单位毫米
          </div>
        </div>
        <div class="pp-health" v-if="health">
          <span class="hi"><b>{{ health.node_count }}</b> 节点</span>
          <span class="hi"><b>{{ health.edge_count }}</b> 边</span>
          <span class="hi">连通分量 <b>{{ health.components }}</b></span>
          <span class="hi">平均绕行比 <b>{{ health.avg_detour_ratio }}</b></span>
          <span class="hi">矩阵耗时 <b>{{ health.cost_ms }} ms</b></span>
        </div>
      </div>

      <div class="pp-toolbar">
        <span class="pp-label">起点</span>
        <el-select v-model="from" filterable style="width: 240px" placeholder="选择起点">
          <el-option v-for="n in nodeOptions" :key="n.code" :label="`${n.code} ${n.name}`" :value="n.code" />
        </el-select>

        <span class="pp-label">终点</span>
        <el-select v-model="to" filterable style="width: 240px" placeholder="选择终点">
          <el-option v-for="n in nodeOptions" :key="n.code" :label="`${n.code} ${n.name}`" :value="n.code" />
        </el-select>

        <el-button type="primary" :loading="loading" @click="onPlan">计算最短路径</el-button>
        <el-button @click="onReset">清除</el-button>

        <div class="pp-result" v-if="result">
          <span class="ok">最短距离 <b>{{ (result.distance / 1000).toFixed(2) }}</b> 米</span>
          <span class="dim">经过 {{ result.path.length }} 个节点 · {{ result.path.length - 1 }} 段</span>
        </div>
      </div>

      <div class="pp-canvas" v-loading="loading">
        <svg :viewBox="viewBox" class="pp-svg" preserveAspectRatio="xMidYMid meet">
          <!-- 边 -->
          <line
            v-for="(e, i) in edges"
            :key="'e' + i"
            :x1="px(e.from_code).x"
            :y1="px(e.from_code).y"
            :x2="px(e.to_code).x"
            :y2="px(e.to_code).y"
            :stroke="isPathEdge(e) ? '#E17B2A' : '#C9D2DC'"
            :stroke-width="isPathEdge(e) ? 5 : 2"
            :stroke-dasharray="e.is_bidirectional ? '' : '8 6'"
          />
          <!-- 路径高亮 -->
          <polyline
            v-if="pathPoints"
            :points="pathPoints"
            fill="none"
            stroke="#E17B2A"
            stroke-width="7"
            stroke-linejoin="round"
            stroke-linecap="round"
            opacity="0.85"
          />
          <!-- 节点 -->
          <g v-for="n in nodes" :key="n.code">
            <circle
              :cx="px(n.code).x"
              :cy="px(n.code).y"
              :r="radius(n)"
              :fill="fillOf(n)"
              :stroke="isOnPath(n.code) ? '#162E58' : '#fff'"
              stroke-width="2"
            />
            <title>{{ n.code }} {{ n.name }}</title>
          </g>
          <!-- 起终点标签 -->
          <g v-if="from">
            <circle :cx="px(from).x" :cy="px(from).y" r="13" fill="none" stroke="#27AE60" stroke-width="3" />
          </g>
          <g v-if="to">
            <circle :cx="px(to).x" :cy="px(to).y" r="13" fill="none" stroke="#C0392B" stroke-width="3" />
          </g>
        </svg>

        <div class="pp-legend">
          <span><i class="dot lane"></i>通道</span>
          <span><i class="dot dock"></i>装卸点</span>
          <span><i class="dot charger"></i>充电位</span>
          <span><i class="line-solid"></i>双向</span>
          <span><i class="line-dash"></i>单向</span>
          <span><i class="ring green"></i>起点</span>
          <span><i class="ring red"></i>终点</span>
        </div>
      </div>

      <div class="pp-foot" v-if="result">
        <div class="pp-path">
          <span class="pp-label">路径</span>
          <span class="pp-codes">{{ result.path.join(' → ') }}</span>
        </div>
        <div class="pp-note">
          算法：Dijkstra（单源最短路）。距离为**沿路长度**，不是两点直线距离。
          不可达时后端返回空路径，前端不做兜底推断。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 任务 3 路径规划演示页。
 *
 * 分工说明（答辩时会被问）：
 *   路网数据、导入、距离矩阵接口  → D（apps/logistics）
 *   最短路算法、可视化、交互       → A（apps/algorithms/scheduling/path + 本页）
 * 本页只调用后端接口，不在前端算最短路。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import BaseTable from '@/components/BaseTable.vue'
import { listRoadEdges, listRoadNodes, networkHealth, shortestPath } from '@/api/logistics'

const nodes = ref([])
const edges = ref([])
const health = ref(null)
const from = ref('')
const to = ref('')
const result = ref(null)
const loading = ref(false)

// ---------------- 坐标换算 ----------------
const PAD = 60
const SPAN_W = 1080
const SPAN_H = 520

const bounds = computed(() => {
  if (!nodes.value.length) return { x0: 0, x1: 1, y0: 0, y1: 1 }
  const xs = nodes.value.map((n) => n.x)
  const ys = nodes.value.map((n) => n.y)
  return {
    x0: Math.min(...xs),
    x1: Math.max(...xs),
    y0: Math.min(...ys),
    y1: Math.max(...ys)
  }
})

const viewBox = computed(() => {
  const b = bounds.value
  const w = b.x1 - b.x0 || 1
  const h = b.y1 - b.y0 || 1
  // 保持等比，避免路网被拉扁
  const scale = Math.min((SPAN_W - PAD * 2) / w, (SPAN_H - PAD * 2) / h)
  const usedW = w * scale + PAD * 2
  const usedH = h * scale + PAD * 2
  return `${0} ${0} ${usedW} ${usedH}`
})

const scaleInfo = computed(() => {
  const b = bounds.value
  const w = b.x1 - b.x0 || 1
  const h = b.y1 - b.y0 || 1
  const s = Math.min((SPAN_W - PAD * 2) / w, (SPAN_H - PAD * 2) / h)
  return { s, b }
})

const nodeMap = computed(() => {
  const m = {}
  nodes.value.forEach((n) => {
    m[n.code] = n
  })
  return m
})

function px(code) {
  const n = nodeMap.value[code]
  if (!n) return { x: 0, y: 0 }
  const { s, b } = scaleInfo.value
  // 路网 y 轴向北为正，SVG y 向下为正 → 翻转
  return {
    x: PAD + (n.x - b.x0) * s,
    y: PAD + (b.y1 - n.y) * s
  }
}

// ---------------- 渲染辅助 ----------------
const nodeOptions = computed(() =>
  [...nodes.value].sort((a, b) => {
    // 装卸点排前面，演示时好找
    const rank = (n) => (n.node_type === 'dock' ? 0 : n.node_type === 'charger' ? 1 : 2)
    return rank(a) - rank(b) || a.code.localeCompare(b.code)
  })
)

const pathSet = computed(() => new Set(result.value ? result.value.path : []))
const pathPairs = computed(() => {
  const s = new Set()
  if (!result.value) return s
  const p = result.value.path
  for (let i = 0; i < p.length - 1; i += 1) {
    s.add(p[i] + '|' + p[i + 1])
    s.add(p[i + 1] + '|' + p[i])
  }
  return s
})

function isOnPath(code) {
  return pathSet.value.has(code)
}

function isPathEdge(e) {
  return pathPairs.value.has(e.from_code + '|' + e.to_code)
}

function radius(n) {
  if (n.node_type === 'dock') return 9
  if (n.node_type === 'charger') return 8
  return 5.5
}

function fillOf(n) {
  if (isOnPath(n.code)) return '#E17B2A'
  if (n.node_type === 'dock') return '#0F9DA8'
  if (n.node_type === 'charger') return '#27AE60'
  return '#9AA7B4'
}

const pathPoints = computed(() => {
  if (!result.value) return ''
  return result.value.path
    .map((c) => {
      const p = px(c)
      return `${p.x},${p.y}`
    })
    .join(' ')
})

// ---------------- 数据与操作 ----------------
async function load() {
  loading.value = true
  try {
    const [nodePage, edgePage, h] = await Promise.all([
      listRoadNodes(),
      listRoadEdges(),
      networkHealth()
    ])
    nodes.value = nodePage.results || []
    edges.value = edgePage.results || []
    health.value = h
  } catch (e) {
    console.error('[PathPlanner] 加载路网失败', e)
  } finally {
    loading.value = false
  }
}

async function onPlan() {
  if (!from.value || !to.value) {
    ElMessage.warning('请先选择起点和终点')
    return
  }
  if (from.value === to.value) {
    ElMessage.warning('起点与终点相同')
    return
  }
  loading.value = true
  try {
    const data = await shortestPath(from.value, to.value)
    if (!data || !data.path || !data.path.length) {
      ElMessage.error('两点之间不可达')
      result.value = null
    } else {
      result.value = data
    }
  } catch (e) {
    console.error('[PathPlanner] 计算失败', e)
  } finally {
    loading.value = false
  }
}

function onReset() {
  from.value = ''
  to.value = ''
  result.value = null
}

onMounted(async () => {
  await load()
  // 默认给一组有演示意义的起终点：原料仓 → 成品仓
  const codes = new Set(nodes.value.map((n) => n.code))
  if (codes.has('N004')) from.value = 'N004'
  else if (codes.has('N001')) from.value = 'N001'
  if (codes.has('N029')) to.value = 'N029'
})
</script>

<style scoped>
.pp-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef1f5;
}
.pp-title {
  font-size: 18px;
  font-weight: 700;
  color: #162e58;
}
.pp-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}
.pp-health {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #6b7280;
}
.pp-health b {
  color: #162e58;
  font-size: 14px;
}
.pp-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 14px 0 10px;
}
.pp-label {
  font-size: 13px;
  color: #6b7280;
}
.pp-result {
  margin-left: auto;
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.pp-result .ok {
  font-size: 14px;
  color: #162e58;
}
.pp-result .ok b {
  font-size: 22px;
  color: #e17b2a;
  margin: 0 2px;
}
.pp-result .dim {
  font-size: 12px;
  color: #6b7280;
}
.pp-canvas {
  position: relative;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  background: #fbfcfd;
  padding: 6px;
}
.pp-svg {
  width: 100%;
  height: 520px;
  display: block;
}
.pp-legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  padding: 8px 12px 4px;
  font-size: 12px;
  color: #6b7280;
}
.pp-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.dot.lane {
  background: #9aa7b4;
}
.dot.dock {
  background: #0f9da8;
}
.dot.charger {
  background: #27ae60;
}
.line-solid,
.line-dash {
  width: 22px;
  height: 0;
  border-top: 2px solid #c9d2dc;
  display: inline-block;
}
.line-dash {
  border-top-style: dashed;
}
.ring {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 3px solid;
  display: inline-block;
}
.ring.green {
  border-color: #27ae60;
}
.ring.red {
  border-color: #c0392b;
}
.pp-foot {
  padding-top: 12px;
}
.pp-path {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.pp-codes {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  color: #162e58;
  word-break: break-all;
}
.pp-note {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.7;
}
</style>
