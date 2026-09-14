<template>
  <div class="template-manage">
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索模板名称" clearable style="width: 240px;" @keyup.enter="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="docType" placeholder="全部类型" clearable style="width: 160px;" @change="loadData">
          <el-option label="入院记录" value="入院记录" />
          <el-option label="出院小结" value="出院小结" />
          <el-option label="手术记录" value="手术记录" />
          <el-option label="门诊病历" value="门诊病历" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新建模板
        </el-button>
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="name" label="模板名称" min-width="180">
          <template #default="{ row }">
            <div style="font-weight: 500;">{{ row.name }}</div>
            <div style="font-size: 12px; color: #909399;">{{ row.description || '无描述' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="doc_type" label="文档类型" width="120">
          <template #default="{ row }"><el-tag size="small">{{ row.doc_type }}</el-tag></template>
        </el-table-column>
        <el-table-column label="字段数" width="100" align="center">
          <template #default="{ row }">{{ (row.fields_json || []).length }}</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData" @current-change="loadData" />
      </div>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模板' : '新建模板'" width="700px" top="5vh">
      <el-form label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板名称" required>
              <el-input v-model="form.name" placeholder="如：入院记录抽取模板" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文档类型" required>
              <el-select v-model="form.doc_type" style="width: 100%;">
                <el-option label="入院记录" value="入院记录" />
                <el-option label="出院小结" value="出院小结" />
                <el-option label="手术记录" value="手术记录" />
                <el-option label="门诊病历" value="门诊病历" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="模板用途说明" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-divider content-position="left">抽取字段配置</el-divider>
        <div class="fields-editor">
          <div v-for="(field, idx) in form.fields" :key="idx" class="field-row">
            <el-input v-model="field.name" placeholder="字段名(英文)" style="width: 140px;" />
            <el-input v-model="field.label" placeholder="显示名(中文)" style="width: 140px;" />
            <el-select v-model="field.type" style="width: 110px;">
              <el-option label="字符串" value="string" />
              <el-option label="数字" value="number" />
              <el-option label="日期" value="date" />
              <el-option label="布尔" value="boolean" />
              <el-option label="列表" value="list" />
            </el-select>
            <el-checkbox v-model="field.required">必填</el-checkbox>
            <el-input v-model="field.description" placeholder="说明" style="flex: 1;" />
            <el-button type="danger" link @click="form.fields.splice(idx, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-button type="primary" plain size="small" @click="addField">
            <el-icon><Plus /></el-icon> 添加字段
          </el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplates, createTemplate, updateTemplate, deleteTemplate } from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const docType = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({ name: '', doc_type: '', description: '', is_active: 1, fields: [] })

const loadData = async () => {
  loading.value = true
  try {
    const { data } = await getTemplates({
      page: page.value, page_size: pageSize.value,
      keyword: keyword.value, doc_type: docType.value
    })
    list.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.value = { name: '', doc_type: '', description: '', is_active: 1, fields: [] }
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.value = {
    name: row.name, doc_type: row.doc_type, description: row.description || '',
    is_active: row.is_active, fields: JSON.parse(JSON.stringify(row.fields_json || []))
  }
  dialogVisible.value = true
}

const addField = () => {
  form.value.fields.push({ name: '', label: '', type: 'string', required: false, description: '' })
}

const save = async () => {
  if (!form.value.name || !form.value.doc_type) {
    ElMessage.warning('请填写模板名称和文档类型')
    return
  }
  saving.value = true
  try {
    const data = { ...form.value }
    if (editingId.value) {
      await updateTemplate(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createTemplate(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除模板「${row.name}」吗？`, '确认删除', { type: 'warning' })
    await deleteTemplate(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.fields-editor { display: flex; flex-direction: column; gap: 8px; }
.field-row { display: flex; gap: 8px; align-items: center; }
</style>
