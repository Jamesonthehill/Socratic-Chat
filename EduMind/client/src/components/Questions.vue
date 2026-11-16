i<template>
  <div class="flex flex-col flex-1 min-h-0 h-full overflow-hidden">
    <div class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
      <h2 class="text-lg font-semibold text-gray-700 ml-2 mb-4">Questions</h2>
    </div>
    <div class="p-8 space-y-4 flex-1 min-h-0 overflow-y-auto scroller">
      <Table :columns="columns" :rows="tableRows" @row-click="openQuestionCard" />
    </div>
    <QuestionFloatingCard
      v-if="selectedQuestion"
      :question="selectedQuestion"
      @close="selectedQuestion = null"
    />
  </div>
</template>

<script setup>
  import { ref, onMounted } from 'vue'
  import { useUserStore } from '../stores/user'
  import axios from 'axios'
  import Table from './Table.vue'
  import QuestionFloatingCard from './QuestionCard.vue'

  const userStore = useUserStore()
  const tableRows = ref([])
  const selectedQuestion = ref(null)

  const columns = [
    {
      label: 'Question',
      key: 'preview_text',
      link: true,
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
    },
    {
      label: 'Status',
      key: 'isApproved',
      formatter: (val) => (val ? 'Approved' : 'Unapproved'),
      filterable: true,
    },
    {
      label: 'Created At',
      key: 'created_at',
      sortable: true,
      filterable: true,
    },
  ]

  const fetchQuestions = async () => {
    try {
      const resp = await axios.get(
        `${import.meta.env.VITE_SERVER_URL}/api/v1/question/user/${userStore.user_id}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': '1',
          },
        }
      )
      function formatDate(dateStr) {
        const date = new Date(dateStr)
        const mm = String(date.getMonth() + 1).padStart(2, '0')
        const dd = String(date.getDate()).padStart(2, '0')
        const yyyy = date.getFullYear()
        return `${mm}/${dd}/${yyyy}`
      }

      tableRows.value = (resp.data.questions || []).map((q) => ({
        ...q,
        tags: q.tags || [],
        created_at: formatDate(q.created_at),
        preview_text: (q.question_text || '').split(' ').slice(0, 10).join(' ') + '...',
      }))
    } catch (e) {
      console.error('Error fetching questions:', e)
    }
  }

  const openQuestionCard = (row) => {
    selectedQuestion.value = row
  }

  onMounted(fetchQuestions)
</script>