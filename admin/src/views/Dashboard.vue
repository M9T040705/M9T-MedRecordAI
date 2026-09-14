<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #409eff;">
            <el-icon :size="28"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.templates || 0 }}</div>
            <div class="stat-label">抽取模板总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #67c23a;">
            <el-icon :size="28"><Collection /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.icd_codes || 0 }}</div>
            <div class="stat-label">ICD 编码总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #e6a23c;">
            <el-icon :size="28"><EditPen /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.terms || 0 }}</div>
            <div class="stat-label">术语词条总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #f56c6c;">
            <el-icon :size="28"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ activeTotal }}</div>
            <div class="stat-label">启用中配置</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span style="font-weight: 600;">快速入口</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" size="large" @click="$router.push('/templates')">
              <el-icon><Document /></el-icon> 管理抽取模板
            </el-button>
            <el-button type="success" size="large" @click="$router.push('/icd')">
              <el-icon><Collection /></el-icon> 管理 ICD 编码
            </el-button>
            <el-button type="warning" size="large" @click="$router.push('/terms')">
              <el-icon><EditPen /></el-icon> 管理术语词典
            </el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span style="font-weight: 600;">配置启用状态</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="启用的抽取模板">
              <el-tag type="success">{{ stats.active_templates || 0 }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="启用的 ICD 编码">
              <el-tag type="success">{{ stats.active_icd_codes || 0 }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="启用的术语词条">
              <el-tag type="success">{{ stats.active_terms || 0 }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getAdminStats } from '../api'

const stats = ref({
  templates: 0, icd_codes: 0, terms: 0,
  active_templates: 0, active_icd_codes: 0, active_terms: 0
})

const activeTotal = computed(() =>
  (stats.value.active_templates || 0) +
  (stats.value.active_icd_codes || 0) +
  (stats.value.active_terms || 0)
)

onMounted(async () => {
  try {
    const { data } = await getAdminStats()
    stats.value = data
  } catch (e) {
    console.error('加载统计失败', e)
  }
})
</script>

<style scoped>
.stat-card { display: flex; align-items: center; gap: 16px; }
.stat-icon {
  width: 56px; height: 56px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
}
.stat-value { font-size: 28px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #909399; margin-top: 2px; }
.quick-actions { display: flex; flex-direction: column; gap: 12px; }
.quick-actions .el-button { width: 100%; justify-content: flex-start; }
</style>
