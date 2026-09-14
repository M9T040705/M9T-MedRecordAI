<template>
  <div class="icd-manage">
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索编码或名称" clearable style="width: 240px;" @keyup.enter="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="category" placeholder="全部分类" clearable style="width: 160px;" @change="loadData">
          <el-option label="呼吸系统" value="呼吸系统" />
          <el-option label="循环系统" value="循环系统" />
          <el-option label="消化系统" value="消化系统" />
          <el-option label="神经系统" value="神经系统" />
          <el-option label="内分泌" value="内分泌" />
          <el-option label="肿瘤" value="肿瘤" />
          <el-option label="损伤中毒" value="损伤中毒" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新增编码
        </el-button>
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="code" label="ICD编码" width="140">
          <template #default="{ row }"><span style="font-family: monospace; font-weight: 600;">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="疾病名称" min-width="200" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }"><el-tag size="small">{{ row.category || '未分类' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData" @current-change="loadData" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑ICD编码' : '新增ICD编码'" width="500px">
      <el-form label-width="100px">
        <el-form-item label="ICD编码" required>
          <el-input v-model="form.code" placeholder="如：I10" />
        </el-form-item>
        <el-form-item label="疾病名称" required>
          <el-input v-model="form.name" placeholder="如：原发性高血压" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%;">
            <el-option label="呼吸系统" value="呼吸系统" />
            <el-option label="循环系统" value="循环系统" />
            <el-option label="消化系统" value="消化系统" />
            <el-option label="神经系统" value="神经系统" />
            <el-option label="内分泌" value="内分泌" />
            <el-option label="肿瘤" value="肿瘤" />
            <el-option label="损伤中毒" value="损伤中毒" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="疾病说明或备注" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
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
import { getIcdCodes, createIcdCode, updateIcdCode, deleteIcdCode } from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const category = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({ code: '', name: '', category: '', description: '', is_active: 1 })

const loadData = async () => {
  loading.value = true
  try {
    const { data } = await getIcdCodes({
      page: page.value, page_size: pageSize.value,
      keyword: keyword.value, category: category.value
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
  form.value = { code: '', name: '', category: '', description: '', is_active: 1 }
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.value = { ...row }
  dialogVisible.value = true
}

const save = async () => {
  if (!form.value.code || !form.value.name) {
    ElMessage.warning('请填写ICD编码和疾病名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateIcdCode(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createIcdCode(form.value)
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
    await ElMessageBox.confirm(`确定删除编码「${row.code} ${row.name}」吗？`, '确认删除', { type: 'warning' })
    await deleteIcdCode(row.id)
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
</style>
