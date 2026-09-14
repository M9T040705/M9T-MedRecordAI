<template>
  <div class="term-manage">
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索术语或标准词" clearable style="width: 240px;" @keyup.enter="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="termType" placeholder="全部类型" clearable style="width: 160px;" @change="loadData">
          <el-option label="同义词" value="synonym" />
          <el-option label="缩写" value="abbreviation" />
          <el-option label="别名" value="alias" />
          <el-option label="口语化" value="colloquial" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新增术语
        </el-button>
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="term" label="术语/缩写" width="180">
          <template #default="{ row }"><span style="font-weight: 500; color: #409eff;">{{ row.term }}</span></template>
        </el-table-column>
        <el-table-column label="映射关系" width="60" align="center">
          <template #default><el-icon color="#909399"><Right /></el-icon></template>
        </el-table-column>
        <el-table-column prop="standard_term" label="标准术语" min-width="180">
          <template #default="{ row }"><span style="font-weight: 500;">{{ row.standard_term }}</span></template>
        </el-table-column>
        <el-table-column prop="term_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="typeColor(row.term_type)" size="small">{{ typeLabel(row.term_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑术语' : '新增术语'" width="500px">
      <el-form label-width="100px">
        <el-form-item label="术语/缩写" required>
          <el-input v-model="form.term" placeholder="如：心梗、AMI" />
        </el-form-item>
        <el-form-item label="标准术语" required>
          <el-input v-model="form.standard_term" placeholder="如：心肌梗死" />
        </el-form-item>
        <el-form-item label="术语类型">
          <el-select v-model="form.term_type" style="width: 100%;">
            <el-option label="同义词" value="synonym" />
            <el-option label="缩写" value="abbreviation" />
            <el-option label="别名" value="alias" />
            <el-option label="口语化" value="colloquial" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="术语说明或备注" />
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
import { getTerms, createTerm, updateTerm, deleteTerm } from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const termType = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({ term: '', standard_term: '', term_type: 'synonym', description: '', is_active: 1 })

const typeLabel = (t) => ({ synonym: '同义词', abbreviation: '缩写', alias: '别名', colloquial: '口语化' }[t] || t)
const typeColor = (t) => ({ synonym: '', abbreviation: 'success', alias: 'warning', colloquial: 'danger' }[t] || '')

const loadData = async () => {
  loading.value = true
  try {
    const { data } = await getTerms({
      page: page.value, page_size: pageSize.value,
      keyword: keyword.value, term_type: termType.value
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
  form.value = { term: '', standard_term: '', term_type: 'synonym', description: '', is_active: 1 }
  dialogVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.value = { ...row }
  dialogVisible.value = true
}

const save = async () => {
  if (!form.value.term || !form.value.standard_term) {
    ElMessage.warning('请填写术语和标准术语')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateTerm(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createTerm(form.value)
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
    await ElMessageBox.confirm(`确定删除术语「${row.term} → ${row.standard_term}」吗？`, '确认删除', { type: 'warning' })
    await deleteTerm(row.id)
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
