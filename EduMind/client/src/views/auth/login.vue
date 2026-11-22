<template>
  <div class="login">
    <form @submit.prevent="doLogin">
      <input v-model="email" type="email" placeholder="Email" required />
      <input v-model="password" type="password" placeholder="Password" required />
      <button type="submit">Login</button>
    </form>
    <div v-if="error">{{ error }}</div>
  </div>
</template>

<script setup>
  import { ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { useAuthStore } from '@/stores/auth'

  const email = ref('')
  const password = ref('')
  const error = ref('')
  const auth = useAuthStore()
  const router = useRouter()

  async function doLogin() {
    error.value = ''
    // Replace with your own API call
    if (email.value === 'test@test.com' && password.value === '1234') {
      const fakeToken = 'abcdef123456'
      const fakeUser = { email: email.value }
      auth.login(fakeToken, fakeUser)
      router.push({ name: 'Home' })
    } else {
      error.value = 'Invalid credentials'
    }
  }
</script>
