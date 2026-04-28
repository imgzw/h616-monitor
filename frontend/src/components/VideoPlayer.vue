<template>
  <div class="video-player" ref="containerRef">
    <img
      v-if="mode === 'mjpeg'"
      :src="mjpegUrl"
      class="video-element"
      @load="onMjpegLoad"
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
        <span>实时{{ lowBandwidth ? ' (低带宽)' : '' }} — {{ resolution }}</span>
        <span class="encoder-badge">{{ modeBadge }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'
import { getGo2rtcConfig, getLowBandwidthUrl } from '../api'

const props = defineProps<{
  streamName?: string
  lowBandwidth?: boolean
}>()

const videoRef = ref<HTMLVideoElement>()
const containerRef = ref<HTMLDivElement>()
const connected = ref(false)
const connecting = ref(false)
const resolution = ref('')
const encoderInfo = ref('')
const mode = ref<'webrtc' | 'mjpeg'>('webrtc')
const modeInfo = ref('')

let pc: RTCPeerConnection | null = null
let mjpegImg: HTMLImageElement | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let webrtcFailed = false

const mjpegUrl = computed(() => '/api/stream.mjpeg?src=camera')

const modeBadge = computed(() => {
  if (mode.value === 'mjpeg') return 'MJPEG'
  if (encoderInfo.value) return encoderInfo
  return 'WebRTC'
})

async function connect() {
  if (connecting.value) return
  connecting.value = true
  connected.value = false
  modeInfo.value = ''

  // If WebRTC already failed on this stream, go straight to MJPEG
  if (webrtcFailed) {
    connectMjpeg()
    return
  }

  try {
    const { data: config } = await getGo2rtcConfig()
    let name = props.streamName || config.camera_name

    if (props.lowBandwidth) {
      try {
        const { data: lb } = await getLowBandwidthUrl('webrtc')
        if (lb.available) {
          name = lb.stream_name
          encoderInfo.value = lb.hw_accelerated ? 'V4L2 M2M' : 'x264'
        } else {
          encoderInfo.value = ''
        }
      } catch {
        encoderInfo.value = ''
      }
    } else {
      encoderInfo.value = ''
    }

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
        // WebRTC failed, mark it and fall back to MJPEG
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
      // WebRTC endpoint returned error (codec mismatch, stream not found, etc.)
      webrtcFailed = true
      disconnect()
      connectMjpeg()
      return
    }

    const answerSdp = await resp.text()

    // Check if answer is valid (go2rtc returns error SDP when codecs don't match)
    if (answerSdp.includes('0 VIDEO') && answerSdp.includes('rtx')) {
      // Valid video track in answer — proceed
    }

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
  modeInfo.value = 'MJPEG 模式'
  connecting.value = false
  // The <img> tag handles MJPEG streaming natively via src binding
  // connected will be set to true on @load event
}

function onMjpegLoad() {
  connected.value = true
  resolution.value = '1280x720'
}

function onMjpegError() {
  connected.value = false
  scheduleReconnect()
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => {
    disconnect()
    // Reset webrtcFailed to try WebRTC again on reconnect
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
  if (mjpegImg) {
    mjpegImg.src = ''
    mjpegImg = null
  }
  connected.value = false
}

function onVideoReady() {
  if (videoRef.value) {
    const v = videoRef.value
    resolution.value = `${v.videoWidth}x${v.videoHeight}`
  }
}

watch(() => props.lowBandwidth, () => {
  webrtcFailed = false
  disconnect()
  connect()
})

onMounted(() => connect())
onBeforeUnmount(() => disconnect())

defineExpose({ connect, disconnect, connected })
</script>

<style scoped>
.video-player {
  position: relative;
  width: 100%;
  background: #000;
  border-radius: 8px;
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
</style>