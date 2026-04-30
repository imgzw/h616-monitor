<template>
  <div class="video-player" ref="containerRef">
    <img
      v-if="mode === 'mjpeg'"
      :src="mjpegUrl"
      class="video-element"
      @load="onMjpegFrame"
      @error="onMjpegError"
    />
    <video
      v-else
      ref="videoRef"
      autoplay
      playsinline
      muted
      class="video-element"
      @loadedmetadata="onVideoReady"
      @timeupdate="onVideoFrame"
    />
    <div v-if="!connected" class="video-overlay">
      <el-icon :size="48" class="connecting-icon"><VideoCamera /></el-icon>
      <p>{{ connecting ? '正在连接...' : '未连接' }}</p>
      <p v-if="modeInfo" class="mode-info">{{ modeInfo }}</p>
      <el-button v-if="!connecting" type="primary" @click="connect">重新连接</el-button>
    </div>
    <div v-if="connected" class="video-overlay-hover" @click.stop>
      <div class="overlay-status">
        <span class="status-dot active" />
        <span>{{ resolution }}</span>
        <span class="encoder-badge">{{ modeBadge }}</span>
      </div>
    </div>
    <!-- Permanent overlay: time + FPS -->
    <div v-if="connected" class="video-info-bar">
      <span class="info-time">{{ currentTime }}</span>
      <span class="info-fps">{{ fps }} fps</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'
import { getGo2rtcConfig } from '../api'

const props = defineProps<{
  streamName?: string
  lowBandwidth?: boolean
}>()

const videoRef = ref<HTMLVideoElement>()
const containerRef = ref<HTMLDivElement>()
const connected = ref(false)
const connecting = ref(false)
const resolution = ref('')
const mode = ref<'webrtc' | 'mjpeg'>('webrtc')
const modeInfo = ref('')

// --- Clock ---
const currentTime = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}

// --- FPS ---
const fps = ref(0)
let frameTimestamps: number[] = []

function recordFrame() {
  const now = performance.now()
  frameTimestamps.push(now)
  const cutoff = now - 1000
  while (frameTimestamps.length && frameTimestamps[0] < cutoff) {
    frameTimestamps.shift()
  }
  fps.value = frameTimestamps.length
}

function onMjpegFrame() {
  if (!connected.value) {
    connected.value = true
    resolution.value = '1280x720'
  }
  recordFrame()
}

function onVideoFrame() {
  recordFrame()
}

// --- Connection state ---
let pc: RTCPeerConnection | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let webrtcFailed = false

const mjpegUrl = computed(() => '/api/stream.mjpeg?src=camera')

const modeBadge = computed(() => {
  if (mode.value === 'mjpeg') return 'MJPEG'
  return 'WebRTC'
})

async function connect() {
  if (connecting.value) return

  if (props.lowBandwidth) {
    connectMjpeg()
    return
  }

  if (webrtcFailed) {
    connectMjpeg()
    return
  }

  connecting.value = true
  connected.value = false
  modeInfo.value = ''

  try {
    const { data: config } = await getGo2rtcConfig()
    const name = props.streamName || config.camera_name

    const url = `/api/webrtc?src=${name}`

    pc = new RTCPeerConnection({ iceServers: [] })
    pc.addTransceiver('video', { direction: 'recvonly' })
    pc.addTransceiver('audio', { direction: 'recvonly' })

    pc.ontrack = (event) => {
      if (videoRef.value && event.streams[0]) {
        videoRef.value.srcObject = event.streams[0]
        connected.value = true
        mode.value = 'webrtc'
      }
    }

    pc.oniceconnectionstatechange = () => {
      if (!pc) return
      const state = pc.iceConnectionState
      if (state === 'failed' || state === 'disconnected') {
        connected.value = false
        webrtcFailed = true
        disconnect()
        connectMjpeg()
      }
    }

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/sdp' },
      body: offer.sdp,
    })

    if (!resp.ok) {
      webrtcFailed = true
      disconnect()
      connectMjpeg()
      return
    }

    const answerSdp = await resp.text()
    await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
  } catch (e) {
    console.error('WebRTC connect failed:', e)
    webrtcFailed = true
    disconnect()
    connectMjpeg()
  } finally {
    connecting.value = false
  }
}

function connectMjpeg() {
  mode.value = 'mjpeg'
  modeInfo.value = 'MJPEG 直出模式'
  connecting.value = false
  connected.value = false
}

function onMjpegError() {
  connected.value = false
  scheduleReconnect()
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => {
    disconnect()
    webrtcFailed = false
    connect()
  }, 5000)
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (pc) {
    pc.close()
    pc = null
  }
  connected.value = false
  fps.value = 0
  frameTimestamps = []
}

function onVideoReady() {
  if (videoRef.value) {
    const v = videoRef.value
    resolution.value = `${v.videoWidth}x${v.videoHeight}`
  }
}

watch(() => props.lowBandwidth, (newVal) => {
  disconnect()
  webrtcFailed = false
  modeInfo.value = ''
  connect()
})

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  connect()
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  disconnect()
})

defineExpose({ connect, disconnect, connected })
</script>

<style scoped>
.video-player {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  border-radius: var(--radius);
  overflow: hidden;
  aspect-ratio: 16 / 9;
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.video-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.85);
  color: var(--text-secondary);
  gap: 8px;
}

.connecting-icon {
  color: var(--accent);
  animation: pulse 2s ease-in-out infinite;
}

.mode-info {
  font-size: 12px;
  color: var(--text-tertiary);
}

.video-overlay-hover {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}

.video-player:hover .video-overlay-hover {
  opacity: 1;
  pointer-events: auto;
}

.overlay-status {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(0,0,0,0.6);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  color: #fff;
}

.encoder-badge {
  background: rgba(46, 204, 113, 0.3);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
}

/* Permanent info bar: time + fps */
.video-info-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 14px;
  background: linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 100%);
  pointer-events: none;
  z-index: 2;
}
.info-time {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.6);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
}
.info-fps {
  font-size: 12px;
  font-weight: 500;
  color: rgba(255,255,255,0.8);
  background: rgba(0,0,0,0.4);
  padding: 2px 8px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}
</style>