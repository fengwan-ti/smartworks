<template>
  <el-tag :type="tagType" size="small" effect="light">{{ label }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 状态标签。状态取值与《AI 协作与角色工作包》2.6 节的统一枚举一致，
 * 不要在这里自造同义状态。
 */
const props = defineProps({
  value: { type: String, default: '' },
  map: { type: Object, default: () => ({}) }
})

const FALLBACK = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '已确认', type: 'primary' },
  released: { label: '已下达', type: 'primary' },
  in_progress: { label: '进行中', type: 'warning' },
  paused: { label: '已暂停', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
  cancelled: { label: '已取消', type: 'danger' },
  passed: { label: '合格', type: 'success' },
  failed: { label: '不合格', type: 'danger' },
  normal: { label: '正常', type: 'success' },
  wearing: { label: '磨损', type: 'warning' },
  abnormal: { label: '异常', type: 'danger' }
}

const config = computed(() => props.map[props.value] || FALLBACK[props.value] || { label: props.value, type: 'info' })
const label = computed(() => config.value.label)
const tagType = computed(() => config.value.type)
</script>
