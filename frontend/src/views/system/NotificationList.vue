<template>
  <div class="sw-page">
    <div class="sw-card">
      <div class="bar">
        <div class="left">
          <span class="label">筛选</span>
          <el-radio-group v-model="scope" size="default" @change="reload">
            <el-radio-button label="unread">未读 <b v-if="unread">({{ unread }})</b></el-radio-button>
            <el-radio-button label="all">全部</el-radio-button>
          </el-radio-group>
        </div>
        <div class="right">
          <el-button :disabled="!unread" type="primary" plain @click="onReadAll">
            全部标记已读
          </el-button>
        </div>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="tip"
        title="通知用于派工、设备报警、待检提醒。每个人只看得到自己的通知（超管也一样），通知不是业务数据。"
      />

      <el-empty v-if="!loading && !rows.length" description="没有通知" />

      <div v-else class="list">
        <div v-for="n in rows" :key="n.id" :class="['item', { unread: !n.is_read }]">
          <div class="dot"></div>
          <div class="body">
            <div class="title-row">
              <span class="title">{{ n.title }}</span>
              <el-tag size="small" effect="plain" class="biz">{{ n.biz_type || '系统' }}</el-tag>
              <span class="time">{{ formatTime(n.created_at) }}</span>
            </div>
            <div class="content">{{ n.content || '（无内容）' }}</div>
          </div>
          <div class="ops">
            <el-button v-if="!n.is_read" link type="primary" @click="onRead(n)">标记已读</el-button>
            <span v-else class="done">已读</span>
          </div>
        </div>
      </div>

      <el-pagination
        v-if="total > pageSize"
        class="pager"
        layout="total, prev, pager, next"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        @current-change="onPage"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 通知页（只读 + 标记已读）。
 *
 * 为什么不能新建：通知由业务侧产生（派工、报警、待检），
 * 允许手工新建会让"通知"变成留言板，失去提醒的语义。
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listNotifications,
  markAllRead,
  markRead,
  unreadCount
} from '@/api/core'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const unread = ref(0)
const page = ref(1)
const pageSize = ref(20)
const scope = ref('unread')

function formatTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

async function reload() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (scope.value === 'unread') params.is_read = false
    const data = await listNotifications(params)
    rows.value = (data && data.results) || []
    total.value = (data && data.count) || 0
    const u = await unreadCount()
    unread.value = (u && u.unread) || 0
  } catch (e) {
    console.error('[NotificationList] 加载失败', e)
  } finally {
    loading.value = false
  }
}

async function onRead(n) {
  try {
    await markRead(n.id)
    ElMessage.success('已标记已读')
    await reload()
  } catch (e) {
    console.error('[NotificationList] 标记失败', e)
  }
}

async function onReadAll() {
  try {
    const r = await markAllRead()
    ElMessage.success(`已标记 ${(r && r.updated) || 0} 条为已读`)
    await reload()
  } catch (e) {
    console.error('[NotificationList] 全部标记失败', e)
  }
}

function onPage(p) {
  page.value = p
  reload()
}

onMounted(reload)
</script>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef1f5;
  margin-bottom: 6px;
}
.bar .left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.label {
  font-size: 13px;
  color: #6b7280;
}
.tip {
  margin: 10px 0 14px;
}
.list .item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 6px;
  border-bottom: 1px dashed #f0f3f7;
}
.list .item.unread {
  background: #fbfcfe;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 7px;
  background: #d5dde6;
  flex: 0 0 auto;
}
.item.unread .dot {
  background: #e17b2a;
}
.body {
  flex: 1;
  min-width: 0;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.title {
  font-size: 14px;
  font-weight: 600;
  color: #162e58;
}
.item.unread .title {
  color: #0f172a;
}
.biz {
  font-size: 11px;
}
.time {
  margin-left: auto;
  font-size: 12px;
  color: #9aa7b4;
}
.content {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}
.ops {
  flex: 0 0 auto;
}
.done {
  font-size: 12px;
  color: #b6c0cc;
}
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
