import axios from 'axios'

const api = axios.create({
  baseURL: '/api/admin',
  timeout: 30000
})

// ==================== 抽取模板 ====================
export function getTemplates(params) {
  return api.get('/templates', { params })
}
export function getTemplate(id) {
  return api.get(`/templates/${id}`)
}
export function createTemplate(data) {
  return api.post('/templates', data)
}
export function updateTemplate(id, data) {
  return api.put(`/templates/${id}`, data)
}
export function deleteTemplate(id) {
  return api.delete(`/templates/${id}`)
}

// ==================== ICD 编码库 ====================
export function getIcdCodes(params) {
  return api.get('/icd-codes', { params })
}
export function searchIcdCodes(q, limit = 10) {
  return api.get('/icd-codes/search', { params: { q, limit } })
}
export function getIcdCode(id) {
  return api.get(`/icd-codes/${id}`)
}
export function createIcdCode(data) {
  return api.post('/icd-codes', data)
}
export function updateIcdCode(id, data) {
  return api.put(`/icd-codes/${id}`, data)
}
export function deleteIcdCode(id) {
  return api.delete(`/icd-codes/${id}`)
}

// ==================== 术语词典 ====================
export function getTerms(params) {
  return api.get('/terms', { params })
}
export function getTerm(id) {
  return api.get(`/terms/${id}`)
}
export function createTerm(data) {
  return api.post('/terms', data)
}
export function updateTerm(id, data) {
  return api.put(`/terms/${id}`, data)
}
export function deleteTerm(id) {
  return api.delete(`/terms/${id}`)
}

// ==================== 统计 ====================
export function getAdminStats() {
  return api.get('/stats')
}

export default api
