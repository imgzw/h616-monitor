<template>
  <div class="live-view">
    <div class="live-main">
      <div class="video-wrapper">
        <VideoPlayer ref="playerRef" :stream-name="streamName" :low-bandwidth="lowBandwidth" />
      </div>
      <div class="live-sidebar">
        <ZoomControl />
        <div class="control-panel">
          <div class="panel-title">画质模式</div>
          <div class="bandwidth-toggle">
            <el-switch
              v-model="lowBandwidth"
              active-text="省流"
              inactive-text="高清"
              :disabled="!transcodeAvailable"
              @change="onBandwidthChange"
            />
            <div v-if="transcodeInfo" class="encoder-info">
              <span v-if="transcodeInfo.hw_accelerated" class="hw-badge">硬解 V4L2</span>
              <span v-else-if="transcodeInfo.available" class="sw-badge">软解 x264</span>
              <span v-else class="na-badge">不可用</span>
            </div>
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
              :color="diskColor"
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
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { VideoCamera, VideoPause } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VideoPlayer from '../components/VideoPlayer.vue'
import ZoomControl from '../components/ZoomControl.vue'
import { getStatus, startRecording, stopRecording, type SystemStatus } from '../api'

const playerRef = ref()
const streamName = ref('camera')
const lowBandwidth = ref(false)

const status = reactive<Partial<SystemStatus>>({
  stream_active: false,
  recording: { is_recording: false, started_at: null, segment_duration: 300, pid: null },
  storage: { total_bytes: 0, used_bytes: 0, free_bytes: 0, usage_percent: 0, recordings_bytes: 0, recordings_count: 0 },
  cpu_temp: { temp_c: 0, high_threshold: 75, critical_threshold: 85, warning: false },
  transcode: { available: false, encoder: '', hw_accelerated: false, v4l2_m2m_available: false, stream_name: '', low_bandwidth_bitrate: 0 },
  uptime_seconds: 0,
})

const transcodeAvailable = computed(() => status.transcode?.available ?? false)
const transcodeInfo = computed(() => status.transcode)
const tempClass = computed(() => {
  const t = status.cpu_temp?.temp_c ?? 0
  if (t < 0) return 'temp-unknown'
  if (t >= (status.cpu_temp?.critical_threshold ?? 85)) return 'temp-critical'
  if (t >= (status.cpu_temp?.high_threshold ?? 75)) return 'temp-high'
  return 'temp-normal'
})

let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchStatus() {
  try {
    const { data } = await getStatus()
    Object.assign(status, data)
  } catch {
    // silent
  }
}

async function handleStart() {
  try {
    await startRecording()
    ElMessage.success('开始录制')
    await fetchStatus()
  } catch {
    ElMessage.error('启动录制失败')
  }
}

async function handleStop() {
  try {
    await stopRecording()
    ElMessage.success('录制已停止')
    await fetchStatus()
  } catch {
    ElMessage.error('停止录制失败')
  }
}

function onBandwidthChange(val: boolean) {
  lowBandwidth.value = val
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleTimeString('zh-CN')
}

function formatUptime(sec: number | undefined) {
  if (!sec) return '-'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return `${h}小时${m}分钟`
}

function formatSize(bytes: number | undefined) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let i = 0
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return `${size.toFixed(1)} ${units[i]}`
}

const diskColor = () => {
  const pct = status.storage?.usage_percent ?? 0
  if (pct > 90) return '#e94560'
  if (pct > 75) return '#f39c12'
  return '#2ecc71'
}

onMounted(() => {
  fetchStatus()
  pollTimer = setInterval(fetchStatus, 5000)
})
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
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
}
.live-sidebar {
  width: 280px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}
.control-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-primary);
}
.bandwidth-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.encoder-info {
  font-size: 11px;
}
.hw-badge {
  background: rgba(46, 204, 113, 0.2);
  color: #2ecc71;
  padding: 2px 6px;
  border-radius: 3px;
}
.sw-badge {
  background: rgba(243, 156, 18, 0.2);
  color: #f39c12;
  padding: 2px 6px;
  border-radius: 3px;
}
.na-badge {
  color: var(--text-secondary);
  font-size: 11px;
}
.recording-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 14px;
}
.recording-info {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.recording-actions {
  margin-top: 4px;
}
.recording-actions .el-button {
  width: 100%;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13px;
}
.status-label {
  color: var(--text-secondary);
  min-width: 60px;
}
.storage-detail {
  justify-content: flex-end;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: -6px;
}
.temp-value {
  font-weight: 600;
}
.temp-normal { color: #2ecc71; }
.temp-high { color: #f39c12; }
.temp-critical { color: #e94560; }
.temp-unknown { color: var(--text-secondary); }
.temp-warn {
  color: #e94560;
  font-size: 11px;
  font-weight: 600;
}
</style>