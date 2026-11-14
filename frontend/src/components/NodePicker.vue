<template>
  <el-popover
    v-model:visible="visible"
    placement="bottom-start"
    :width="340"
    trigger="click"
    :teleported="true"
    popper-class="np-popper"
  >
    <template #reference>
      <div :class="['np-trigger', { 'is-empty': !current }]">
        <span v-if="current" class="np-code">{{ current.code }}</span>
        <span v-if="current" class="np-name">{{ current.name }}</span>
        <span v-else class="np-ph">{{ placeholder }}</span>
        <span class="np-arrow">▾</span>
      </div>
    </template>

    <div class="np-panel">
      <el-input
        v-model="keyword"
        size="small"
        placeholder="搜索节点编号或名称"
        clearable
        class="np-search"
      />
      <div class="np-list" @mouseleave="emitHover('')">
        <div
          v-for="n in filtered"
          :key="n.code"
          :class="['np-item', { 'is-active': n.code === modelValue }]"
          @mouseenter="emitHover(n.code)"
          @click="pick(n.code)"
        >
          <span class="np-code">{{ n.code }}</span>
          <span class="np-name">{{ n.name }}</span>
          <span :class="['np-type', n.node_type]">{{ typeLabel(n.node_type) }}</span>
        </div>
        <div v-if="!filtered.length" class="np-empty">没有匹配的节点</div>
      </div>
      <div class="np-foot">
        共 {{ options.length }} 个节点　·　鼠标移到某一行，左侧图上对应节点会放大
      </div>
    </div>
  </el-popover>
</template>

<script setup>
/**
 * 节点选择器。
 *
 * 为什么不用 el-select：
 *   本页要求「鼠标悬停下拉项时，左侧 SVG 上对应节点放大」。
 *   el-select 的选项是内部渲染的 <li>，拿不到稳定的 hover 事件，
 *   所以这里用 el-popover + 自己的列表，hover 与点击都可控。
 *
 * 事件：
 *   update:modelValue  选定节点
 *   hover              悬停某个节点（离开列表时抛空字符串）
 */
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择节点' }
})

const emit = defineEmits(['update:modelValue', 'hover'])

const visible = ref(false)
const keyword = ref('')

const current = computed(() => props.options.find((n) => n.code === props.modelValue))

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const list = props.options
  if (!kw) return list
  return list.filter((n) =>
    n.code.toLowerCase().includes(kw) || String(n.name || '').toLowerCase().includes(kw))
})

watch(visible, (v) => {
  if (!v) {
    keyword.value = ''
    emit('hover', '')
  }
})

function typeLabel(t) {
  return t === 'dock' ? '装卸点' : t === 'charger' ? '充电位' : '通道'
}

function emitHover(code) {
  emit('hover', code)
}

function pick(code) {
  emit('update:modelValue', code)
  visible.value = false
  emit('hover', '')
}
</script>

<style scoped>
.np-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 240px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s;
}
.np-trigger:hover {
  border-color: #0f9da8;
}
.np-trigger.is-empty .np-ph {
  color: #a8abb2;
}
.np-code {
  font-family: Consolas, Monaco, monospace;
  font-weight: 700;
  color: #162e58;
  flex: 0 0 auto;
}
.np-name {
  flex: 1;
  font-size: 13px;
  color: #4a5a70;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.np-ph {
  flex: 1;
  font-size: 13px;
}
.np-arrow {
  color: #a8abb2;
  font-size: 12px;
  flex: 0 0 auto;
}
.np-panel {
  padding: 2px;
}
.np-search {
  margin-bottom: 8px;
}
.np-list {
  max-height: 300px;
  overflow: auto;
}
.np-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
}
.np-item:hover {
  background: #f0f7f8;
}
.np-item.is-active {
  background: #e6f4f5;
}
.np-item .np-name {
  color: #2b2b2b;
}
.np-type {
  flex: 0 0 auto;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #eef1f5;
  color: #6b7280;
}
.np-type.dock {
  background: #e2f4f5;
  color: #0b7b84;
}
.np-type.charger {
  background: #e3f6ec;
  color: #1e7a4c;
}
.np-empty {
  padding: 18px;
  text-align: center;
  color: #a8abb2;
  font-size: 12px;
}
.np-foot {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f3f7;
  font-size: 11px;
  color: #9aa7b4;
}
</style>
