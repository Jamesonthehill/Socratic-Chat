<template>
  <div class="flex flex-row flex-1 h-full min-h-0">
    <!-- Chat/Main Area (left) -->
    <div ref="chat" class="flex flex-col flex-1 text-gray-600 h-full min-h-0 relative">
      <!-- Top-Left New Chat Button -->
      <button
        @click="startNewChat"
        class="absolute top-3 left-3 z-10 flex items-center justify-center w-10 h-10 rounded-full hover:bg-gray-100 transition bg-white"
        title="Start New Chat"
      >
        <SquarePen class="w-5 h-5 text-gray-600" />
      </button>
      <!-- Scrollable Central Area -->
      <div ref="scrollContainer" class="flex flex-col flex-1 overflow-y-auto scroller message-list">
        <div class="flex justify-center max-w-3xl mx-auto">
          <ChatMessageList :messages="messages" />
        </div>
      </div>
      <!-- Fixed Chat Input -->
      <div class="w-full max-w-2xl mx-auto p-2">
        <ChatInput
          v-model="newMessage"
          :disabled="false"
          placeholder="New chat in this project"
          @send="handleUserMessage"
        />
      </div>
    </div>

    <!-- Questions Side Panel (right) -->
    <div
      v-if="questions.length"
      ref="questions_box"
      :class="[
        'flex flex-col bg-gray-200',
        collapsed ? 'w-14' : 'w-[70%] border-l border-gray-300',
        'min-h-0',
        'max-h-full',
      ]"
    >
      <div :class="['items-center p-2 mr-4', collapsed ? 'flex-1 items-start' : 'flex relative']">
        <button
          class="w-10 h-10 flex items-center justify-center focus:outline-none border border-gray-300 hover:bg-gray-300 rounded-full transition-all duration-300"
          @click="toggleQuestionsBox"
        >
          <component :is="collapsed ? ChevronLeft : ChevronRight" class="w-5 h-5 text-gray-600" />
        </button>

        <!-- Centered column buttons -->
        <div
          v-if="!collapsed"
          class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex gap-2 z-10"
          style="pointer-events: auto"
        >
          <button
            v-for="n in 2"
            :key="n"
            :class="[
              'flex items-center w-10 h-10 rounded-full justify-center border border-gray-300 transition',
              store.columns === n
                ? 'bg-gray-300'
                : 'hover:bg-gray-300 border-gray-300 text-gray-600',
            ]"
            @click="store.setColumns(n)"
          >
            <component :is="iconMap[n]" class="w-5 h-5" />
          </button>
        </div>

        <!-- Keep Approve All at the right if needed -->
        <div v-if="!collapsed" class="flex items-center gap-2 ml-auto">
          <button
            class="flex gap-2 h-10 items-center px-3 py-1 rounded-full text-sm font-medium text-green-700 hover:bg-gray-300 transition border"
            @click="handleApproveAll"
          >
            <CheckCheck class="w-5 h-5 text-green-700" />
            Approve All
          </button>
        </div>
      </div>
      <span v-if="!collapsed" class="text-xs font-light px-4 p-2 text-sm font-light">
        Showing {{ questions.length }} question(s) pending your approval
      </span>

      <div v-if="!collapsed" class="flex-1 m-3 mt-0 min-h-0 flex flex-col">
        <ChatRightCards
          :assets="questions"
          @tweak-request="handleTweakRequest"
          :tweak-complete="lastTweakedCardId"
          :columns="store.columns"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
  import { ref, watch, onMounted, nextTick } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import {
    ChevronRight,
    ChevronLeft,
    SquarePen,
    CheckCheck,
    RectangleVertical,
    Columns2,
  } from 'lucide-vue-next'
  import ChatInput from '@/components/ChatInput.vue'
  import ChatMessageList from '@/components/ChatMessageList.vue'
  import ChatRightCards from '@/components/ChatRightCards.vue'
  import { useUserStore } from '@/stores/user'
  import { useChatStore } from '@/stores/chats'
  import { useStore } from '@/stores/index'
  import { getSessionMessages, sendMessage, createSummary, getQuestions } from '../../../api/chat'
  import { sendTweakRequest, approveQuestion } from '../../../api/questions'
  import { checkHealth } from '../../../api/lightrag'
  import { initProject, createTitle } from '../../../api/chat'

  const route = useRoute()
  const router = useRouter()

  const messages = ref([])
  const questions = ref([])
  const lastTweakedCardId = ref(null)
  const collapsed = ref(true)
  const newMessage = ref('')
  const thinking = ref(false)
  const thinking_message_created_at = ref(null)

  const iconMap = {
    1: RectangleVertical,
    2: Columns2,
  }
  const userStore = useUserStore()
  const chatStore = useChatStore()
  const store = useStore()

  function toggleQuestionsBox() {
    collapsed.value = !collapsed.value
    console.log(collapsed.value)
  }

  function startNewChat() {
    createTitle(route.params.session_id)
    const project_id = route.params.project_id
    router.push(`/p/${project_id}`)
  }

  async function handleUserMessage(messageText = newMessage.value) {
    if (!messageText.trim()) return
    const user_message = messageText
    newMessage.value = ''
    const temp_user_message_created_at = new Date().toISOString()
    const temp_user_message_id = `id_${temp_user_message_created_at}`
    const temp_user_message = {
      id: temp_user_message_id,
      session_id: route.params.session_id,
      role: 'user',
      content: user_message,
      created_at: temp_user_message_created_at,
    }
    messages.value.push(temp_user_message)
    scrollToBottom()

    thinking.value = true
    thinking_message_created_at.value = new Date().toISOString()
    const thinking_message_id = `id_${thinking_message_created_at.value}`
    const thinking_message = {
      id: thinking_message_id,
      session_id: route.params.session_id,
      role: 'assistant',
      content: 'typing',
      created_at: thinking_message_created_at.value,
    }

    setTimeout(() => {
      if (thinking.value) {
        messages.value.push(thinking_message)
        scrollToBottom()
      }
    }, 200)

    const data = await sendMessage(
      userStore.user_id,
      route.params.session_id,
      route.params.project_id,
      user_message
    )
    const idx = messages.value.findIndex((m) => m.id === temp_user_message.id)
    if (idx !== -1) {
      messages.value[idx] = {
        id: data.user_message_id,
        session_id: route.params.session_id,
        role: 'user',
        content: user_message,
        created_at: temp_user_message_created_at,
      }
    }

    const thinking_idx = messages.value.findIndex((m) => m.id === thinking_message_id)
    if (thinking_idx !== -1) {
      messages.value.splice(thinking_idx, 1)
    }

    setTimeout(async () => {
      thinking.value = false

      messages.value.push({
        id: data.system_message_id,
        session_id: route.params.session_id,
        role: 'assistant',
        content: data.ai_message,
        created_at: data.system_created_at,
      })
      scrollToBottom()

      await fetchQuestions()
      await createSummary(route.params.session_id)
    }, 100)
  }

  async function fetchQuestions() {
    const data = await getQuestions(route.params.session_id)
    questions.value = data.questions.filter((q) => q.isApproved === 0 && q.isArchived === 0)
    collapsed.value = false
  }

  function scrollToBottom() {
    nextTick(() => {
      const list = document.querySelector('.message-list')
      if (list) {
        list.scrollTo({
          top: list.scrollHeight,
          behavior: 'smooth',
        })
      }
    })
  }

  async function handleTweakRequest({ id, session_id, user_message }) {
    const tweak_request_created_at = new Date().toISOString()
    try {
      const tweak_request_id = `id_${tweak_request_created_at}`

      messages.value.push({
        id: tweak_request_id,
        session_id: session_id,
        role: 'user',
        content: user_message,
        created_at: tweak_request_created_at,
      })
      scrollToBottom()

      thinking.value = true
      thinking_message_created_at.value = new Date().toISOString()
      const thinking_message = {
        id: 'thinking',
        session_id: route.params.session_id,
        role: 'assistant',
        content: 'typing',
        created_at: thinking_message_created_at.value,
      }

      setTimeout(() => {
        if (thinking.value) {
          messages.value.push(thinking_message)
          scrollToBottom()
        }
      }, 200)

      const data = await sendTweakRequest(id, session_id, user_message)

      const idx = messages.value.findIndex((m) => m.id === tweak_request_id)
      if (idx !== -1) {
        messages.value[idx] = {
          id: data.user_message_id,
          session_id: session_id,
          role: 'user',
          content: user_message,
          created_at: tweak_request_created_at,
        }
      }
      const thinkingIndex = messages.value.findIndex((m) => m.id === 'thinking')
      if (thinkingIndex !== -1) {
        messages.value.splice(thinkingIndex, 1)
      }

      setTimeout(() => {
        thinking.value = false
        lastTweakedCardId.value = id
        messages.value.push({
          id: data.system_message_id || `assistant-${Date.now()}`,
          session_id,
          role: 'assistant',
          content: data.ai_message,
          created_at: data.system_created_at || new Date().toISOString(),
        })
      }, 200)
    } catch (error) {
      console.error('Failed to tweak question:', error)
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

  async function handleApproveAll() {
    const ids = questions.value.map((q) => q.id)
    for (const id of ids) {
      try {
        await approveQuestion(id, route.params.session_id)
        await fetchQuestions()
      } catch (err) {
        console.error(`Approve failed for id=${id}:`, err)
      }
    }
  }

  onMounted(async () => {
    await fetchQuestions()
    await checkServerState()
    const data = await getSessionMessages(route.params.session_id)
    messages.value = data.messages || []
    if (questions.value.length) {
      collapsed.value = false
    }
    if (chatStore.initialMessage && !chatStore.initialMessageConsumed) {
      chatStore.markInitialMessageConsumed()
      await handleUserMessage(chatStore.initialMessage)
    }
  })

  watch(
    () => route.params.project_id,
    async (project_id) => {
      if (!project_id) return
      await checkServerState()
      const data = await getSessionMessages(route.params.session_id)
      messages.value = data.messages || []
    },
    { immediate: true }
  )
</script>

<style scoped>
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
