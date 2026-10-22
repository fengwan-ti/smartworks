<template>
  <el-container class="layout">
    <el-aside width="210px" class="layout-aside">
      <div class="layout-logo">SmartWorks</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#1f3864"
        text-color="#c9d3e6"
        active-text-color="#ffffff"
      >
        <template v-for="item in menus" :key="item.code">
          <el-sub-menu v-if="item.children && item.children.length" :index="item.code">
            <template #title>
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
              <span>{{ item.name }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              :key="child.code"
              :index="child.path"
            >
              {{ child.name }}
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.name }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <span class="layout-title">{{ route.meta.title || '' }}</span>
        <el-dropdown @command="onCommand">
          <span class="layout-user">
            {{ userStore.displayName }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人信息</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 菜单完全由后端驱动：加岗位只改数据库，不改前端
const menus = computed(() => userStore.menus)

onMounted(async () => {
  if (!userStore.user) {
    try {
      await userStore.fetchMe()
    } catch (e) {
      userStore.reset()
      router.push('/login')
    }
  }
})

async function onCommand(command) {
  if (command === 'logout') {
    await userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } else {
    ElMessage.info('个人信息页待开发')
  }
}
</script>

<style scoped>
.layout {
  height: 100%;
}
.layout-aside {
  background: #1f3864;
  overflow-y: auto;
}
.layout-logo {
  height: 56px;
  color: #fff;
  font-size: 17px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 1px;
}
.layout-header {
  height: 56px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e6e8eb;
}
.layout-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--sw-primary);
}
.layout-user {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}
.layout-main {
  padding: 0;
  background: var(--sw-page-bg);
  overflow-y: auto;
}
</style>
