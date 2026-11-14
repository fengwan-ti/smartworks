<template>
  <div class="sw-page">
    <div class="sw-card">
      <div class="pp-head">
        <div>
          <div class="pp-title">车间路网与路径规划</div>
          <div class="pp-sub">
            任务 3 · 给定起终点计算最短路径　｜　路网 29 节点 / 48 边，距离单位毫米
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
        <NodePicker
          v-model="from"
          :options="nodeOptions"
          placeholder="点图上的节点，或在这里选"
          @hover="onPickerHover"
        />

        <span class="pp-label">终点</span>
        <NodePicker
          v-model="to"
          :options="nodeOptions"
          placeholder="点图上的节点，或在这里选"
          @hover="onPickerHover"
        />

        <el-button type="primary" :loading="loading" @click="onPlan">计算最短路径</el-button>
        <el-button @click="onReset">清除</el-button>

        <div class="pp-result" v-if="result">
          <span class="ok">最短距离 <b>{{ (result.distance / 1000).toFixed(2) }}</b> 米</span>
          <span class="dim">经过 {{ result.path.length }} 个节点 · {{ result.path.length - 1 }} 段</span>
        </div>
      </div>

      <div class="pp-hint">
        <span class="dot-mark"></span>
        {{ pickHint }}
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
            :stroke="isPathEdge(e) ? '#E17B2A' : (isHoverEdge(e) ? '#9FD4DA' : '#C9D2DC')"
            :stroke-width="isPathEdge(e) ? 5 : (isHoverEdge(e) ? 3 : 2)"
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

          <!-- 起终点外圈（画在节点下面，避免遮挡） -->
          <circle
            v-if="from"
            :cx="px(from).x"
            :cy="px(from).y"
            :r="radiusOf(from) + 10"
            fill="none"
            stroke="#27AE60"
            stroke-width="3"
          />
          <circle
            v-if="to"
            :cx="px(to).x"
            :cy="px(to).y"
            :r="radiusOf(to) + 10"
            fill="none"
            stroke="#C0392B"
            stroke-width="3"
          />

          <!-- 节点 -->
          <g v-for="n in nodes" :key="n.code" class="node-g">
            <!-- 透明命中区：半径放大，鼠标容易点中 -->
            <circle
              :cx="px(n.code).x"
              :cy="px(n.code).y"
              :r="radiusOf(n.code) + 12"
              fill="transparent"
              class="hit"
              @mouseenter="hoverCode = n.code"
              @mouseleave="hoverCode = ''"
              @click="onNodeClick(n.code)"
            />
            <circle
              :cx="px(n.code).x"
              :cy="px(n.code).y"
              :r="radiusOf(n.code)"
              :fill="fillOf(n)"
              :stroke="isOnPath(n.code) ? '#162E58' : '#fff'"
              :stroke-width="isHovered(n.code) ? 3 : 2"
              pointer-events="none"
            />
            <text
              v-if="n.code === from"
              :x="px(n.code).x"
              :y="px(n.code).y - radiusOf(n.code) - 8"
              text-anchor="middle"
              class="badge-txt"
              fill="#27AE60"
            >起</text>
            <text
              v-if="n.code === to"
              :x="px(n.code).x"
              :y="px(n.code).y - radiusOf(n.code) - 8"
              text-anchor="middle"
              class="badge-txt"
              fill="#C0392B"
            >终</text>
          </g>

          <!-- 悬停标签（最后画，保证在最上层）。靠右的节点自动左翻，避免被画布裁掉 -->
          <g v-if="hoveredNode" class="hover-label" pointer-events="none">
            <rect
              :x="labelPos.rectX"
              :y="labelPos.rectY"
              :width="hoverLabelWidth"
              height="26"
              rx="5"
              fill="#162E58"
              opacity="0.94"
            />
            <text
              :x="labelPos.textX"
              :y="labelPos.textY"
              :text-anchor="labelPos.anchor"
              class="hover-txt"
              fill="#fff"
            >{{ hoveredNode.code }}　{{ hoveredNode.name }}</text>
          </g>
        </svg>

        <div class="pp-legend">
          <span><i class="dot lane"></i>通道</span>
          <span><i class="dot dock"></i>装卸点</span>
          <span><i class="dot charger"></i>充电位</span>
          <span><i class="line-solid"></i>双向</span>
          <span><i class="line-dash"></i>单向</span>
          <span><i class="ring green"></i>起点（标「起」）</span>
          <span><i class="ring red"></i>终点（标「终」）</span>
        </div>
      </div>

      <div class="pp-foot" v-if="result">
        <div class="pp-path">
          <span class="pp-label">路径</span>
          <span class="pp-codes">{{ result.path.join(' → ') }}</span>
        </div>
        <div class="pp-note">
          算法：Dijkstra（单源最短路）。距离为沿路长度，不是两点直线距离。
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
 * 三条交互（都是为了答辩时不用解释就能懂）：
 *   1. 鼠标移到节点：节点放大 1.6 倍 + 右侧弹出「编号 名称」标签 + 相邻边变亮
 *   2. 直接点图上的节点：按「先起点、再终点、然后重来」自动填，提示条实时告诉你下次点击会设成什么
 *   3. 起点/终点选择器里悬停某一行，图上对应节点同样放大 —— 选择器与图双向联动
 *
 * 分工（答辩会问）：
 *   路网数据、导入、距离矩阵接口 → D（apps/logistics）
 *   最短路算法、可视化、交互      → A（apps/algorithms/scheduling/path + 本页）
 *   本页只调接口，不在前端算最短路。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import NodePicker from '@/components/NodePicker.vue'
import { listRoadEdges, listRoadNodes, networkHealth, shortestPath } from '@/api/logistics'

const nodes = ref([])
const edges = ref([])
const health = ref(null)
const from = ref('')
const to = ref('')
const result = ref(null)
const loading = ref(false)

/** 图上悬停的节点 */
const hoverCode = ref('')
/** 选择器里悬停的节点（手在下拉里时鼠标不在图上，所以要单独记） */
const pickerHoverCode = ref('')

function onPickerHover(code) {
  pickerHoverCode.value = code || ''
}

const effectiveHover = computed(() => pickerHoverCode.value || hoverCode.value)

const hoveredNode = computed(() =>
  effectiveHover.value ? nodes.value.find((n) => n.code === effectiveHover.value) : null)

const canvasW = computed(() => {
  const { s: sc, b } = scaleInfo.value
  return (b.x1 - b.x0) * sc + PAD * 2
})

const canvasH = computed(() => {
  const { s: sc, b } = scaleInfo.value
  return (b.y1 - b.y0) * sc + PAD * 2
})

/** 标签位置：默认画在节点右侧；右侧放不下就翻到左侧 */
const labelPos = computed(() => {
  const n = hoveredNode.value
  if (!n) return { rectX: 0, rectY: 0, textX: 0, textY: 0, anchor: 'start' }
  const p = px(n.code)
  const r = radiusOf(n.code)
  const w = hoverLabelWidth.value
  const gap = 8
  const padding = 10
  const rectY = Math.min(Math.max(p.y - 13, 4), canvasH.value - 30)

  if (p.x + r + gap + w > canvasW.value - 4) {
    // 右翻左
    const rectX = Math.max(4, p.x - r - gap - w)
    return {
      rectX,
      rectY,
      textX: rectX + padding,
      textY: p.y + 4,
      anchor: 'start'
    }
  }
  const rectX = p.x + r + gap
  return {
    rectX,
    rectY,
    textX: rectX + padding,
    textY: p.y + 4,
    anchor: 'start'
  }
})

const hoverLabelWidth = computed(() => {
  const n = hoveredNode.value
  if (!n) return 0
  const text = `${n.code}　${n.name}`
  let w = 22
  for (const ch of text) {
    w += /[\u4e00-\u9fa5]/.test(ch) ? 13 : 8
  }
  return w
})

// ---------------- 坐标换算 ----------------
const PAD = 70
const SPAN_W = 1120
const SPAN_H = 540

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

const scaleInfo = computed(() => {
  const b = bounds.value
  const w = b.x1 - b.x0 || 1
  const h = b.y1 - b.y0 || 1
  const s = Math.min((SPAN_W - PAD * 2) / w, (SPAN_H - PAD * 2) / h)
  return { s, b }
})

const viewBox = computed(() => {
  const { s, b } = scaleInfo.value
  const usedW = (b.x1 - b.x0) * s + PAD * 2
  const usedH = (b.y1 - b.y0) * s + PAD * 2
  return `0 0 ${usedW} ${usedH}`
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

/** 悬停时把它相邻的边也提亮，帮助看清这个点连哪几条路 */
function isHoverEdge(e) {
  const h = effectiveHover.value
  if (!h) return false
  return e.from_code === h || e.to_code === h
}

function isHovered(code) {
  return effectiveHover.value === code
}

/** 半径：基准 + 悬停放大 1.6 倍 + 起终点略大 */
function radiusOf(code) {
  const n = nodeMap.value[code]
  const base = !n ? 5 : n.node_type === 'dock' ? 9 : n.node_type === 'charger' ? 8 : 5.5
  let r = base
  if (code === from.value || code === to.value) r = base * 1.25
  if (isHovered(code)) r = base * 1.6 + 2
  return r
}

function fillOf(n) {
  if (isOnPath(n.code)) return '#E17B2A'
  if (isHovered(n.code)) return '#0F9DA8'
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

// ---------------- 点图选点 ----------------
const pickHint = computed(() => {
  if (!from.value && !to.value) {
    return '点击图上的任意节点设为起点（也可以在右上两个选择器里选）'
  }
  if (from.value && !to.value) {
    return `起点已设为 ${from.value}，再点击一个节点设为终点（会自动计算）`
  }
  return `当前 ${from.value} → ${to.value}，再点任意节点将重新从起点开始选`
})

function onNodeClick(code) {
  if (!from.value) {
    from.value = code
    result.value = null
    return
  }
  if (!to.value) {
    if (code === from.value) {
      ElMessage.warning('终点不能与起点相同')
      return
    }
    to.value = code
    result.value = null
    onPlan()
    return
  }
  // 已有一组，重新开始
  from.value = code
  to.value = ''
  result.value = null
}

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
  hoverCode.value = ''
  pickerHoverCode.value = ''
}

onMounted(async () => {
  await load()
  // 默认给一组有演示意义的起终点：原料收发料口 → 成品仓发货口
  const codes = new Set(nodes.value.map((n) => n.code))
  if (codes.has('N004')) from.value = 'N004'
  else if (codes.has('N001')) from.value = 'N001'
  if (codes.has('N029')) to.value = 'N029'
  if (from.value && to.value) onPlan()
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
  padding: 14px 0 8px;
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
.pp-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: #0b7b84;
  background: #f0f8f9;
  border: 1px solid #d8ecee;
  border-radius: 6px;
  padding: 7px 12px;
  margin-bottom: 10px;
}
.dot-mark {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #0f9da8;
  flex: 0 0 auto;
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
  height: 540px;
  display: block;
}
.node-g .hit {
  cursor: pointer;
}
.badge-txt {
  font-size: 12px;
  font-weight: 700;
}
.hover-txt {
  font-size: 12px;
  font-weight: 600;
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
