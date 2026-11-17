import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useChatStore = defineStore('chat', () => {
  // ────── State ──────
  const session_id = ref(null)
  const project_id = ref(null)
  const new_message = ref('')
  const messages = ref([])
  const input = ref('')
  const selectedQuestions = ref([])
  const tweakRequest = reactive({})
  const tweakComplete = ref('')
  const questionsVersion = ref(1)
  const rightCollapsed = ref(false)
  const initialMessage = ref(null)
  const initialMessageConsumed = ref(false)

  // ────── Actions ──────
  function setSessionId(id) {
    session_id.value = id
  }

  function setProjectId(id) {
    project_id.value = id
  }

  function setNewMessage(msg) {
    new_message.value = msg
  }

  function addMessage(msg) {
    messages.value.push(msg)
  }

  function setMessages(msgs) {
    messages.value = msgs
  }

  function clearMessages() {
    messages.value = []
  }

  function updateInput(value) {
    input.value = value
  }

  function setSelectedQuestions(questions) {
    selectedQuestions.value = questions
  }

  function handleTweakRequest(payload) {
    Object.assign(tweakRequest, payload)
  }

  function triggerTweakComplete(id) {
    tweakComplete.value = id
    setTimeout(() => (tweakComplete.value = ''), 100)
  }

  function triggerQuestionsUpdate() {
    questionsVersion.value += 1
  }

  function toggleRightPane(value) {
    rightCollapsed.value = value
  }

  function setInitialMessage(msg) {
    initialMessage.value = msg
    initialMessageConsumed.value = false
  }

  function markInitialMessageConsumed() {
    initialMessageConsumed.value = true
  }

  function clearInitialMessage() {
    initialMessage.value = null
    initialMessageConsumed.value = false
  }

  function setNewChat() {
    session_id.value = null
    messages.value = []
    initialMessage.value = null
    initialMessageConsumed.value = false
  }

  // ────── Expose ──────
  return {
    // state
    session_id,
    project_id,
    messages,
    input,
    selectedQuestions,
    tweakRequest,
    tweakComplete,
    questionsVersion,
    rightCollapsed,
    initialMessage,
    initialMessageConsumed,

    // actions
    setSessionId,
    setProjectId,
    setNewMessage,
    addMessage,
    setMessages,
    clearMessages,
    updateInput,
    setSelectedQuestions,
    handleTweakRequest,
    triggerTweakComplete,
    triggerQuestionsUpdate,
    toggleRightPane,
    setInitialMessage,
    markInitialMessageConsumed,
    clearInitialMessage,
    setNewChat,
  }
})
