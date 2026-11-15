/**
 * 轮询组合式函数：让页面按固定间隔自动重新拉数据。
 *
 * 为什么需要它：
 *   现在的界面是「你点一下，它才去问服务端一次」。数据库里的数据是立刻变的，
 *   但别人屏幕上不会自动变 —— 因为浏览器不会主动知道。计划员建了工单，
 *   操作工必须刷新页面或切菜单才看得见。
 *
 * 为什么用轮询而不是 WebSocket：
 *   WebSocket 才是真·实时推送，但要装 Django Channels + 改 ASGI + 维护长连接，
 *   大约两天工作量。轮询只需要一个 setInterval，1 小时能落地，
 *   对「看板 / 告警 / 待办」这类 30 秒级延迟完全够用。第一代选轮询，是取舍不是偷懒。
 *
 * 三个细节（都是为了不添麻烦）：
 *   1. 页面在后台标签页时（document.hidden）跳过本轮 —— 不给服务器白扛压力
 *   2. 单次请求失败只记日志，不弹错误框 —— 轮询失败是常态（断网/重启），
 *      弹框会把用户烦死；下次成功会自动恢复
 *   3. 组件卸载时清掉定时器 —— 否则切页面后还在偷偷请求，越积越多
 *
 * 用法（三行）：
 *   import { usePolling } from '@/composables/usePolling'
 *   ... 定义好 async function load() { ... }
 *   const { lastAt, enabled } = usePolling(load, 30000)   // 30 秒
 *   // enabled 可绑一个开关，让用户自己关掉自动刷新
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

export function usePolling(fn, intervalMs = 30000, options = {}) {
  const { immediate = false } = options
  const enabled = ref(true)
  const lastAt = ref(null)
  const failCount = ref(0)
  let timer = null
  let running = false

  async function tick() {
    // 上一轮还没结束就跳过，避免慢接口把请求堆起来
    if (running) return
    if (!enabled.value) return
    if (typeof document !== 'undefined' && document.hidden) return
    running = true
    try {
      await fn()
      lastAt.value = new Date()
      failCount.value = 0
    } catch (e) {
      failCount.value += 1
      // 连续失败不弹窗，只在控制台留痕，方便排查
      if (failCount.value <= 3) {
        console.warn('[polling] 本轮刷新失败（第 %d 次）', failCount.value, e)
      }
    } finally {
      running = false
    }
  }

  onMounted(() => {
    if (immediate) tick()
    timer = setInterval(tick, intervalMs)
  })

  onBeforeUnmount(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })

  return { enabled, lastAt, failCount, tick, intervalMs }
}

export default usePolling
