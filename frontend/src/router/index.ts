import { createRouter, createWebHistory } from 'vue-router'
import LiveView from '../views/LiveView.vue'
import RecordingsView from '../views/RecordingsView.vue'

const routes = [
  { path: '/', name: 'live', component: LiveView },
  { path: '/recordings', name: 'recordings', component: RecordingsView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router