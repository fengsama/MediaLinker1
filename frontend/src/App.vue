<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const step = ref(1)
const sourcePath = ref('')
const recursive = ref(true)
const files = ref([])
const selectedPaths = ref(new Set())
const loading = ref(false)
const pickingDirectory = ref(false)
const error = ref('')
const apiOnline = ref(false)
const mediaType = ref('tv')
const title = ref('')
const year = ref('')
const season = ref(1)
const startEpisode = ref(1)
const metadataOpen = ref(false)
const metadataLoading = ref(false)
const metadataResults = ref([])
const metadataError = ref('')
const selectedMetadataId = ref(null)
const metadataConfigMode = ref(false)
const tmdbConfigured = ref(false)
const tmdbToken = ref('')
const configSaving = ref(false)
const targetPath = ref('')
const pickingTarget = ref(false)
const linkLoading = ref(false)
const linkError = ref('')
const linkResult = ref(null)
const operationMode = ref('hardlink')
const confirmOriginalChange = ref(false)
const settingsOpen = ref(false)
const settingsView = ref('menu')
const updateInfo = ref({
  current_version: '0.5.0',
  latest_version: '',
  update_available: false,
  can_auto_update: false,
  release_url: '',
  platform: '',
  packaged: false,
  auto_update_blocked: false,
  last_update_error: '',
  last_update_log: '',
})
const updateState = ref('idle')
const updateMessage = ref('')
const autoUpdateAttempted = ref(false)
let lifecycleSocket = null
let lifecycleReconnectTimer = null
let pageIsClosing = false

function connectLifecycle() {
  if (!window.WebSocket || pageIsClosing) return
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  lifecycleSocket = new WebSocket(`${protocol}//${window.location.host}/api/lifecycle`)
  lifecycleSocket.addEventListener('open', () => lifecycleSocket.send('ready'))
  lifecycleSocket.addEventListener('close', () => {
    if (!pageIsClosing) lifecycleReconnectTimer = window.setTimeout(connectLifecycle, 1000)
  })
}

window.addEventListener('beforeunload', () => {
  pageIsClosing = true
  if (lifecycleReconnectTimer) window.clearTimeout(lifecycleReconnectTimer)
  lifecycleSocket?.close()
})

const platformLabel = computed(() => ({
  'windows-installer': 'Windows 安装版',
  'windows-portable': 'Windows 绿色版',
  linux: 'Linux 便携版',
  flatpak: 'Flatpak',
}[updateInfo.value.platform] || updateInfo.value.platform || '检测中'))

const selectedFiles = computed(() => files.value.filter((file) => selectedPaths.value.has(file.path)))
const totalSize = computed(() => selectedFiles.value.reduce((sum, file) => sum + file.size, 0))
const allSelected = computed(() => files.value.length > 0 && selectedPaths.value.size === files.value.length)
const selectedSubtitleCount = computed(() => selectedFiles.value.reduce((sum, file) => sum + (file.subtitles?.length || 0), 0))
const previews = computed(() => selectedFiles.value.map((file, index) => {
  const safeTitle = sanitizeName(title.value.trim())
  if (mediaType.value === 'movie') {
    const displayTitle = year.value ? `${safeTitle} (${year.value})` : safeTitle
    const targetName = `${displayTitle}${file.extension}`
    return { ...file, episode: null, targetName, targetFolder: displayTitle, targetParts: [displayTitle], subtitleTargets: buildSubtitleTargets(file, targetName) }
  }
  const seasonNumber = String(season.value || 0).padStart(2, '0')
  const episodeNumber = String((startEpisode.value || 1) + index).padStart(2, '0')
  const showFolder = `${safeTitle}${year.value ? ` (${year.value})` : ''}`
  const seasonFolder = `Season ${seasonNumber}`
  const targetName = `${safeTitle} S${seasonNumber}E${episodeNumber}${file.extension}`
  return { ...file, episode: `S${seasonNumber}E${episodeNumber}`, targetName, targetFolder: `${showFolder} / ${seasonFolder}`, targetParts: [showFolder, seasonFolder], subtitleTargets: buildSubtitleTargets(file, targetName) }
}))
const linkItems = computed(() => previews.value.flatMap((item) => [
  { source_path: item.path, target_parts: item.targetParts, target_name: item.targetName },
  ...item.subtitleTargets.map((subtitle) => ({ source_path: subtitle.path, target_parts: item.targetParts, target_name: subtitle.targetName })),
]))

function sanitizeName(value) {
  return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').replace(/[ .]+$/g, '').trim()
}

function buildSubtitleTargets(file, videoTargetName) {
  const videoSourceStem = file.name.slice(0, -file.extension.length)
  const videoTargetStem = videoTargetName.slice(0, -file.extension.length)
  return (file.subtitles || []).map((subtitle) => {
    const subtitleStem = subtitle.name.slice(0, -subtitle.extension.length)
    const languageSuffix = subtitleStem.slice(videoSourceStem.length)
    return { ...subtitle, targetName: `${videoTargetStem}${languageSuffix}${subtitle.extension}` }
  })
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index > 2 ? 2 : 1)} ${units[index]}`
}

function openSettings() {
  settingsView.value = 'menu'
  settingsOpen.value = true
}

async function pollUpdateStatus() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1500))
    try {
      const response = await fetch('/api/update/status')
      const data = await response.json()
      if (!response.ok) continue
      if (data.status === 'failed') {
        updateInfo.value = { ...updateInfo.value, auto_update_blocked: true, last_update_error: data.last_error, last_update_log: data.installer_log }
        updateState.value = 'error'
        updateMessage.value = data.last_error || '自动更新失败。'
        return
      }
      if (data.status === 'success') {
        updateState.value = 'up_to_date'
        updateMessage.value = `更新成功，当前版本 v${data.current_version}`
        return
      }
    } catch { /* 安装过程中后台可能正在重启 */ }
  }
  updateState.value = 'error'
  updateMessage.value = '更新等待超时。请重新打开软件查看版本；如果仍是旧版，请手动下载安装包。'
}

async function applySoftwareUpdate(force = false) {
  if (autoUpdateAttempted.value || updateState.value === 'downloading' || updateState.value === 'restarting') return
  autoUpdateAttempted.value = true
  updateState.value = 'downloading'
  updateMessage.value = `正在下载 MediaLinker v${updateInfo.value.latest_version}…`
  try {
    const response = await fetch(`/api/update/apply?force=${force ? 'true' : 'false'}`, { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '自动更新失败')
    if (data.status === 'up_to_date') {
      updateState.value = 'up_to_date'
      updateMessage.value = data.message || '当前已经是最新版本。'
      return
    }
    updateState.value = data.status === 'installing' ? 'restarting' : data.status
    updateMessage.value = data.message || '更新已下载，软件即将重新启动。'
    pollUpdateStatus()
  } catch (requestError) {
    updateState.value = 'error'
    updateMessage.value = requestError.message || '自动更新失败，请稍后重试。'
  }
}

async function checkForUpdates({ automatic = false, force = false } = {}) {
  if (updateState.value === 'checking' || updateState.value === 'downloading' || updateState.value === 'restarting') return
  updateState.value = 'checking'
  updateMessage.value = automatic ? '正在自动检查更新…' : '正在查询 GitHub 最新版本…'
  try {
    const response = await fetch(`/api/update/check?force=${force ? 'true' : 'false'}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '检查更新失败')
    updateInfo.value = data
    if (data.last_update_error) {
      updateState.value = 'error'
      updateMessage.value = data.last_update_error
      return
    }
    if (!data.update_available) {
      updateState.value = 'up_to_date'
      updateMessage.value = `当前已是最新版本 v${data.current_version}`
      return
    }
    updateState.value = 'available'
    updateMessage.value = `发现新版本 v${data.latest_version}`
    if (data.can_auto_update) {
      await applySoftwareUpdate()
    } else if (automatic) {
      updateMessage.value = `发现新版本 v${data.latest_version}，当前运行方式需要手动安装。`
    }
  } catch (requestError) {
    updateState.value = 'error'
    updateMessage.value = requestError.message || '检查更新失败，请稍后重试。'
  }
}

async function retrySoftwareUpdate() {
  autoUpdateAttempted.value = false
  updateInfo.value = { ...updateInfo.value, auto_update_blocked: false, last_update_error: '' }
  await applySoftwareUpdate(true)
}

function toggleAll() {
  selectedPaths.value = allSelected.value ? new Set() : new Set(files.value.map((file) => file.path))
}

function toggleFile(path) {
  const next = new Set(selectedPaths.value)
  next.has(path) ? next.delete(path) : next.add(path)
  selectedPaths.value = next
}

async function checkHealth() {
  try {
    const response = await fetch('/api/health')
    apiOnline.value = response.ok
  } catch { apiOnline.value = false }
}

async function checkMetadataStatus() {
  try {
    const response = await fetch('/api/metadata/config/status')
    const data = await response.json()
    tmdbConfigured.value = Boolean(data.configured)
  } catch { tmdbConfigured.value = false }
}

async function pickDirectory() {
  error.value = ''
  pickingDirectory.value = true
  try {
    const response = await fetch('/api/files/pick-directory', { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '无法打开文件夹选择窗口')
    if (data.selected) sourcePath.value = data.path
  } catch (requestError) {
    error.value = requestError.message || '文件夹选择失败。'
  } finally {
    pickingDirectory.value = false
  }
}

async function scanFiles() {
  error.value = ''
  files.value = []
  selectedPaths.value = new Set()
  if (!sourcePath.value.trim()) { error.value = '请输入需要扫描的目录。'; return }
  loading.value = true
  try {
    const response = await fetch('/api/files/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: sourcePath.value.trim(), recursive: recursive.value }) })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '扫描失败')
    files.value = data.files
  } catch (requestError) {
    error.value = requestError.message || '无法连接后端服务。'
  } finally { loading.value = false }
}

function goNext() {
  if (!selectedFiles.value.length) { error.value = '请至少选择一个影视文件。'; return }
  error.value = ''
  step.value = 2
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function buildPreview() {
  error.value = ''
  if (!title.value.trim()) { error.value = '请输入影视名称后再生成预览。'; return }
  if (mediaType.value === 'movie' && selectedFiles.value.length > 1) { error.value = '电影模式一次只能选择一个视频文件，请返回扫描页调整选择。'; return }
  step.value = 3
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function goToGenerate() {
  linkError.value = ''
  linkResult.value = null
  step.value = 4
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function pickTargetDirectory() {
  linkError.value = ''
  pickingTarget.value = true
  try {
    const response = await fetch('/api/files/pick-directory?purpose=target', { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '无法打开文件夹选择窗口')
    if (data.selected) targetPath.value = data.path
  } catch (requestError) {
    linkError.value = requestError.message || '选择输出目录失败。'
  } finally { pickingTarget.value = false }
}

async function createLinks() {
  linkError.value = ''
  linkResult.value = null
  if (!targetPath.value.trim()) { linkError.value = '请先选择硬链接输出根目录。'; return }
  if (operationMode.value === 'move' && !confirmOriginalChange.value) { linkError.value = '请确认你理解原文件将被移动并重命名。'; return }
  linkLoading.value = true
  try {
    const response = await fetch('/api/organizer/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_root: targetPath.value.trim(),
        items: linkItems.value,
        mode: operationMode.value,
      }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '创建硬链接失败')
    linkResult.value = data
  } catch (requestError) {
    linkError.value = requestError.message || '创建硬链接失败。'
  } finally { linkLoading.value = false }
}

async function searchMetadata() {
  metadataError.value = ''
  selectedMetadataId.value = null
  metadataResults.value = []
  if (!title.value.trim()) {
    error.value = '请先输入需要搜索的影视名称。'
    return
  }
  error.value = ''
  metadataOpen.value = true
  metadataConfigMode.value = false
  metadataLoading.value = true
  try {
    const response = await fetch(`/api/metadata/search?q=${encodeURIComponent(title.value.trim())}`)
    const data = await response.json()
    if (response.status === 503 || response.status === 401) {
      metadataConfigMode.value = true
      throw new Error(data.detail || '请先配置 TMDB 凭证')
    }
    if (!response.ok) throw new Error(data.detail || '搜索影视资料失败')
    metadataResults.value = data.results
    if (!data.results.length) metadataError.value = '没有找到相关结果，可以尝试英文名或其他关键词。'
  } catch (requestError) {
    metadataError.value = requestError.message || '搜索失败，请稍后重试。'
  } finally {
    metadataLoading.value = false
  }
}

function openMetadataConfig() {
  metadataError.value = ''
  tmdbToken.value = ''
  metadataConfigMode.value = true
  metadataOpen.value = true
}

async function saveTmdbConfig() {
  metadataError.value = ''
  if (!tmdbToken.value.trim()) { metadataError.value = '请输入 API Read Access Token。'; return }
  configSaving.value = true
  try {
    const response = await fetch('/api/metadata/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: tmdbToken.value.trim() }) })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '保存 TMDB 凭证失败')
    tmdbConfigured.value = true
    metadataConfigMode.value = false
    tmdbToken.value = ''
    await searchMetadata()
  } catch (requestError) {
    metadataError.value = requestError.message || '配置失败，请重试。'
  } finally { configSaving.value = false }
}

function applyMetadata() {
  const selected = metadataResults.value.find((item) => item.id === selectedMetadataId.value)
  if (!selected) return
  title.value = selected.title
  if (selected.year) year.value = selected.year
  mediaType.value = selected.media_type
  metadataOpen.value = false
}

watch(targetPath, (value) => {
  const normalized = value.trim()
  if (normalized) localStorage.setItem('media-linker-output-path', normalized)
})
watch(operationMode, () => { confirmOriginalChange.value = false; linkError.value = ''; linkResult.value = null })

onMounted(() => {
  connectLifecycle()
  checkHealth()
  checkMetadataStatus()
  targetPath.value = localStorage.getItem('media-linker-output-path') || ''
  window.setTimeout(() => checkForUpdates({ automatic: true }), 900)
})
</script>

<template>
  <div class="shell">
    <header class="hero">
      <div><span class="eyebrow">MEDIA LINKER · V{{ updateInfo.current_version }}</span><h1>影视硬链接整理工具</h1><p>扫描下载目录，为后续重命名、剧集归档和硬链接生成做好准备。</p></div>
      <div class="hero-actions">
        <span class="status" :class="{ online: apiOnline }"><i></i>{{ apiOnline ? '后端已连接' : '后端未连接' }}</span>
        <button class="settings-button" :class="{ 'has-update': updateInfo.update_available }" aria-label="打开设置" title="设置" @click="openSettings">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8.7a3.3 3.3 0 1 0 0 6.6 3.3 3.3 0 0 0 0-6.6Zm9 3.3-2.1-1.2c0-.5-.2-1-.4-1.5l.9-2.3-2.4-2.4-2.3.9c-.5-.2-1-.4-1.5-.4L12 3H8.7L7.5 5.1c-.5.1-1 .2-1.5.4l-2.3-.9L1.3 7l.9 2.3c-.2.5-.3 1-.4 1.5L0 12l1.8 1.2c.1.5.2 1 .4 1.5L1.3 17l2.4 2.4 2.3-.9c.5.2 1 .3 1.5.4L8.7 21H12l1.2-2.1c.5-.1 1-.2 1.5-.4l2.3.9 2.4-2.4-.9-2.3c.2-.5.4-1 .4-1.5L21 12Z"/></svg>
          <span v-if="updateInfo.update_available" class="update-dot"></span>
        </button>
      </div>
    </header>

    <main>
      <section class="steps">
        <div v-for="(label, index) in ['选择来源', '匹配信息', '预览整理', '生成链接']" :key="label" class="step" :class="{ active: step === index + 1, done: step > index + 1 }"><b>0{{ index + 1 }}</b><span>{{ label }}</span></div>
      </section>

      <section v-if="step === 1" class="panel">
        <div class="panel-title"><div><span>来源目录</span><h2>扫描并选择影视文件</h2></div><span class="tag">本地 / 已挂载 SMB</span></div>
        <form class="scan-form" @submit.prevent="scanFiles">
          <label><span>目录路径</span><div class="input-row"><input v-model="sourcePath" placeholder="点击“选择文件夹”，或输入 D:\Downloads" /><button type="button" class="picker-button" :disabled="pickingDirectory" @click="pickDirectory">{{ pickingDirectory ? '等待选择…' : '选择文件夹' }}</button><button type="submit" :disabled="loading">{{ loading ? '扫描中…' : '开始扫描' }}</button></div></label>
          <label class="check"><input v-model="recursive" type="checkbox" /> 扫描所有子目录</label>
        </form>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="summary"><div><small>发现视频</small><strong>{{ files.length }}</strong></div><div><small>已选择</small><strong>{{ selectedFiles.length }} 个 · {{ formatSize(totalSize) }}</strong></div><div><small>自动关联字幕</small><strong>{{ selectedSubtitleCount }} 个 SRT</strong></div></div>
        <div v-if="files.length" class="selection-tools"><span>默认不选择文件，请勾选本次需要整理的项目。</span><div><button class="text-button" @click="selectedPaths = new Set(files.map((file) => file.path))">全选</button><button class="text-button" @click="selectedPaths = new Set()">取消全选</button></div></div>
        <div class="table-wrap">
          <table v-if="files.length">
            <thead><tr><th class="select-cell"><input type="checkbox" :checked="allSelected" @change="toggleAll" /></th><th>文件名</th><th>格式</th><th>字幕</th><th>大小</th><th>完整路径</th></tr></thead>
            <tbody><tr v-for="file in files" :key="file.path" :class="{ chosen: selectedPaths.has(file.path) }" @click="toggleFile(file.path)"><td class="select-cell"><input type="checkbox" :checked="selectedPaths.has(file.path)" @click.stop @change="toggleFile(file.path)" /></td><td class="filename">{{ file.name }}</td><td>{{ file.extension }}</td><td><span v-if="file.subtitles?.length" class="subtitle-badge">{{ file.subtitles.length }} 个 SRT</span><span v-else>—</span></td><td>{{ formatSize(file.size) }}</td><td class="path">{{ file.path }}</td></tr></tbody>
          </table>
          <div v-else class="empty"><span>▶</span><p>输入目录并开始扫描</p><small>支持 MKV、MP4、AVI、MOV、WMV、M4V、TS、WEBM</small></div>
        </div>
        <div v-if="files.length" class="actions"><span>勾选需要整理的文件，然后继续。</span><button class="primary" :disabled="!selectedFiles.length" @click="goNext">下一步：匹配影视信息 →</button></div>
      </section>

      <section v-else-if="step === 2" class="panel">
        <div class="panel-title"><div><span>影视信息</span><h2>设置整理规则</h2></div><span class="tag">已选择 {{ selectedFiles.length }} 个文件</span></div>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="form-grid">
          <label><span>影视类型</span><select v-model="mediaType"><option value="tv">电视剧 / 动漫</option><option value="movie">电影</option></select></label>
          <label><span>影视名称</span><div class="metadata-input"><input v-model="title" placeholder="例如：进击的巨人" @keyup.enter="searchMetadata" /><button type="button" @click="searchMetadata">搜索中文资料</button><button type="button" class="config-button" @click="openMetadataConfig">{{ tmdbConfigured ? '已配置' : '配置 TMDB' }}</button></div></label>
          <label><span>年份（可选）</span><input v-model="year" inputmode="numeric" placeholder="例如：2023" /></label>
          <label v-if="mediaType === 'tv'"><span>季数</span><input v-model.number="season" type="number" min="0" /></label>
          <label v-if="mediaType === 'tv'"><span>起始集数</span><input v-model.number="startEpisode" type="number" min="1" /></label>
        </div>
        <div class="notice">系统将按照扫描结果中的文件顺序，从起始集数开始依次编号。下一步可逐项核对目标文件名。</div>
        <div class="actions"><button class="secondary" @click="step = 1; error = ''">← 返回选择文件</button><button class="primary" @click="buildPreview">下一步：生成重命名预览 →</button></div>
      </section>

      <section v-else-if="step === 3" class="panel">
        <div class="panel-title"><div><span>执行前检查</span><h2>重命名预览</h2></div><span class="tag">{{ mediaType === 'tv' ? '剧集批量编号' : '电影命名' }}</span></div>
        <div class="preview-summary"><strong>{{ title }}</strong><span>{{ mediaType === 'tv' ? `第 ${season} 季 · ${previews.length} 集` : year || '未填写年份' }}</span></div>
        <div class="table-wrap preview-table"><table><thead><tr><th>#</th><th>原文件名</th><th v-if="mediaType === 'tv'">集数</th><th>目标文件名</th><th>目标文件夹</th></tr></thead><tbody><template v-for="(item, index) in previews" :key="item.path"><tr><td>{{ index + 1 }}</td><td class="path">{{ item.name }}</td><td v-if="mediaType === 'tv'" class="episode">{{ item.episode }}</td><td class="filename">{{ item.targetName }}</td><td class="path">{{ item.targetFolder }}</td></tr><tr v-for="subtitle in item.subtitleTargets" :key="subtitle.path" class="subtitle-row"><td>↳</td><td class="path">{{ subtitle.name }}</td><td v-if="mediaType === 'tv'">字幕</td><td class="filename">{{ subtitle.targetName }}</td><td class="path">随视频自动关联</td></tr></template></tbody></table></div>
        <div class="notice">请检查文件排序和集数是否正确。此预览不会修改原始文件。</div>
        <div class="actions"><button class="secondary" @click="step = 2">← 返回修改信息</button><button class="primary" @click="goToGenerate">下一步：选择输出位置 →</button></div>
      </section>

      <section v-else-if="step === 4" class="panel">
        <div class="panel-title"><div><span>执行整理</span><h2>选择处理方式和输出位置</h2></div><span class="tag">输出目录会自动记忆</span></div>
        <div class="operation-options">
          <label :class="{ selected: operationMode === 'hardlink' }"><input v-model="operationMode" type="radio" value="hardlink" /><span><strong>创建硬链接（推荐）</strong><small>保留下载目录中的原始文件和名称，几乎不额外占用空间，适合继续做种。</small></span></label>
          <label class="danger-option" :class="{ selected: operationMode === 'move' }"><input v-model="operationMode" type="radio" value="move" /><span><strong>移动并重命名原文件</strong><small>原文件将离开当前目录并进入媒体库，可能导致磁力/PT 任务无法继续做种。</small></span></label>
        </div>
        <div class="target-picker">
          <label><span>输出根目录</span><div class="input-row"><input v-model="targetPath" placeholder="点击右侧按钮选择输出文件夹" /><button type="button" class="picker-button" :disabled="pickingTarget" @click="pickTargetDirectory">{{ pickingTarget ? '等待选择…' : '选择文件夹' }}</button></div></label>
        </div>
        <div class="summary"><div><small>准备处理</small><strong>{{ linkItems.length }} 个文件</strong></div><div><small>视频 / 字幕</small><strong>{{ previews.length }} / {{ selectedSubtitleCount }}</strong></div><div><small>原文件</small><strong>{{ operationMode === 'hardlink' ? '保持不变' : '移动并改名' }}</strong></div></div>
        <p v-if="linkError" class="error">{{ linkError }}</p>
        <div v-if="linkResult" class="success-message"><strong>{{ operationMode === 'hardlink' ? '硬链接创建完成' : '原文件移动并重命名完成' }}</strong><span>已成功处理 {{ linkResult.completed_count }} 个文件。</span></div>
        <div v-if="operationMode === 'hardlink'" class="notice"><strong>硬链接限制：</strong>来源文件和输出目录必须位于同一磁盘分区或同一 NAS 文件系统。已有同名目标文件时系统不会覆盖。</div>
        <div v-else class="danger-notice"><strong>注意：</strong>此操作会改变原始视频和字幕的位置及名称，可能导致正在做种的任务丢失文件。<label><input v-model="confirmOriginalChange" type="checkbox" /> 我确认移动并重命名原文件</label></div>
        <div class="output-preview"><small>预计输出示例</small><code v-if="previews.length">{{ targetPath || '输出根目录' }}\{{ previews[0].targetParts.join('\\') }}\{{ previews[0].targetName }}</code></div>
        <div class="actions"><button class="secondary" :disabled="linkLoading" @click="step = 3">← 返回预览</button><button class="primary" :class="{ 'danger-primary': operationMode === 'move' }" :disabled="linkLoading || Boolean(linkResult) || (operationMode === 'move' && !confirmOriginalChange)" @click="createLinks">{{ linkLoading ? '正在处理…' : (linkResult ? '处理完成' : (operationMode === 'hardlink' ? '开始生成硬链接' : '移动并重命名原文件')) }}</button></div>
      </section>
    </main>

    <div v-if="metadataOpen" class="modal-backdrop" @click.self="metadataOpen = false">
      <section class="metadata-modal" role="dialog" aria-modal="true" aria-label="影视资料搜索结果">
        <header class="modal-header"><div><span>TMDB · 中文资料</span><h2>{{ metadataConfigMode ? '配置 TMDB' : '选择正确的影视信息' }}</h2><p>{{ metadataConfigMode ? '凭证仅保存在这台电脑上' : `搜索关键词：${title}` }}</p></div><button class="close-button" aria-label="关闭" @click="metadataOpen = false">×</button></header>
        <div class="modal-body">
          <div v-if="metadataConfigMode" class="tmdb-config">
            <h3>粘贴 API Read Access Token</h3>
            <p>登录 TMDB 后，在账户的 API 设置中申请并复制“API Read Access Token”。搜索将固定使用简体中文（zh-CN）。</p>
            <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noreferrer">打开 TMDB API 设置页面 ↗</a>
            <label><span>API Read Access Token</span><textarea v-model="tmdbToken" rows="5" placeholder="eyJhbGciOiJIUzI1NiJ9…"></textarea></label>
            <p v-if="metadataError" class="config-error">{{ metadataError }}</p>
          </div>
          <div v-else-if="metadataLoading" class="search-state"><span class="spinner"></span><p>正在搜索中文影视资料…</p></div>
          <div v-else-if="metadataError" class="search-state error-state"><p>{{ metadataError }}</p><button class="secondary" @click="searchMetadata">重新搜索</button></div>
          <div v-else class="metadata-results">
            <label v-for="item in metadataResults" :key="item.id" class="metadata-card" :class="{ selected: selectedMetadataId === item.id }">
              <input v-model="selectedMetadataId" type="radio" :value="item.id" />
              <div class="poster"><img v-if="item.poster" :src="item.poster" :alt="item.title" /><span v-else>暂无海报</span></div>
              <div class="metadata-copy"><div class="result-title"><strong>{{ item.title }}</strong><span>{{ item.year || '年份未知' }} · {{ item.media_type_label }}</span></div><p v-if="item.original_title && item.original_title !== item.title" class="original-title">{{ item.original_title }}</p><p class="result-meta">{{ [item.country, item.language, ...item.genres].filter(Boolean).join(' · ') || '暂无分类信息' }}</p><p class="overview">{{ item.overview || '暂无中文简介' }}</p><small>来源：{{ item.provider }} · ID {{ item.id }}</small></div>
            </label>
          </div>
        </div>
        <footer class="modal-footer"><span>{{ metadataConfigMode ? 'TMDB 凭证不会显示在前端搜索请求中' : (selectedMetadataId ? '已选择一条资料' : '请选择正确的搜索结果') }}</span><div><button class="secondary" @click="metadataOpen = false">取消</button><button v-if="metadataConfigMode" class="primary" :disabled="configSaving" @click="saveTmdbConfig">{{ configSaving ? '验证并保存中…' : '验证并保存' }}</button><button v-else class="primary" :disabled="!selectedMetadataId" @click="applyMetadata">完成并填充</button></div></footer>
      </section>
    </div>

    <div v-if="settingsOpen" class="modal-backdrop" @click.self="settingsOpen = false">
      <section class="settings-modal" role="dialog" aria-modal="true" aria-label="软件设置">
        <header class="modal-header">
          <div><span>MEDIA LINKER · 设置</span><h2>{{ settingsView === 'menu' ? '设置' : '软件信息' }}</h2><p>{{ settingsView === 'menu' ? '管理 MediaLinker 的软件选项' : '版本信息与在线更新' }}</p></div>
          <button class="close-button" aria-label="关闭设置" @click="settingsOpen = false">×</button>
        </header>
        <div v-if="settingsView === 'menu'" class="settings-menu">
          <button class="settings-option" @click="settingsView = 'about'">
            <span class="settings-option-icon">i</span>
            <span><strong>软件信息</strong><small>查看版本号、检查更新和发布信息</small></span>
            <b>›</b>
          </button>
        </div>
        <div v-else class="about-view">
          <button class="settings-back" @click="settingsView = 'menu'">← 返回设置</button>
          <div class="app-identity"><div class="app-mark">ML</div><div><strong>MediaLinker</strong><span>影视硬链接整理工具</span></div></div>
          <div class="version-grid">
            <div><small>本地版本</small><strong>v{{ updateInfo.current_version }}</strong></div>
            <div><small>GitHub 最新版本</small><strong>{{ updateInfo.latest_version ? `v${updateInfo.latest_version}` : '尚未查询' }}</strong></div>
            <div><small>运行平台</small><strong>{{ platformLabel }}</strong></div>
          </div>
          <div class="update-status" :class="`state-${updateState}`">
            <span v-if="updateState === 'checking' || updateState === 'downloading'" class="spinner small-spinner"></span>
            <i v-else></i>
            <div><strong>{{ updateState === 'error' ? '更新检查遇到问题' : (updateInfo.update_available ? '软件更新' : '版本状态') }}</strong><p>{{ updateMessage || '打开软件时会自动检查 GitHub 最新版本。' }}</p></div>
          </div>
          <div class="about-actions">
            <a v-if="updateInfo.release_url" class="release-link" :href="updateInfo.release_url" target="_blank" rel="noreferrer">查看 Release</a>
            <button class="primary" :disabled="['checking', 'downloading', 'restarting'].includes(updateState)" @click="checkForUpdates({ force: true })">{{ updateState === 'checking' ? '查询中…' : '手动查询更新' }}</button>
            <button v-if="updateInfo.auto_update_blocked" class="retry-update" :disabled="['downloading', 'restarting'].includes(updateState)" @click="retrySoftwareUpdate">重试更新</button>
          </div>
          <p v-if="updateInfo.last_update_log" class="update-log-path">安装日志：{{ updateInfo.last_update_log }}</p>
          <p class="update-help">Windows 安装版、绿色版和 Linux 便携版会自动下载对应更新并重新启动。Flatpak 版会显示最新版本和下载入口。</p>
        </div>
      </section>
    </div>

    <div v-if="updateState === 'downloading' || updateState === 'restarting'" class="update-toast"><span class="spinner small-spinner"></span><div><strong>MediaLinker 正在更新</strong><p>{{ updateMessage }}</p></div></div>
    <div v-else-if="updateState === 'error' && updateMessage" class="update-toast update-error-toast"><i></i><div><strong>MediaLinker 更新失败</strong><p>{{ updateMessage }}</p><small v-if="updateInfo.last_update_log">日志：{{ updateInfo.last_update_log }}</small></div></div>
  </div>
</template>
