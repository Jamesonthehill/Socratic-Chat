import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const user_id = ref('101')
  const team_id = ref('201')
  const user_name = ref('')

  function setUser(id, name = '', teamId = '') {
    user_id.value = id
    user_name.value = name
    team_id.value = teamId
  }

  return { user_id, user_name, team_id, setUser }
})
