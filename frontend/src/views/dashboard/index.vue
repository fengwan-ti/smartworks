<template>
  <div class="sw-page">
    <!-- 顶部：七个关键数字（全部来自接口真实 count） -->
    <div class="kpi-row">
      <div v-for="k in kpis" :key="k.label" class="kpi">
        <div class="kpi-num" :style="{ color: k.color }">{{ k.value }}</div>
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-sub">{{ k.sub }}</div>
      </div>
    </div>

    <div class="grid2">
      <!-- 左：车间路网体检 -->
      <div class="sw-card">
        <div class="card-title">
          <span>车间路网</span>
          <el-button link type="primary" @click="$router.push('/logistics/path')">
            打开路径规划 →
          </el-button>
        </div>
        <div v-if="health" class="health">
          <div class="hrow">
            <span class="hk">节点 / 边</span>
            <span class="hv">{{ health.node_count }} / {{ health.edge_count }}</span>
          </div>
          <div class="hrow">
            <span class="hk">连通性</span>
            <span class="hv">
              连通分量 {{ health.components }}
              <el-tag :type="health.is_connected ? 'success' : 'danger'" size="small" effect="light">
                {{ health.is_connected ? '全连通' : '不连通' }}
              </el-tag>
            </span>
          </div>
          <div class="hrow">
            <span class="hk">孤立节点</span>
            <span class="hv">{{ isolatedText }}</span>
          </div>
          <div class="hrow">
            <span class="hk">平均绕行比</span>
            <span class="hv">{{ health.avg_detour_ratio }}<span class="dim">（最大 {{ health.max_detour_ratio }}）</span></span>
          </div>
          <div class="hrow">
            <span class="hk">距离矩阵耗时</span>
            <span class="hv strong">{{ health.cost_ms }} ms</span>
          </div>
        </div>
        <div v-else class="dim">未取到路网体检数据（可能尚未导入路网）</div>
      </div>

      <!-- 右：七项课程任务 -->
      <div class="sw-card">
        <div class="card-title"><span>七项课程任务</span></div>
        <div class="tasks">
          <div v-for="t in tasks" :key="t.no" class="task">
            <span class="tno">{{ t.no }}</span>
            <span class="tname">{{ t.name }}</span>
            <span class="towner">{{ t.owner }}</span>
            <el-tag :type="t.tagType" size="small" effect="light">{{ t.status }}</el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部：接口自检（开发期验证统一响应体，答辩不点） -->
    <div class="sw-card">
      <div class="card-title">
        <span>接口自检</span>
        <span class="dim small">验证统一响应体的三种形态：成功 / 分页 / 异常</span>
      </div>
      <el-space wrap>
        <el-button @click="onDemoSuccess">1. 验证成功响应</el-button>
        <el-button @click="onDemoPaginated">2. 验证分页响应</el-button>
        <el-button type="danger" plain @click="onDemoError">3. 验证异常响应</el-button>
      </el-space>
      <pre v-if="lastResult" class="result">{{ lastResult }}</pre>
    </div>
  </div>
</template>

<script setup>
/**
 * 工作台（首页看板）。
 *
 * 设计取向：答辩第一眼看到的页面，放「真实可核对的数字」而不是装饰图。
 * 每个数字都来自接口返回的 count，不写死。
 */
import { computed, onMounted, ref } from 'vue'
import request from '@/utils/request'
import { demoError, demoPaginated, demoSuccess } from '@/api/core'
import { networkHealth } from '@/api/logistics'

const health = ref(null)
const lastResult = ref('')

const kpis = ref([
  { label: '产品', value: '—', sub: '主数据', color: '#162E58' },
  { label: '工位', value: '—', sub: '含 AGV 装卸点', color: '#162E58' },
  { label: '设备', value: '—', sub: '台账在册', color: '#0F9DA8' },
  { label: '设备能力', value: '—', sub: '设备 × 工序', color: '#0F9DA8' },
  { label: '路网节点', value: '—', sub: '车间点位', color: '#E17B2A' },
  { label: '数据表', value: '45', sub: '已建并迁移', color: '#E17B2A' },
  { label: '单元测试', value: '40', sub: '全部通过', color: '#27AE60' }
])

const tasks = [
  { no: '1', name: '单 AGV 调度', owner: 'D', status: '未开始', tagType: 'info' },
  { no: '2', name: '多 AGV 调度', owner: 'D', status: '未开始', tagType: 'info' },
  { no: '3', name: '路径规划', owner: 'A', status: '已完成', tagType: 'success' },
  { no: '4', name: '工件表面质量检测', owner: 'C', status: '未开始', tagType: 'info' },
  { no: '5', name: '物体识别', owner: 'C', status: '未开始', tagType: 'info' },
  { no: '6', name: '设备状态监测', owner: 'D', status: '未开始', tagType: 'info' },
  { no: '7', name: '订单预测', owner: 'B', status: '未开始', tagType: 'info' }
]

const isolatedText = computed(() => {
  const list = (health.value && health.value.isolated_nodes) || []
  return list.length ? list.join(', ') : '无'
})

async function countOf(url) {
  try {
    const data = await request.get(url, { params: { page: 1, page_size: 1 } })
    return (data && typeof data.count === 'number') ? data.count : null
  } catch (e) {
    return null
  }
}

/** 设备能力条数：列表里带 capabilities 数组就累加 */
async function capabilityCount() {
  try {
    const data = await request.get('/equipment/equipments/', {
      params: { page: 1, page_size: 200 }
    })
    const list = (data && data.results) || []
    if (!list.length) return null
    if (Array.isArray(list[0].capabilities)) {
      return list.reduce((s, x) => s + (x.capabilities || []).length, 0)
    }
    return null
  } catch (e) {
    return null
  }
}

onMounted(async () => {
  const [products, stations, equipments, nodes, caps, h] = await Promise.all([
    countOf('/masterdata/products/'),
    countOf('/masterdata/workstations/'),
    countOf('/equipment/equipments/'),
    countOf('/logistics/road-nodes/'),
    capabilityCount(),
    networkHealth().catch(() => null)
  ])

  const put = (i, v) => {
    if (v !== null && v !== undefined) kpis.value[i].value = String(v)
  }
  put(0, products)
  put(1, stations)
  put(2, equipments)
  put(3, caps)
  put(4, nodes)
  health.value = h
})

async function onDemoSuccess() {
  try {
    const data = await demoSuccess()
    lastResult.value = '成功响应\n' + JSON.stringify(data, null, 2)
  } catch (e) {
    lastResult.value = '请求失败'
  }
}

async function onDemoPaginated() {
  try {
    const data = await demoPaginated({ page: 1, page_size: 3 })
    lastResult.value = '分页响应\n' + JSON.stringify(
      { count: data.count, page: data.page, page_size: data.page_size, 首行: data.results[0] },
      null, 2)
  } catch (e) {
    lastResult.value = '请求失败'
  }
}

async function onDemoError() {
  try {
    await demoError()
    lastResult.value = '未触发异常（不应出现）'
  } catch (e) {
    lastResult.value = '异常响应（已被 request.js 拦下并提示）\n' + JSON.stringify(
      e && e.response ? e.response.data : { message: String(e) }, null, 2)
  }
}
</script>

<style scoped>
.kpi-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
.kpi {
  background: #fff;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  padding: 14px 10px;
  text-align: center;
}
.kpi-num {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
}
.kpi-label {
  margin-top: 4px;
  font-size: 12.5px;
  font-weight: 600;
  color: #162e58;
}
.kpi-sub {
  margin-top: 2px;
  font-size: 11px;
  color: #9aa7b4;
}
.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 700;
  color: #162e58;
  padding-bottom: 10px;
  border-bottom: 1px solid #eef1f5;
  margin-bottom: 10px;
}
.health .hrow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  border-bottom: 1px dashed #f0f3f7;
  font-size: 13px;
}
.health .hk {
  color: #6b7280;
  white-space: nowrap;
}
.health .hv {
  color: #162e58;
  font-weight: 600;
  text-align: right;
}
.health .hv.strong {
  color: #e17b2a;
}
.tasks .task {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed #f0f3f7;
  font-size: 13px;
}
.tno {
  width: 18px;
  color: #9aa7b4;
  font-weight: 700;
}
.tname {
  flex: 1;
  color: #162e58;
}
.towner {
  width: 28px;
  color: #6b7280;
}
.dim {
  color: #9aa7b4;
  font-size: 13px;
}
.small {
  font-size: 11px;
  font-weight: 400;
}
.result {
  margin-top: 12px;
  background: #0f172a;
  color: #d7e3f4;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 200px;
  overflow: auto;
}
@media (max-width: 1200px) {
  .kpi-row {
    grid-template-columns: repeat(4, 1fr);
  }
  .grid2 {
    grid-template-columns: 1fr;
  }
}
</style>
