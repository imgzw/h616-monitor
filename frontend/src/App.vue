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
      <router-view v-slot="{ Component }">
        <transition name="fade-slide" mode="out-in">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </transition>
      </router-view>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, reactive, onMounted, onBeforeUnmount, provide } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, VideoCamera, Film } from '@element-plus/icons-vue'
import { getStatus, type SystemStatus } from './api'

const route = useRoute()
const activeMenu = computed(() => route.path)

const systemStatus = reactive<SystemStatus>({
  stream_active: false,
  recording: { is_recording: false, started_at: null, segment_duration: 300, pid: null },
  storage: { total_bytes: 0, used_bytes: 0, free_bytes: 0, usage_percent: 0, recordings_bytes: 0, recordings_count: 0 },
  cpu_temp: { temp_c: 0, high_threshold: 75, critical_threshold: 85, warning: false },
  transcode: { available: false, encoder: '', hw_accelerated: false, v4l2_m2m_available: false, stream_name: '', low_bandwidth_bitrate: 0 },
  uptime_seconds: 0,
})

provide('systemStatus', systemStatus)
provide('refreshStatus', pollStatus)

let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollStatus() {
  try {
    const { data } = await getStatus()
    Object.assign(systemStatus, data)
  } catch {
    systemStatus.stream_active = false
  }
}

onMounted(() => {
  pollStatus()
  pollTimer = setInterval(pollStatus, 5000)
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
  border-radius: var(--radius-sm);
  transition: background 0.2s;
}
.sidebar-logo:hover {
  background: var(--bg-tertiary);
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
  border-radius: 6px;
  margin: 2px 6px;
  transition: background 0.15s;
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
  padding: 16px;
  overflow-y: auto;
  --el-main-padding: 16px;
}

@media (max-width: 768px) {
  .app-main {
    padding: 10px;
    --el-main-padding: 10px;
  }
}
</style>