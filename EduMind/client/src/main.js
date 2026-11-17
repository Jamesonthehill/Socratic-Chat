import { createApp } from 'vue'
import ToastPlugin from 'vue-toast-notification'
import './style.css'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import 'prismjs/components/prism-javascript'
import 'prismjs/themes/prism-tomorrow.css'
import 'vue-toast-notification/dist/theme-bootstrap.css'

const app = createApp(App)

app.use(router)
app.use(ToastPlugin)
app.use(createPinia())

app.mount('#app')
