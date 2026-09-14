import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import TemplateManage from './views/TemplateManage.vue'
import IcdManage from './views/IcdManage.vue'
import TermManage from './views/TermManage.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { title: '仪表盘' } },
  { path: '/templates', name: 'TemplateManage', component: TemplateManage, meta: { title: '抽取模板管理' } },
  { path: '/icd', name: 'IcdManage', component: IcdManage, meta: { title: 'ICD编码库管理' } },
  { path: '/terms', name: 'TermManage', component: TermManage, meta: { title: '术语词典管理' } }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
