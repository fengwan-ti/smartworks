<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    :clearable="clearable"
    :disabled="disabled"
    :style="{ width }"
    @update:model-value="onChange"
  >
    <el-option v-for="o in options" :key="o.value" :label="o.label" :value="o.value" />
  </el-select>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { loadDict } from '@/utils/dict'

/**
 * 字典下拉。用法：
 *   <DictSelect v-model="form.status" dict-type="work_order_status" />
 * 字典内容在后端「数据字典」页维护，前端不写死选项。
 */
const props = defineProps({
  dictType: { type: String, required: true },
  modelValue: { type: [String, Number], default: '' },
  placeholder: { type: String, default: '请选择' },
  width: { type: String, default: '160px' },
  clearable: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'change'])
const options = ref([])

onMounted(async () => {
  options.value = await loadDict(props.dictType)
})

function onChange(value) {
  emit('update:modelValue', value)
  emit('change', value)
}
</script>
