<template>
  <div class="sw-page">
    <!-- 顶部：关键数字（全部来自一个聚合接口） -->
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
        <div v-if="network" class="health">
          <div class="hrow">
            <span class="hk">节点 / 边</span>
            <span class="hv">{{ network.node_count }} / {{ network.edge_count }}</span>
          </div>
          <div class="hrow">
            <span class="hk">装卸点 / 单向边</span>
            <span class="hv">{{ network.dock_count }} / {{ network.one_way_edges }}</span>
          </div>
          <div class="hrow">
            <span class="hk">连通性</span>
            <span class="hv">
              <el-tag :type="network.is_connected ? 'success' : 'danger'" size="small" effect="light">
                {{ network.is_connected ? '全连通' : '存在孤立节点' }}
              </el-tag>
              <span v-if="!network.is_connected" class="dim">
                （{{ network.isolated_count }} 个：{{ (network.isolated_nodes || []).join(', ') }}）
              </span>
            </span>
          </div>
          <div class="hrow">
            <span class="hk">距离矩阵</span>
            <span class="hv">
              <el-button link type="primary" @click="$router.push('/logistics/path')">
                {{ network.node_count * network.node_count }} 格，点开路径规划可查
              </el-button>
            </span>
          </div>
        </div>
        <div v-else class="dim">未取到路网数据（可能尚未导入路网）</div>
      </div>

      <!-- 右：七项课程任务 -->
      <div class="sw-card">
        <div class="card-title">
          <span>七项课程任务</span>
          <span class="dim small">已完成 {{ taskDone }} / {{ taskTotal }}</span>
        </div>
        <div class="tasks">
          <div v-for="t in tasks" :key="t.no" class="task">
            <span class="tno">{{ t.no }}</span>
            <span class="tname">{{ t.name }}</span>
            <span class="towner">{{ t.owner }}</span>
            <el-tag :type="t.status === 'done' ? 'success' : 'info'" size="small" effect="light">
              {{ t.status === 'done' ? '已完成' : '未开始' }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 当前账号可见范围（权限演示用） -->
    <div class="sw-card me-card" v-if="me">
      <div class="card-title"><span>当前账号</span></div>
      <div class="me-row">
        <span class="me-name">{{ me.name }}（{{ me.username }}）</span>
        <el-tag v-if="me.is_superuser" type="warning" size="small" effect="light">超级管理员</el-tag>
        <span class="me-item">可见菜单目录 <b>{{ me.menu_dirs }}</b> 个</span>
        <span class="me-item">接口权限码 <b>{{ me.permission_codes }}</b> 个</span>
        <span class="me-hint">
          用 planner / planner123 登录对比：目录只剩 3 个，用户与角色接口返回 403
        </span>
      </div>
    </div>

    <!-- 底部：接口自检 -->
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
 * 数据来源：GET /analytics/dashboard/ —— 一个聚合接口返回全部数字。
 * 为什么不在前端并发发 5 个请求：
 *   首页是答辩第一眼，任何一个请求失败页面就残一块；一个接口要么全成要么全失败，
 *   状态明确、排查容易。实测稳态 8ms。
 */
import { computed, onMounted, ref } from 'vue'
import request from '@/utils/request'
import { demoError, demoPaginated, demoSuccess } from '@/api/core'

const network = ref(null)
const tasks = ref([])
const taskDone = ref(0)
const taskTotal = ref(0)
const me = ref(null)
const lastResult = ref('')

const kpis = ref([
  { label: '产品', value: '—', sub: '主数据', color: '#162E58' },
  { label: '工位', value: '—', sub: '含 AGV 装卸点', color: '#162E58' },
  { label: '设备', value: '—', sub: '台账在册', color: '#0F9DA8' },
  { label: '设备能力', value: '—', sub: '设备 × 工序', color: '#0F9DA8' },
  { label: '员工技能', value: '—', sub: '人 × 工序', color: '#E17B2A' },
  { label: '路网节点', value: '—', sub: '车间点位', color: '#E17B2A' },
  { label: '数据表', value: '46', sub: '已建并迁移', color: '#27AE60' }
])

async function load() {
  try {
    const data = await request.get('/analytics/dashboard/')
    const kpi = (data && data.kpi) || {}
    const put = (i, v) => {
      if (v !== null && v !== undefined) kpis.value[i].value = String(v)
    }
    put(0, kpi.products)
    put(1, kpi.workstations)
    put(2, kpi.equipments)
    put(3, kpi.capabilities)
    put(4, kpi.skills)
    put(5, kpi.road_nodes)

    network.value = (data && data.network) || null
    tasks.value = (data && data.tasks) || []
    taskDone.value = (data && data.task_done) || 0
    taskTotal.value = (data && data.task_total) || 0
    me.value = (data && data.me) || null
  } catch (e) {
    console.error('[Dashboard] 加载聚合数据失败', e)
  }
}

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

onMounted(load)
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
.me-card {
  margin-bottom: 14px;
}
.me-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #4a5a70;
}
.me-name {
  font-weight: 600;
  color: #162e58;
}
.me-item b {
  color: #0f9da8;
  font-size: 15px;
  margin: 0 2px;
}
.me-hint {
  font-size: 12px;
  color: #9aa7b4;
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
