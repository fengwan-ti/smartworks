<template>
  <div class="sw-page">
    <div class="sw-card">
      <el-result icon="info" :title="title" sub-title="该功能尚未开发">
        <template #extra>
          <p class="ph-tip">菜单由后端接口驱动，路由已通。页面在对应周次实现。</p>
          <el-tag type="info">当前为 Day 1 骨架</el-tag>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => route.meta.title || '功能建设中')
</script>

<style scoped>
.ph-tip {
  color: #8a93a5;
  font-size: 13px;
  margin-bottom: 10px;
}
</style>
