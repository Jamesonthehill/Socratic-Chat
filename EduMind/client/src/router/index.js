import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/home/home.vue'
import Project from '@/views/project/project.vue'
import Chat from '@/views/project/chat_session.vue'
import Questions from '@/views/questions/questions.vue'
import Login from '@/views/auth/login.vue'

import {useAuthStore} from '@/stores/auth.js'

const routes = [
  { path: '/login', name: 'Login', component: Login },
  { path: '/', name: 'Home', component: Home, meta: { hideNavbar: true } },
  { path: '/chat/:session_id?/p/:project_id', name: 'Chat', component: Chat , meta: { requiresAuth: true }},
  { path: '/p/:project_id?', name: 'Project', component: Project, meta: { requiresAuth: true } },
  { path: '/questions', name: 'Questions', component: Questions, meta: { hideTopNavbar: true , meta: { requiresAuth: true }} },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (auth.token === null) auth.restore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && auth.isAuthenticated) {
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router
