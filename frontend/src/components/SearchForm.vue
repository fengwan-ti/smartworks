<template>
  <el-form :inline="true" class="search-form" @submit.prevent="onSearch">
    <el-form-item v-for="f in fields" :key="f.prop" :label="f.label">
      <!-- 文本 -->
      <el-input
        v-if="!f.type || f.type === 'input'"
        v-model="values[f.prop]"
        :placeholder="f.placeholder || '请输入'"
        :style="{ width: f.width || '170px' }"
        clearable
        @keyup.enter="onSearch"
      />

      <!-- 下拉 -->
      <el-select
        v-else-if="f.type === 'select'"
        v-model="values[f.prop]"
        :placeholder="f.placeholder || '全部'"
        :style="{ width: f.width || '170px' }"
        clearable
      >
        <el-option
          v-for="o in f.options || []"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>

      <!-- 字典下拉 -->
      <DictSelect
        v-else-if="f.type === 'dict'"
        v-model="values[f.prop]"
        :dict-type="f.dictType"
        :width="f.width || '160px'"
      />

      <!-- 日期 -->
      <el-date-picker
        v-else-if="f.type === 'date'"
        v-model="values[f.prop]"
        type="date"
        :placeholder="f.placeholder || '选择日期'"
        value-format="YYYY-MM-DD"
        :style="{ width: f.width || '170px' }"
      />

      <!-- 日期区间 -->
      <el-date-picker
        v-else-if="f.type === 'daterange'"
        v-model="values[f.prop]"
        type="daterange"
        range-separator="至"
        start-placeholder="开始"
        end-placeholder="结束"
        value-format="YYYY-MM-DD"
        :style="{ width: f.width || '260px' }"
      />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
      <el-button @click="onReset">重置</el-button>
      <slot />
    </el-form-item>
  </el-form>
</template>

<script setup>
import { reactive, watch } from 'vue'
import DictSelect from './DictSelect.vue'

/**
 * 查询区。字段用 schema 描述，避免每个页面重复写 el-form-item。
 *
 * 用法：
 *   <SearchForm :fields="fields" :loading="loading"
 *               @search="load" @reset="onReset" />
 *
 * fields 支持的类型：input / select / dict / date / daterange
 *   { prop, label, type, options?, dictType?, width?, placeholder? }
 *
 * search 事件抛出的是「已去掉空值」的对象，d 开头的区间字段会展开成
 *   xxx_from / xxx_to，后端 filters 可以直接按字段名接。
 */
const props = defineProps({
  fields: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['search', 'reset'])

const values = reactive({})

// 初始化所有字段，保证模板里能安全绑定
props.fields.forEach((f) => {
  values[f.prop] = f.type === 'daterange' ? [] : ''
})

watch(
  () => props.fields,
  (list) => {
    list.forEach((f) => {
      if (!(f.prop in values)) {
        values[f.prop] = f.type === 'daterange' ? [] : ''
      }
    })
  }
)

function buildParams() {
  const params = {}
  Object.keys(values).forEach((key) => {
    const field = props.fields.find((f) => f.prop === key)
    const val = values[key]

    if (field && field.type === 'daterange') {
      if (Array.isArray(val) && val.length === 2 && val[0] && val[1]) {
        params[key + '_from'] = val[0]
        params[key + '_to'] = val[1]
      }
      return
    }
    if (val !== '' && val !== null && val !== undefined) {
      params[key] = val
    }
  })
  return params
}

function onSearch() {
  emit('search', buildParams())
}

function onReset() {
  props.fields.forEach((f) => {
    values[f.prop] = f.type === 'daterange' ? [] : ''
  })
  emit('reset', {})
  emit('search', {})
}

defineExpose({ values, buildParams })
</script>

<style scoped>
.search-form {
  padding: 4px 0 0;
}
</style>
