<template>
  <div class="sw-page">
    <!-- 库龄是"钱压了多久"，所以四个数都围绕数量和天数，不堆图 -->
    <div class="sw-metrics">
      <div class="sw-metric">
        <div class="sw-metric__label">在库数量</div>
        <div class="sw-metric__value">{{ aging.total_qty }}<span class="sw-metric__unit">件</span></div>
        <div class="sw-metric__foot">{{ aging.batch_count }} 个批次（截至 {{ aging.as_of }}）</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">90 天以上</div>
        <div class="sw-metric__value" :class="{ 'sw-metric--danger-text': aging.over_90_qty > 0 }">
          {{ aging.over_90_qty }}<span class="sw-metric__unit">件</span>
        </div>
        <div class="sw-metric__foot">呆滞库存，占比 {{ over90Ratio }}%</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">周转率</div>
        <div class="sw-metric__value">{{ rate.turnover_rate }}<span class="sw-metric__unit">次</span></div>
        <div class="sw-metric__foot">近 {{ rate.period_days }} 天：出库 {{ rate.shipped_qty }} / 在库 {{ rate.current_stock_qty }}</div>
      </div>
      <div class="sw-metric">
        <div class="sw-metric__label">周转天数</div>
        <div class="sw-metric__value">
          {{ rate.turnover_days === null || rate.turnover_days === undefined ? '—' : rate.turnover_days }}
          <span class="sw-metric__unit">天</span>
        </div>
        <div class="sw-metric__foot">没有出库时显示"—"，不是 0（0 会被误读成"卖得极快"）</div>
      </div>
    </div>

    <!-- 四档占比：用进度条，不引图表库 -->
    <div class="sw-card">
      <div class="sw-toolbar">
        <span style="font-weight: 600">库龄分布</span>
        <el-date-picker v-model="asOf" type="date" value-format="YYYY-MM-DD"
                        placeholder="截止日期" style="width: 150px" @change="loadAging" />
        <el-select v-model="warehouse" clearable placeholder="全部仓库"
                   style="width: 170px" @change="loadAging">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
        </el-select>
        <el-select v-model="kind" style="width: 140px" @change="loadAging">
          <el-option label="只看成品" value="product" />
          <el-option label="只看原料" value="material" />
          <el-option label="全部" value="" />
        </el-select>
        <el-button :loading="loading" @click="loadAging">刷新</el-button>
      </div>

      <div class="bucket-rows">
        <div v-for="b in aging.buckets" :key="b.label" class="bucket-row">
          <span class="bucket-label">{{ b.label }}</span>
          <div class="bucket-bar">
            <div class="bucket-bar__fill"
                 :class="{ 'bucket-bar__fill--danger': b.label === '90天以上' && b.qty > 0 }"
                 :style="{ width: (b.ratio || 0) + '%' }" />
          </div>
          <span class="bucket-num">{{ b.qty }} 件</span>
          <span class="sw-sub">{{ b.batch_count }} 批 · {{ b.ratio }}%</span>
        </div>
      </div>
    </div>

    <div class="sw-card">
      <BaseTable :columns="columns" :rows="aging.items" :total="aging.items.length"
                 :show-pagination="false">
        <template #age="{ row }">
          <span :class="{ 'sw-danger-text': row.age_days >= 90 }">{{ row.age_days }} 天</span>
        </template>
        <template #bucket="{ row }">
          <el-tag size="small" :type="row.age_days >= 90 ? 'danger' : (row.age_days >= 61 ? 'warning' : 'success')"
                  effect="light">
            {{ row.bucket }}
          </el-tag>
        </template>
      </BaseTable>
    </div>
  </div>
</template>

<script setup>
/**
 * 库龄分析（成品仓）。
 *
 * 口径：
 *   库龄 = 截止日期 − 批次入库日期；按"当前可用数量"算，不含已占用/已出库部分。
 *   四档 0-30 / 31-60 / 61-90 / 90+，90 以上单独叫"呆滞库存"。
 *   周转率 = 近 N 天出库量 ÷ 当前在库量（不是 ÷ 平均库存，简化了，报告里写明）。
 *
 * 为什么要 kind 筛选：同一个库龄接口原料侧也要用，
 * 成品页上混进"45号钢棒"会被问"这是成品仓还是原料仓"。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import BaseTable from '@/components/BaseTable.vue'
import { listWarehouses, stockAging, turnover } from '@/api/inventory'

const loading = ref(false)
const asOf = ref('')
const warehouse = ref(null)
const kind = ref('product')
const warehouses = ref([])

const aging = reactive({
  as_of: '', total_qty: 0, batch_count: 0,
  buckets: [], over_90_qty: 0, items: []
})
const rate = reactive({
  period_days: 90, shipped_qty: 0, current_stock_qty: 0,
  turnover_rate: 0, turnover_days: null
})

const over90Ratio = computed(() => {
  const total = Number(aging.total_qty || 0)
  if (!total) return '0.0'
  return ((Number(aging.over_90_qty || 0) / total) * 100).toFixed(1)
})

const columns = [
  { prop: 'batch_no', label: '批次号', width: 150, fixed: 'left' },
  { prop: 'product_name', label: '产品', minWidth: 220 },
  { prop: 'material_code', label: '物料编码', width: 120 },
  { prop: 'in_date', label: '入库日期', width: 120 },
  { prop: 'age_days', label: '库龄', width: 100, slot: 'age' },
  { prop: 'bucket', label: '区间', width: 110, slot: 'bucket' },
  { prop: 'qty', label: '可用数量', width: 110 }
]

async function loadAging() {
  loading.value = true
  try {
    const params = { kind: kind.value || undefined }
    if (asOf.value) params.as_of = asOf.value
    if (warehouse.value) params.warehouse = warehouse.value
    const data = await stockAging(params)
    Object.assign(aging, {
      as_of: data.as_of || '',
      total_qty: data.total_qty || 0,
      batch_count: data.batch_count || 0,
      buckets: data.buckets || [],
      over_90_qty: data.over_90_qty || 0,
      items: data.items || []
    })
    const t = await turnover({ days: 90 })
    Object.assign(rate, t || {})
  } catch (e) {
    ElMessage.error('库龄加载失败：' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const data = await listWarehouses({ page_size: 100 })
    warehouses.value = (data && data.results) || data || []
  } catch (e) {
    // 仓库列表拿不到不影响库龄本身，只是少了筛选
    console.warn('[StockAging] 仓库列表加载失败', e)
  }
  await loadAging()
})
</script>

<style scoped>
.bucket-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 6px 2px 2px;
}
.bucket-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.bucket-label {
  width: 84px;
  color: #606266;
  font-size: 13px;
}
.bucket-bar {
  flex: 1;
  height: 14px;
  background: #f0f2f5;
  border-radius: 7px;
  overflow: hidden;
}
.bucket-bar__fill {
  height: 100%;
  background: linear-gradient(90deg, #7cc7a0, #4aa87a);
  border-radius: 7px;
  transition: width .3s;
}
.bucket-bar__fill--danger {
  background: linear-gradient(90deg, #f0a3a3, #d9534f);
}
.bucket-num {
  width: 90px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.sw-danger-text {
  color: #d9534f;
  font-weight: 600;
}
.sw-metric--danger-text {
  color: #d9534f;
}
</style>
