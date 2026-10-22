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
        show-overflow-tooltip
      />
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
 * 约定：父组件负责取数，本组件只上报分页变化。
 * 事件 change 抛出 { page, pageSize }
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
