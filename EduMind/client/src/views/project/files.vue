<template>
  <!-- Project Files Page -->
  <div class="flex flex-col flex-1 min-h-0 p-4">
    <h4 class="text-gray-700 ml-2 mb-4">Content Management</h4>

    <!-- Button Toolbar -->
    <div class="flex justify-between items-center mb-6">
      <!-- Left Buttons -->
      <div class="flex space-x-2">
        <button
          @click="createNewScan"
          :disabled="scanning"
          class="flex items-center space-x-2 hover:bg-gray-200 border-1 border-gray-400 px-2 py-2 transition-colors disabled:opacity-50"
        >
          <Combine class="w-5 h-5 animate-spin" v-if="scanning" />
          <Combine class="w-5 h-5" v-else />
          <span>{{ scanning ? 'Scanning…' : 'Scan Files' }}</span>
        </button>
        <button
          @click="openPipelineStatus"
          class="flex items-center space-x-2 hover:bg-gray-200 border-1 border-gray-400 px-2 py-2 transition-colors"
        >
          <RefreshCcw class="w-5 h-5" />
          <span>Pipeline Status</span>
        </button>
      </div>

      <!-- Right Buttons -->
      <div class="flex space-x-2 items-center">
        <button
          class="flex items-center space-x-2 bg-blue-900 text-white border-1 border-blue-900 hover:bg-blue-800 px-2 py-2 transition-colors cursor-pointer"
          @click="openAddLinks"
        >
          <Globe class="w-5 h-5" />
          <span>Add Web Links</span>
        </button>
        <!-- Upload Files: clicking this label triggers the hidden <input> -->
        <label
          for="fileUploader"
          class="flex items-center space-x-2 bg-green-900 text-white border-1 border-green-900 hover:bg-green-800 px-2 py-2 transition-colors cursor-pointer"
        >
          <UploadCloudIcon class="w-5 h-5" />
          <span>Upload Files</span>
        </label>
        <!-- Hidden file input, bound to handleFileChange -->
        <input
          id="fileUploader"
          type="file"
          multiple
          class="hidden"
          ref="fileInputRef"
          @change="handleFileChange"
        />
        <button
          @click="openClearAll"
          class="flex items-center space-x-2 hover:bg-gray-200 border-1 border-gray-400 px-2 py-2 transition-colors"
        >
          <Eraser class="w-5 h-5" />
          <span>Clear All</span>
        </button>
      </div>
    </div>
    <div class="flex-1 overflow-auto">
      <!-- Data Table -->
      <Table :columns="columns" :rows="filesList" @row-click="removeFile" />
    </div>
  </div>
  <!-- ──────────────────────────────────────────────────────────────────────────────── -->
  <!-- Modal: Pipeline Status Dialog                                                 -->
  <!-- ──────────────────────────────────────────────────────────────────────────────── -->
  <transition name="fade">
    <div
      v-if="showPipelineStatus"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <!-- Modal container with same FIXED width w-96 and height h-96 -->
      <div class="bg-white -2xl w-200 h-150 mx-4 flex flex-col overflow-hidden rounded-lg">
        <!-- Modal Header -->
        <div class="flex items-center justify-between px-3 py-3">
          <h4 class="ml-2 mr-2">Scan Status</h4>

          <!-- Close “×” button -->
          <button @click="closePipelineStatus" class="text-gray-400 hover:text-gray-300 px-1 py-1">
            <XIcon class="w-5 h-5" />
          </button>
        </div>

        <div class="flex flex-col space-y-3 px-3 mt-3">
          <!-- Pipeline Status with Dot -->
          <div class="flex items-center space-x-3 ml-3">
            <p class="font-medium">
              {{ busy ? 'Pipeline Busy' : 'Pipeline Idle' }}
            </p>
            <div :class="['w-3 h-3 rounded-full', busy ? 'bg-green-500' : 'bg-gray-400']"></div>
          </div>

          <!-- Job Name -->
          <div class="flex space-x-2">
            <span class="font-semibold text-gray-700 ml-3">Job Name:</span>
            <span class="text-gray-600">{{ job_name }}</span>
          </div>

          <div class="flex justify-between items-center px-3 py-2 border-b border-gray-200">
            <!-- Start Time -->
            <div class="flex space-x-2">
              <span class="font-semibold text-gray-700">Start Time:</span>
              <span class="text-gray-600">{{ job_start }}</span>
            </div>

            <!-- Progress -->
            <div class="flex space-x-2">
              <span class="font-semibold text-gray-700">Progress:</span>
              <span class="text-gray-600">{{ cur_batch }}/{{ batchs }} batch</span>
            </div>
          </div>
        </div>

        <div class="flex flex-col space-y-3 px-3 mt-3">
          <!-- Latest Message Full-Width Line -->
          <div class="w-full">
            <span class="font-semibold text-gray-700 ml-1">Latest Message:</span>
            <div
              class="font-mono mt-1 text-gray-100 bg-gray-800 -md px-3 py-2 w-full break-words whitespace-pre-wrap"
            >
              {{ latest_message || 'Waiting for User Action' }}
            </div>
          </div>
        </div>
        <!-- Previous Messages (fills remaining space with scroll) -->
        <div class="flex flex-col px-3 pb-3 pt-2 flex-1 min-h-0">
          <span class="font-semibold text-gray-700 ml-1 mb-1">Previous Messages:</span>
          <div
            class="flex-1 font-mono text-gray-100 bg-gray-800 -md px-3 py-2 w-full overflow-auto break-words whitespace-pre-wrap scroller"
          >
            <div v-for="(msg, idx) in history_messages" :key="idx">
              {{ msg }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </transition>
  <!-- ──────────────────────────────────────────────────────────────────────────────── -->
  <!-- Modal: Clear All Dialog                                                 -->
  <!-- ──────────────────────────────────────────────────────────────────────────────── -->
  <transition name="fade">
    <div
      v-if="showClearAll"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <!-- Modal container -->
      <div class="bg-white -2xl w-150 h-90 mx-4 flex flex-col overflow-hidden rounded-lg">
        <!-- Modal Header -->
        <div class="flex items-center justify-between px-3 py-3">
          <h4 class="font-semibold ml-2 mr-2 text-red-600">Clear Documents</h4>
          <button @click="closeClearAll" class="text-gray-400 hover:text-gray-300 px-1 py-1">
            <XIcon class="w-5 h-5" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="flex flex-col flex-1 justify-center space-y-3 px-6 text-gray-700">
          <p>This will remove all documents from the system.</p>
          <p class="text-red-600 font-semibold">
            WARNING: This action will permanently delete all documents and cannot be undone!
          </p>
          <p>Type <code class="font-mono bg-gray-100 px-1">yes</code> to confirm:</p>
          <input
            v-model="confirmText"
            type="text"
            placeholder="Type 'yes' to confirm"
            class="border border-gray-300 px-3 py-2 w-full"
          />
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-end px-6 py-4 space-x-2 border-t border-gray-200">
          <button
            @click="clearAllConfirmed"
            :disabled="confirmText.trim().toLowerCase() !== 'yes'"
            class="bg-red-600 hover:bg-red-500 text-white px-4 py-2 transition-colors disabled:opacity-50"
          >
            Clear All
          </button>
          <button
            @click="closeClearAll"
            class="bg-gray-300 text-gray-700 hover:bg-gray-400 px-4 py-2 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </transition>
  <!-- ──────────────────────────────────────────────────────────────────────────────── -->
  <!-- Modal: Add Web Links                                              -->
  <!-- ──────────────────────────────────────────────────────────────────────────────── -->
  <transition name="fade">
    <div
      v-if="showAddLinks"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <div class="bg-white -2xl w-150 h-100 mx-4 flex flex-col overflow-hidden rounded-lg">
        <!-- Modal Header -->
        <div class="flex items-center justify-between px-3 py-3">
          <h4 class="ml-2 mr-2">Add Web Resources</h4>
          <button @click="closeAddLinks" class="text-gray-400 hover:text-gray-300 px-1 py-1">
            <XIcon class="w-5 h-5" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="flex-1 flex flex-col space-y-2 px-4 py-3 overflow-y-auto scroller">
          <div
            v-for="(link, idx) in webLinks"
            :key="link.id"
            class="flex items-center space-x-2 mb-2"
          >
            <input
              v-model="link.url"
              type="url"
              placeholder="Enter web resource link"
              class="flex-1 border h-10 px-3 py-2 focus:outline-none focus:ring-2 transition-all duration-150"
              :class="{
                'border-red-500 ring-2 ring-red-200': webLinksErrors[idx],
                'border-gray-300 focus:ring-green-800': !webLinksErrors[idx],
              }"
              :autofocus="idx === webLinks.length - 1 && webLinks.length > 1"
            />
            <button @click="removeWebLink(idx)" v-if="webLinks.length > 1" title="Remove">
              <XIcon class="w-5 h-5 text-gray-300 hover:text-gray-400" />
            </button>
          </div>
          <!-- Error Message: -->
          <div v-if="webLinksErrors[idx]" class="text-xs text-red-600 ml-1">
            Please enter a valid link (must start with http:// or https://)
          </div>
          <button
            class="flex items-center h-10 space-x-1 border border-gray-200 bg-gray-100 hover:bg-gray-200 px-3 self-start mt-1 transition-all duration-300"
            @click="addWebLink"
          >
            <Plus class="w-5 h-5" />
            Add Link
          </button>
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-end space-x-2 px-6 py-4 border-t border-gray-300">
          <button
            @click="closeAddLinks"
            class="bg-gray-200 text-gray-700 hover:bg-gray-300 px-4 py-2 h-10"
          >
            Cancel
          </button>
          <button
            @click="saveWebLinks"
            class="bg-blue-900 text-white hover:bg-blue-800 px-4 py-2 h-10 flex items-center justify-center"
            :disabled="!canSaveLinks || savingLinks"
          >
            <svg
              v-if="savingLinks"
              class="animate-spin h-5 w-5 text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              ></path>
            </svg>
            <span v-if="!savingLinks">Save</span>
            <span v-else>Saving…</span>
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
  import { ref, onMounted, computed, defineExpose, watch, onUnmounted } from 'vue'
  import { useToast } from 'vue-toast-notification'
  import axios from 'axios'
  import { UploadCloudIcon, Combine, RefreshCcw, Eraser, XIcon, Globe, Plus } from 'lucide-vue-next'
  import Table from '@/components/Table.vue'
  import {
    scanNewDocuments,
    getPipelineStatus,
    getDocuments,
    clearDocuments,
    clearCache,
    uploadDocument,
    insertLinks,
  } from '../../../api/lightrag'

  const toast = useToast()
  function showSuccess() {
    toast.success('Scan started successfully')
  }

  function showError(message) {
    toast.error(`Scan failed: ${message}`)
  }

  const fileInputRef = ref(null)

  function clickUpload() {
    fileInputRef.value?.click()
  }

  defineExpose({ clickUpload })

  const SERVER_URL = import.meta.env.VITE_SERVER_URL

  const filesList = ref([])

  function formatDate(dateStr) {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    })
  }

  const columns = [
    { label: 'Content', key: 'file_path', link: true, external: true, width: '60%' },
    { label: 'Status', key: 'status', type: 'status', filterable: true },
    { label: 'Uploaded At', key: 'uploaded_at', sortable: true },
    { label: 'Error', key: 'error', width: '5%' },
  ]

  const scanning = ref(false)
  async function createNewScan() {
    scanning.value = true
    try {
      const resp = await scanNewDocuments()
      showSuccess()
    } catch (err) {
      const message = err?.response?.data?.error || err.message || 'Scan failed'
      showError()
    } finally {
      scanning.value = false
    }
  }

  function handleFileChange(e) {
    const selectedFiles = Array.from(e.target.files)
    if (!selectedFiles.length) return

    selectedFiles.forEach((file) => {
      const tempId = crypto.randomUUID()
      filesList.value.unshift({
        id: tempId,
        name: file.name.length > 30 ? file.name.slice(0, 30) + '…' : file.name,
        status: 'Uploading…',
        uploading: true,
        uploaded_at: '',
      })

      uploadDocument(file, (percent) => {
        const idx = filesList.value.findIndex((f) => f.id === tempId)
        if (idx !== -1) {
          filesList.value[idx].status = `Uploading… (${percent}%)`
        }
      })
        .then((res) => {
          const idx = filesList.value.findIndex((f) => f.id === tempId)
          if (idx !== -1) {
            filesList.value[idx] = {
              id: res.id || tempId,
              name: file.name.length > 30 ? file.name.slice(0, 30) + '…' : file.name,
              status: res.status || 'Uploaded',
              summary: res.content_summary || '',
              uploaded_at: formatDate(new Date()),
              error: res.error || '',
            }
          }
        })
        .catch((err) => {
          const idx = filesList.value.findIndex((f) => f.id === tempId)
          if (idx !== -1) {
            filesList.value[idx].status = 'Failed'
            filesList.value[idx].uploading = false
            filesList.value[idx].error = err?.message || 'Upload failed'
          }
        })
    })

    // Clear input value
    e.target.value = ''
  }

  let pollingInterval = null

  onMounted(() => {
    fetchFiles()
    pollingInterval = setInterval(fetchFiles, 3000) // every 3 seconds
  })

  onUnmounted(() => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      pollingInterval = null
    }
  })

  // Delete a file row both locally and via API
  async function removeFile(row) {
    const id = row.id
    try {
      await axios.delete(`${SERVER_URL}/api/v1/file/${id}`)
      filesList.value = filesList.value.filter((f) => f.id !== id)
    } catch (err) {
      console.error('Error deleting file:', err.response?.data || err.message)
    }
  }

  // Initial fetch of existing files on mount
  async function fetchFiles() {
    try {
      const resp = await getDocuments()

      console.log(resp)

      // Flatten all statuses into a single array
      const allDocs = Object.values(resp.statuses).flat()

      filesList.value = allDocs.map((doc) => {
        const parts = doc.file_path.split('/')
        const filename = parts[parts.length - 1]
        return {
          id: doc.id,
          file_path: doc.file_path,
          status: doc.status.charAt(0).toUpperCase() + doc.status.slice(1),
          summary: doc.content_summary,
          content_length: doc.content_length || 0,
          chunks_count: doc.chunks_count || 0,
          uploaded_at: formatDate(doc.created_at),
          error: doc.error || '',
        }
      })
    } catch (err) {
      console.error('Error fetching files:', err.response?.data || err.message)
    }
  }

  onMounted(fetchFiles)

  const showPipelineStatus = ref(false)

  const busy = ref(false)
  const job_name = ref('')
  const job_start = ref('')
  const batchs = ref(0)
  const cur_batch = ref(0)
  const latest_message = ref('')
  const history_messages = ref([])

  function openPipelineStatus() {
    showPipelineStatus.value = true
  }

  function closePipelineStatus() {
    showPipelineStatus.value = false
  }

  const fetchStatus = async () => {
    try {
      const data = await getPipelineStatus()
      busy.value = data.busy
      job_name.value = data.job_name
      job_start.value = data.job_start
      cur_batch.value = data.cur_batch
      batchs.value = data.batchs
      latest_message.value = data.latest_message
      history_messages.value = data.history_messages
    } catch (err) {
      toast.error(`Failed to fetch status: ${errorMessage(err)}`)
    }
  }

  let intervalId = null

  watch(showPipelineStatus, async (isOpen) => {
    if (isOpen) {
      await fetchStatus() // fetch immediately
      if (intervalId) clearInterval(intervalId) // clear just in case
      intervalId = setInterval(fetchStatus, 1000)
    } else {
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }
  })

  const showClearAll = ref(false)
  const confirmText = ref('')

  function openClearAll() {
    showClearAll.value = true
  }

  function closeClearAll() {
    showClearAll.value = false
  }

  async function clearAllConfirmed() {
    try {
      await clearDocuments()
      await clearCache()
      toast.success('All documents cleared.')
      closeClearAll()
      fetchFiles() // reload the file list
    } catch (err) {
      console.error(err)
      toast.error('Failed to clear documents.')
    }
  }

  const showAddLinks = ref(false)

  function openAddLinks() {
    showAddLinks.value = true
  }
  function closeAddLinks() {
    showAddLinks.value = false
  }

  const webLinks = ref([{ id: crypto.randomUUID(), url: '' }])
  const savingLinks = ref(false)

  function addWebLink() {
    webLinks.value.push({ id: crypto.randomUUID(), url: '' })
  }

  function removeWebLink(idx) {
    if (webLinks.value.length > 1) {
      webLinks.value.splice(idx, 1)
    }
  }

  const canSaveLinks = computed(
    () =>
      webLinks.value.length > 0 &&
      webLinks.value.every((link) => !!link.url && isValidHttpUrl(link.url))
  )

  async function saveWebLinks() {
    savingLinks.value = true
    try {
      await insertLinks(webLinks.value.map((l) => l.url))
      toast.success('Links added successfully.')
      closeAddLinks()
      fetchFiles()
      webLinks.value = [{ id: crypto.randomUUID(), url: '' }]
    } catch (err) {
      toast.error(err?.response?.data?.error || err.message || 'Failed to add links')
    } finally {
      savingLinks.value = false
    }
  }

  // Simple URL validation
  function isValidHttpUrl(string) {
    try {
      let url = new URL(string)
      return url.protocol === 'http:' || url.protocol === 'https:'
    } catch (_) {
      return false
    }
  }

  const webLinksErrors = computed(() =>
    webLinks.value.map((link) => link.url && !isValidHttpUrl(link.url))
  )

  watch(showAddLinks, (open) => {
    if (open) {
      if (webLinks.value.length === 0) webLinks.value = [{ id: crypto.randomUUID(), url: '' }]
    }
  })
</script>

<style scoped>
  .fade-enter-active,
  .fade-leave-active {
    transition: opacity 0.2s ease;
  }
  .fade-enter-from,
  .fade-leave-to {
    opacity: 0;
  }
  .fade-enter-to,
  .fade-leave-from {
    opacity: 1;
  }

  /* Scrollbar styling for any overflow containers */
  .scroller::-webkit-scrollbar {
    width: 8px;
  }
  .scroller::-webkit-scrollbar-track {
    background: transparent;
  }
  .scroller::-webkit-scrollbar-thumb {
    background-color: #9298a0;
    border-radius: 4px;
  }
  .scroller::-webkit-scrollbar-thumb:hover {
    background-color: #a9b8ce;
  }
</style>
