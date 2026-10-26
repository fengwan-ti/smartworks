<template>
  <div>
    <el-table :data="rows" border stripe size="default" style="width: 100%">
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth || 120"
        :show-overflow-tooltip="!col.slot"
      >
        <!--
          这里刻意把插槽判断写在 el-table-column 的 default 插槽内部，而不是写成
          <template v-if="col.slot" #default>。
          后者属于"结构性指令 + v-slot 写在同一个 template 上"，行为依赖 Vue 版本，
          容易出现"插槽没生效、单元格全空"的现象。
        -->
        <template #default="scope">
          <slot v-if="col.slot" :name="col.slot" :row="scope.row" :index="scope.$index" />
          <span v-else>{{ display(scope.row, col.prop) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="showPagination"
      style="margin-top: 12px; justify-content: flex-end"
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

/**
 * 通用分页表格。
 *
 * props：
 *   columns  列定义 [{ prop, label, width?, minWidth?, slot? }]
 *            slot 填了就在页面里用同名具名插槽自定义单元格
 *   rows / total  数据与总数（父组件负责取数）
 *
 * 事件：change -> { page, pageSize }
 */
const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  showPagination: { type: Boolean, default: true }
})

const emit = defineEmits(['change'])

const page = ref(1)
const pageSize = ref(10)

/** 普通列取值，null 显示空字符串而不是 "null" */
function display(row, prop) {
  const v = row ? row[prop] : ''
  return v === null || v === undefined ? '' : v
}

function onPageChange(value) {
  page.value = value
  emit('change', { page: page.value, pageSize: pageSize.value })
}

function onSizeChange(value) {
  pageSize.value = value
  page.value = 1
  emit('change', { page: page.value, pageSize: pageSize.value })
}
</script>
