<template>
  <div class="nf-wrap">
    <el-result icon="warning" title="404" sub-title="页面不存在或已被移除">
      <template #extra>
        <el-button type="primary" @click="$router.push('/')">返回工作台</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.nf-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
