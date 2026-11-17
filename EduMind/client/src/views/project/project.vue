<template>
  <div class="flex-col flex flex-1 min-h-0 h-full overflow-hidden text-gray-700">
    <div class="flex-1 min-h-0 overflow-y-auto scroller" v-if="currentPage === 'Files'">
      <FilesPage ref="fileUploadTrigger" />
    </div>
    <div class="flex-1 min-h-0" v-if="currentPage === 'Chat'">
      <ChatPage @open-file-upload="handleOpenFilesAndUpload" />
    </div>
    <div class="flex-1 min-h-0 overflow-y-auto scroller" v-if="currentPage === 'Questions'">
      <QuestionsPage />
    </div>
  </div>
</template>

<script setup>
  import { ref, watch, onMounted } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import FilesPage from './files.vue'
  import ChatPage from './chat.vue'
  import QuestionsPage from './questions.vue'
  import { initProject } from '../../../api/chat'
  import { checkHealth } from '../../../api/lightrag'

  const route = useRoute()
  const router = useRouter()
  const pages = ['Files', 'Chat', 'Questions']
  const currentPage = ref('Chat')
  const fileUploadTrigger = ref(null)

  const setPage = (page) => {
    currentPage.value = page
    if (route.hash !== `#${page}`) {
      router.replace({ hash: `#${page}` })
    }
  }

  const handleOpenFilesAndUpload = () => {
    setPage('Files')
    nextTick(() => {
      fileUploadTrigger.value?.openUploadModal?.()
    })
  }

  const updatePageFromHash = async () => {
    const hash = route.hash?.replace('#', '')
    if (pages.includes(hash)) {
      currentPage.value = hash
    } else {
      currentPage.value = 'Chat'
    }
  }

  const checkServerState = async () => {
    try {
      const data = await checkHealth()
      const path = data.working_directory
      const match = path.match(/\/app\/files\/project\/([^/]+)\/rag_storage/)
      const extractedId = match ? match[1] : null
      const currentId = route.params.project_id
      if (extractedId === currentId) {
        console.log('✅ Project ID matches:', extractedId)
      } else {
        console.warn('Switching to New Project')
        await initProject(currentId)
        console.log('✅ Project initialized:', currentId)
      }
    } catch (error) {
      console.error('Health check failed:', error)
      throw error
    }
  }

  onMounted(async () => {
    try {
      await checkServerState()
      await updatePageFromHash()
    } catch (err) {
      console.error('Initialization failed:', err)
    }
  })

  watch(
    () => [route.params.project_id, route.hash],
    async () => {
      try {
        await checkServerState()
        await updatePageFromHash()
      } catch (err) {
        console.error('Server State Checkup Failed with Error:', err)
      }
    }
  )
</script>
