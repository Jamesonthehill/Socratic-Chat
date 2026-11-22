<template>
  <div class="flex flex-col min-h-0 p-4 h-full">
    <div class="flex flex justify-between pr-2">
      <h4 class="text-gray-700 ml-2 mb-4">All Questions</h4>
      <Button
        text="Export Options"
        type="ghost"
        class="text-blue-600 hover:text-blue-800"
        size="sm"
        @click="openExportDialog"
      />
    </div>
    <!-- Only this div scrolls -->
    <div class="flex-1 min-h-0 overflow-y-auto mt-5">
      <Table
        :columns="columns"
        :rows="tableRows"
        @row-click="openQuestionCard"
        @update:filteredRows="handleFilteredRows"
      />
    </div>
    <QuestionFloatingCard
      v-if="selectedQuestion"
      :question="selectedQuestion"
      @close="selectedQuestion = null"
    />
  </div>
  <transition name="fade">
    <div
      v-if="showArchiveConfirmDialog"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <!-- Modal container -->
      <div class="bg-white rounded-2xl w-100 h-60 mx-4 flex flex-col overflow-hidden">
        <!-- Modal Header -->
        <div class="flex items-center justify-between px-3 py-3">
          <h4 class="ml-2 mr-2 text-red-600">Delete Question</h4>
        </div>

        <!-- Modal Body -->
        <div class="flex flex-col flex-1 justify-center space-y-3 px-6 text-gray-700">
          <p class="text-red-600 font-medium">
            WARNING: This action will permanently delete the question and cannot be undone!
          </p>
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-end px-6 py-4 space-x-2 border-t border-gray-200">
          <button
            @click="archiveQuestion(questionToArchive.id)"
            class="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-full transition-colors disabled:opacity-50"
          >
            Delete
          </button>
          <button
            @click="closeArchiveConfirmDialog"
            class="bg-gray-300 text-gray-700 hover:bg-gray-400 px-4 py-2 rounded-full transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </transition>
  <!-- Export Options Dialog -->
  <transition name="fade">
    <div
      v-if="showExportDialog"
      class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
    >
      <!-- Modal container -->
      <div class="bg-white rounded-2xl w-110 h-90 mx-4 flex flex-col overflow-hidden">
        <!-- Modal Header -->
        <div class="flex px-3 py-3">
          <h2 class="text-lg font-semibold ml-2 mr-2 text-green-800">Export Options</h2>
        </div>

        <!-- Modal Body -->
        <div class="flex flex-col flex-1 space-y-3 px-6 text-sm text-gray-700">
          <p class="text-gray-600">
            Note: Export will include all questions in current filter state.
          </p>
          <div class="flex flex-col items-start space-y-2 py-4 w-full">
            <label class="text-gray-600 text-sm font-medium">Export Format</label>
            <select
              v-model="exportFormat"
              class="border border-gray-300 rounded-xl px-2 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-green-800"
            >
              <option value="csv">CSV</option>
              =
              <option value="qti">QTI</option>
            </select>
            <label class="text-gray-600 text-sm font-medium mt-2">Export File Name</label>
            <input
              v-model="exportFileName"
              type="text"
              placeholder="Enter export file name"
              class="border border-gray-300 rounded-xl px-2 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-green-800"
            />
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-end px-6 py-4 space-x-2 border-t border-gray-200">
          <button
            @click="handleExport"
            class="bg-green-800 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-full transition-colors disabled:opacity-50"
          >
            Export
          </button>
          <button
            @click="closeExportDialog"
            class="bg-gray-300 text-gray-700 hover:bg-gray-400 text-sm font-medium px-4 py-2 rounded-full transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
  import { ref, watch, computed } from 'vue'

  import { useUserStore } from '@/stores/user'
  import { useRouter } from 'vue-router'
  import Table from '@/components/Table.vue'
  import QuestionFloatingCard from '@/components/QuestionCard.vue'
  import Button from '@/components/Button.vue'
  import {
    getQuestionsByUser,
    archiveQuestionById,
    exportQuestions,
    undoApproval,
  } from '../../../api/questions'

  const router = useRouter()
  const userStore = useUserStore()
  const user_id = computed(() => userStore.user_id)
  const tableRows = ref([])
  const selectedQuestion = ref(null)
  const showArchiveConfirmDialog = ref(false)
  const showExportDialog = ref(false)

  const columns = [
    {
      label: 'Question',
      key: 'preview_text',
      link: true,
      width: '30%',
    },
    {
      label: 'Project',
      key: 'project_name',
      link: true,
      route: 'p/:project_id',
      filterable: true,
    },
    {
      label: 'Difficulty',
      key: 'difficulty_level',
      filterable: true,
    },
    {
      label: 'Tags',
      key: 'tags',
      type: 'array',
      filterable: true,
      width: '20%',
    },
    {
      label: 'Status',
      key: 'isApproved',
      type: 'status',
      formatter: (val) => (val ? 'Approved' : 'Unapproved'),
      filterable: true,
    },
    {
      label: 'Last Updated At',
      key: 'updated_at',
      sortable: true,
      filterable: true,
    },
    {
      key: 'actions',
      label: 'Actions',
      type: 'actions',
      actions: [
        {
          label: '',
          icon: 'Edit',
          color: 'text-blue-600 hover:text-blue-800',
          action: (row) => openEditor(row),
        },
        {
          label: '',
          icon: 'Trash',
          color: 'text-red-600 hover:text-red-800',
          action: (row) => openArchiveConfirmDialog(row),
        },
      ],
    },
  ]

  const fetchQuestions = async () => {
    try {
      const data = await getQuestionsByUser(userStore.user_id)

      console.log(data)

      function formatDate(dateStr) {
        const date = new Date(dateStr)
        // Use options for shorter format
        return date.toLocaleString(undefined, {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
        })
      }

      tableRows.value = (data.questions || []).map((q) => ({
        ...q,
        tags: q.tags || [],
        updated_at: formatDate(q.updated_at),
        preview_text: (q.question_text || '').split(' ').slice(0, 10).join(' ') + '...',
        isApproved: q.isApproved ? 'Approved' : 'Pending',
      }))
      // Ensure the table only shows !isArchived questions
      tableRows.value = tableRows.value.filter((q) => !q.isArchived)
    } catch (e) {
      console.error('Error fetching questions:', e)
    }
  }

  const openQuestionCard = (row) => {
    selectedQuestion.value = row
  }

  watch(
    user_id,
    (newUserId) => {
      if (newUserId) fetchQuestions()
    },
    { immediate: true }
  )

  const openArchiveConfirmDialog = (row) => {
    questionToArchive.value = row
    showArchiveConfirmDialog.value = true
  }
  const closeArchiveConfirmDialog = () => {
    showArchiveConfirmDialog.value = false
  }

  const openExportDialog = () => {
    showExportDialog.value = true
  }
  const closeExportDialog = () => {
    showExportDialog.value = false
  }

  const filteredTableRows = ref([])
  function handleFilteredRows(rows) {
    filteredTableRows.value = rows
  }
  const exportFormat = ref('csv')
  const exportFileName = ref('')

  function base64ToUint8Array(base64) {
    const binary_string = atob(base64)
    const len = binary_string.length
    const bytes = new Uint8Array(len)
    for (let i = 0; i < len; i++) {
      bytes[i] = binary_string.charCodeAt(i)
    }
    return bytes
  }

  const handleExport = async () => {
    const filename =
      (exportFileName.value?.trim() || 'questions_export') +
      (exportFormat.value === 'csv' ? '.csv' : '.zip')

    const data = await exportQuestions(filename, exportFormat.value, filteredTableRows.value)
    const byteArray = base64ToUint8Array(data.export.filedata)
    const mimeType = exportFormat === 'csv' ? 'text/csv' : 'application/zip'
    const blob = new Blob([byteArray], { type: mimeType })

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    if (typeof closeExportDialog === 'function') closeExportDialog()
  }

  const questionToArchive = ref(null)
  const archiveQuestion = async (questionId) => {
    try {
      await archiveQuestionById(questionId)
      closeArchiveConfirmDialog()
      fetchQuestions()
    } catch (error) {
      console.error('Error deleting question:', error)
    }
  }

  const openEditor = async (row) => {
    try {
      const res = await undoApproval(row.id, row.session_id)
      if (res.success) {
        router.push(`/chat/${row.session_id}/p/${row.project_id}`)
      } else {
        console.error(res.error || 'Failed to revert approval')
      }
    } catch (error) {
      console.error('Undo approval error:', error)
    }
  }
</script>
