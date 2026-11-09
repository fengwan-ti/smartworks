/**
 * 数据字典缓存。
 *
 * 为什么需要缓存：一个页面里可能有多处用到同一类字典（如状态、类别），
 * 每次都请求接口会明显拖慢首屏。这里按 dict_type 缓存，全站共用一份。
 *
 * 返回结构统一为 [{ value, label }]，直接给 el-select 用。
 */
import { fetchDicts } from '@/api/core'

const cache = {}
const pending = {}

export async function loadDict(dictType) {
  if (cache[dictType]) return cache[dictType]
  if (pending[dictType]) return pending[dictType]

  pending[dictType] = fetchDicts(dictType)
    .then((data) => {
      const rows = (data && data.results) || []
      const options = rows.map((x) => ({ value: x.dict_code, label: x.dict_name }))
      cache[dictType] = options
      return options
    })
    .finally(() => {
      delete pending[dictType]
    })

  return pending[dictType]
}

/** 根据字典值取中文名，找不到就原样返回。 */
export async function dictLabel(dictType, value) {
  const options = await loadDict(dictType)
  const hit = options.find((o) => o.value === value)
  return hit ? hit.label : value
}

/** 清缓存，调完字典维护页后用。 */
export function clearDictCache() {
  Object.keys(cache).forEach((k) => delete cache[k])
}
