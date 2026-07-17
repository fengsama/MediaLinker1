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
  checkHealth()
  checkMetadataStatus()
  targetPath.value = localStorage.getItem('media-linker-output-path') || ''
})
</script>

<template>
  <div class="shell">
    <header class="hero">
      <div><span class="eyebrow">MEDIA LINKER · V0.3</span><h1>影视硬链接整理工具</h1><p>扫描下载目录，为后续重命名、剧集归档和硬链接生成做好准备。</p></div>
      <span class="status" :class="{ online: apiOnline }"><i></i>{{ apiOnline ? '后端已连接' : '后端未连接' }}</span>
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
  </div>
</template>
