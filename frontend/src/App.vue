<template>
  <el-container class="app-layout">
    <el-aside width="64px" class="app-sidebar">
      <div class="sidebar-logo" @click="$router.push('/')">
        <el-icon :size="28" color="#e94560"><Monitor /></el-icon>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="sidebar-menu"
        background-color="transparent"
        text-color="#a0a0b0"
        active-text-color="#e94560"
        :router="true"
      >
        <el-menu-item index="/">
          <el-icon><VideoCamera /></el-icon>
        </el-menu-item>
        <el-menu-item index="/recordings">
          <el-icon><Film /></el-icon>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-bottom">
        <div class="sidebar-status">
          <span :class="['status-dot', systemStatus.stream_active ? 'active' : 'inactive']" />
        </div>
      </div>
    </el-aside>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, VideoCamera, Film } from '@element-plus/icons-vue'
import { getStatus, type SystemStatus } from './api'

const route = useRoute()
const activeMenu = computed(() => route.path)

const systemStatus = reactive<Partial<SystemStatus>>({
  stream_active: false,
})

let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollStatus() {
  try {
    const { data } = await getStatus()
    systemStatus.stream_active = data.stream_active
  } catch {
    systemStatus.stream_active = false
  }
}

onMounted(() => {
  pollStatus()
  pollTimer = setInterval(pollStatus, 10000)
})
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
  overflow: hidden;
}
.app-sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 12px;
}
.sidebar-logo {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-bottom: 8px;
}
.sidebar-menu {
  border-right: none;
  width: 100%;
}
.sidebar-menu .el-menu-item {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  padding: 0 !important;
}
.sidebar-menu .el-menu-item .el-icon {
  margin-right: 0;
  font-size: 20px;
}
.sidebar-bottom {
  margin-top: auto;
  padding-bottom: 16px;
}
.sidebar-status {
  display: flex;
  justify-content: center;
}
.app-main {
  background: var(--bg-primary);
  padding: 20px;
  overflow-y: auto;
  --el-main-padding: 20px;
}
</style>