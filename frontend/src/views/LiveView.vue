<template>
  <div class="live-view">
    <div class="live-main">
      <div class="video-wrapper">
        <VideoPlayer ref="playerRef" stream-name="camera" :low-bandwidth="true" />
      </div>
      <div class="live-sidebar">
        <ZoomControl />
        <div class="control-panel">
          <div class="panel-title">视频源</div>
          <div class="stream-info">
            <span class="sw-badge">MJPEG 直出</span>
            <span class="stream-detail">1280x720 · 120fps</span>
          </div>
        </div>
        <div class="control-panel">
          <div class="panel-title">录制控制</div>
          <div class="recording-status">
            <span :class="['status-dot', status.recording?.is_recording ? 'recording' : 'inactive']" />
            <span>{{ status.recording?.is_recording ? '录制中' : '未录制' }}</span>
          </div>
          <div v-if="status.recording?.is_recording" class="recording-info">
            <span>开始: {{ formatTime(status.recording.started_at) }}</span>
          </div>
          <div class="recording-actions">
            <el-button v-if="!status.recording?.is_recording" type="danger" @click="handleStart">
              <el-icon><VideoCamera /></el-icon> 开始录制
            </el-button>
            <el-button v-else type="danger" plain @click="handleStop">
              <el-icon><VideoPause /></el-icon> 停止录制
            </el-button>
          </div>
        </div>
        <div class="control-panel">
          <div class="panel-title">系统状态</div>
          <div class="status-row">
            <span class="status-label">流媒体</span>
            <span :class="['status-dot', status.stream_active ? 'active' : 'inactive']" />
            <span>{{ status.stream_active ? '在线' : '离线' }}</span>
          </div>
          <div class="status-row">
            <span class="status-label">CPU温度</span>
            <span :class="['temp-value', tempClass]">{{ status.cpu_temp?.temp_c ?? '-' }}°C</span>
            <span v-if="status.cpu_temp?.warning" class="temp-warn">⚠ 过热</span>
          </div>
          <div class="status-row">
            <span class="status-label">运行时间</span>
            <span>{{ formatUptime(status.uptime_seconds) }}</span>
          </div>
          <div class="status-row">
            <span class="status-label">磁盘使用</span>
            <el-progress
              :percentage="status.storage?.usage_percent ?? 0"
              :stroke-width="10"
              :color="diskColorVal"
            />
          </div>
          <div class="status-row storage-detail">
            <span>{{ formatSize(status.storage?.used_bytes) }} / {{ formatSize(status.storage?.total_bytes) }}</span>
          </div>
          <div class="status-row">
            <span class="status-label">录像数</span>
            <span>{{ status.storage?.recordings_count ?? 0 }} 个</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject } from 'vue'
import { VideoCamera, VideoPause } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VideoPlayer from '../components/VideoPlayer.vue'
import ZoomControl from '../components/ZoomControl.vue'
import { startRecording, stopRecording, type SystemStatus } from '../api'
import { formatSize, formatUptime, formatTime, diskColor } from '../utils/format'

const playerRef = ref()
const lowBandwidth = ref(true)

const status = inject<SystemStatus>('systemStatus')!
const refreshStatus = inject<() => Promise<void>>('refreshStatus')!

const tempClass = computed(() => {
  const t = status.cpu_temp?.temp_c ?? 0
  if (t < 0) return 'temp-unknown'
  if (t >= (status.cpu_temp?.critical_threshold ?? 85)) return 'temp-critical'
  if (t >= (status.cpu_temp?.high_threshold ?? 75)) return 'temp-high'
  return 'temp-normal'
})

async function handleStart() {
  try {
    await startRecording()
    ElMessage.success('开始录制')
    await refreshStatus()
  } catch {
    ElMessage.error('启动录制失败')
  }
}

async function handleStop() {
  try {
    await stopRecording()
    ElMessage.success('录制已停止')
    await refreshStatus()
  } catch {
    ElMessage.error('停止录制失败')
  }
}

const diskColorVal = computed(() => diskColor(status.storage?.usage_percent ?? 0))
</script>

<style scoped>
.live-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.live-main {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}
.video-wrapper {
  flex: 1;
  min-width: 0;
  background: #000;
  border-radius: var(--radius);
  overflow: hidden;
}
.live-sidebar {
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}
.control-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px;
}
.panel-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.bandwidth-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.encoder-info {
  font-size: 11px;
  white-space: nowrap;
}
.stream-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stream-detail {
  font-size: 11px;
  color: var(--text-tertiary);
}
.hw-badge {
  background: rgba(63, 185, 80, 0.12);
  color: var(--success);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
}
.sw-badge {
  background: rgba(210, 153, 34, 0.12);
  color: var(--warning);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
}
.recording-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}
.recording-info {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.recording-actions .el-button {
  width: 100%;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}
.status-row:last-child { margin-bottom: 0; }
.status-label {
  color: var(--text-secondary);
  min-width: 54px;
  font-size: 12px;
}
.storage-detail {
  justify-content: flex-end;
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: -4px;
}
.temp-value { font-weight: 600; }
.temp-normal { color: var(--success); }
.temp-high { color: var(--warning); }
.temp-critical { color: var(--danger); }
.temp-unknown { color: var(--text-secondary); }
.temp-warn {
  color: var(--danger);
  font-size: 11px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .live-main {
    flex-direction: column;
    gap: 12px;
  }
  .video-wrapper {
    aspect-ratio: 16 / 9;
    max-height: 45vh;
  }
  .live-sidebar {
    width: 100%;
    flex-shrink: 1;
    gap: 8px;
  }
  .control-panel {
    padding: 12px;
  }
}
</style>
