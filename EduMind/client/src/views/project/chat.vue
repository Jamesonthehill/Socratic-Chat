<template>
  <div class="flex-1 mx-auto w-2xl max-w-2xl mt-[15vh] space-y-4">
    <!-- Header: centered project name -->
    <header class="flex items-center justify-center space-x-2">
      <h1>{{ projectName }}</h1>
    </header>

    <!-- Chat Input Area -->
    <div>
      <ChatInput
        v-model="newMessage"
        :disabled="false"
        placeholder="New chat in this project"
        @send="initChat"
        class="w-full"
      />
    </div>

    <div class="flex-1 w-full">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full">
        <!-- Project files card -->
        <div
          class="flex items-center justify-between bg-gray-200 shadow-sm hover:bg-gray-300 transition-colors rounded-4xl p-4 cursor-pointer"
          @click="$emit('open-file-upload')"
        >
          <div class="flex space-x-3">
            <FolderIcon class="w-5 h-5 text-indigo-600" />
            <div class="space-y-1">
              <h4 class="">Project Resources</h4>
              <p>{{ projectFileCount }} file(s)</p>
            </div>
          </div>
          <ChevronRight class="w-5 h-5 text-gray-500" />
        </div>
        <!-- Add instructions card -->
        <div
          class="flex items-center justify-between bg-gray-200 shadow-sm hover:bg-gray-300 transition-colors rounded-4xl p-4 cursor-pointer"
          @click="openInstructionsEditor"
        >
          <div class="flex space-x-3">
            <EditIcon class="w-5 h-5 text-yellow-600" />
            <div class="space-y-1">
              <h4 class="">Add Instructions</h4>
              <p v-if="instructionsText" class="text-gray-600 max-w-50 truncate">
                {{ instructionsText }}
              </p>
              <p v-else class="italic">No instructions added yet</p>
            </div>
          </div>
          <ChevronRight class="w-5 h-5 text-gray-500" />
        </div>
      </div>
    </div>

    <!-- Chat History Header -->
    <div class="space-y-4">
      <h2 class="text-gray-400 text-center text-sm">Chat History</h2>
    </div>
    <div class="justify-center max-h-64 overflow-y-auto space-y-2 scroller">
      <div
        v-for="session in sortedSessions"
        :key="session.id"
        class="flex justify-between items-center bg-gray-200 rounded-2xl ml-2 px-4 py-3 shadow-sm cursor-pointer hover:bg-gray-300 transition-colors"
        @click="goToSession(session.id)"
      >
        <span class="text-gray-800 truncate max-w-[70%]">
          {{ session.topic || 'Untitled Chat' }}
        </span>
        <span class="text-gray-500 italic">
          {{ formatDate(session.created_at) }}
        </span>
      </div>
    </div>
  </div>
  <transition name="fade">
    <div
      v-if="showInstructionModal"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <!-- Modal container with same FIXED width w-96 and height h-96 -->
      <div class="bg-white rounded-2xl w-150 h-96 mx-4 flex flex-col overflow-hidden">
        <!-- Modal Header -->
        <div class="flex items-center justify-between px-3 py-3">
          <h3 class="ml-2 mr-2">Add Instructions</h3>

          <!-- Close “×” button -->
          <button
            @click="closeInstructionsEditor"
            class="text-gray-400 hover:text-gray-300 px-1 py-1 rounded-full"
          >
            <XIcon class="w-5 h-5" />
          </button>
        </div>

        <div class="text-sm flex flex-col items-left justify-between ml-2 mr-2 mt-2 px-3">
          <p>How can EduMind best help you with this project?</p>
          <p>
            You can ask EduMind to focus on certain topics, or ask it to use a certain tone or
            format for responses.
          </p>
        </div>

        <!-- Modal Body -->
        <div class="p-4 flex-1">
          <textarea
            v-model="draftInstructionsText"
            placeholder="E.g. ''The questions should include a substantial number of code examples to effectively assess students' understanding of software development.''"
            class="w-full h-full resize-none rounded-2xl border border-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-800 scroller"
          ></textarea>
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-end px-3 py-3 space-x-2">
          <button
            @click="saveInstructions"
            class="bg-green-800 hover:bg-green-700 text-white font-medium px-4 py-2 rounded-full transition-colors"
          >
            Save
          </button>
          <button
            @click="closeInstructionsEditor"
            class="bg-gray-300 text-gray-500 hover:bg-gray-400 font-medium px-4 py-2 rounded-full transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
  import { ref, watch, onMounted, computed } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import ChatInput from '@/components/ChatInput.vue'
  import { FolderIcon, EditIcon, XIcon, ChevronRight } from 'lucide-vue-next'
  import { useUserStore } from '@/stores/user'
  import { useChatStore } from '@/stores/chats'
  import { getDocuments } from '../../../api/lightrag'
  import {
    createNewSession,
    createInstructions,
    getProject,
    getSessions,
    getProjects,
  } from '../../../api/chat'

  const route = useRoute()
  const router = useRouter()
  const chatStore = useChatStore()
  const projectName = ref('')
  const projectFileCount = ref(0)
  const newMessage = ref('')
  const sessions = ref([])
  const showInstructionModal = ref(false)
  const instructionsText = ref('')
  const draftInstructionsText = ref('')
  const emit = defineEmits(['open-file-upload'])

  onMounted(async () => {
    await fetchProjectDetails()
    await fetchSessions()
    await fetchFiles()
  })

  watch(
    () => route.params.project_id,
    async (projectId) => {
      const userStore = useUserStore()
      const user_id = userStore.user_id
      const data = await getProjects(user_id)
      if (data.projects.length === 0) {
        return
      }
      if (projectId == null || projectId === 'DEFAULT') return
      await fetchProjectDetails()
      await fetchSessions()
      await fetchFiles()
    },
    { immediate: true }
  )

  async function initChat() {
    if (!newMessage.value.trim()) return
    const user_message = newMessage.value
      .trim()
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
    const userStore = useUserStore()
    const user_id = userStore.user_id
    const data = await createNewSession(user_id, route.params.project_id)
    chatStore.setInitialMessage(user_message)
    router.push(`/chat/${data.session_id}/p/${route.params.project_id}`)
    newMessage.value = ''
    try {
    } catch (e) {
      console.error(e)
    }
  }

  function openInstructionsEditor() {
    draftInstructionsText.value = instructionsText.value
    showInstructionModal.value = true
  }

  function closeInstructionsEditor() {
    showInstructionModal.value = false
  }

  async function saveInstructions() {
    instructionsText.value = draftInstructionsText.value
    await createInstructions(route.params.project_id, instructionsText.value)
    showInstructionModal.value = false
  }

  async function fetchFiles() {
    try {
      const resp = await getDocuments()
      const allDocs = Object.values(resp.statuses).flat()
      projectFileCount.value = allDocs.length
    } catch (err) {
      console.error('Error fetching file count:', err.response?.data || err.message)
      projectFileCount.value = 0
    }
  }

  async function fetchSessions() {
    try {
      const userStore = useUserStore()
      const user_id = userStore.user_id
      const data = await getSessions(user_id, route.params.project_id)
      sessions.value = (data.sessions || [])
        .slice()
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    } catch (err) {
      console.error('Failed to fetch sessions:', err.response?.data || err.message)
      sessions.value = []
    }
  }

  const sortedSessions = computed(() =>
    [...sessions.value].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  )

  function formatDate(dateStr) {
    const date = new Date(dateStr)
    return date.toLocaleString(undefined, {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    })
  }

  function goToSession(sessionId) {
    const chatStore = useChatStore()
    chatStore.setSessionId(sessionId)
    chatStore.clearMessages()
    router.push(`/chat/${sessionId}/p/${route.params.project_id}`)
  }

  async function fetchProjectDetails() {
    try {
      const data = await getProject(route.params.project_id)
      const project = data.project
      instructionsText.value = project.instructions || ''
      projectName.value = project.name || 'Untitled'
    } catch (error) {
      console.error('Error fetching project details:', error.response?.data || error.message)
    }
  }
</script>

<style scoped>
  /* Fade transition for modal backdrop + container */
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
</style>
