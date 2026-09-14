# 医疗病案管理后台

基于 Vue 3 + Element Plus 的医疗病案系统管理后台，支持抽取模板、ICD编码库、术语词典的可视化管理。

## 功能特性

| 功能 | 说明 |
|---|---|
| 📊 **仪表盘** | 模板/ICD/术语数量统计，快速入口 |
| 📋 **抽取模板管理** | 不同类型病案的抽取字段配置（增删改查、动态字段） |
| 🏥 **ICD编码库管理** | 疾病编码与名称维护，支持分类、搜索、启停 |
| 📝 **术语词典管理** | 同义词、缩写、别名、口语化术语映射，用于抽取前文本归一化 |

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端框架 | Vue 3 + Vite |
| UI 组件库 | Element Plus |
| 路由 | Vue Router 4 |
| HTTP 客户端 | Axios |
| 后端 | FastAPI |

## 快速开始

```bash
# 启动后端服务（项目根目录）
cd project2_medical_platform
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 启动前端管理后台（新开终端）
cd admin
npm install
npm run dev
```

访问 **http://localhost:5174**

## 项目结构

```
admin/
├── index.html
├── package.json
├── vite.config.js
├── README.md
└── src/
    ├── main.js
    ├── App.vue              # 布局（侧边栏 + 顶部栏）
    ├── router.js            # 路由配置
    ├── api/
    │   └── index.js         # API 封装
    └── views/
        ├── Dashboard.vue       # 仪表盘
        ├── TemplateManage.vue  # 抽取模板管理
        ├── IcdManage.vue       # ICD编码库管理
        └── TermManage.vue      # 术语词典管理
```

## 后端 API

| 模块 | 接口 |
|---|---|
| 抽取模板 | `GET/POST /api/admin/templates`、`GET/PUT/DELETE /api/admin/templates/{id}` |
| ICD编码 | `GET/POST /api/admin/icd-codes`、`GET/PUT/DELETE /api/admin/icd-codes/{id}`、`GET /api/admin/icd-codes/search?q=` |
| 术语词典 | `GET/POST /api/admin/terms`、`GET/PUT/DELETE /api/admin/terms/{id}` |
| 统计 | `GET /api/admin/stats` |

## 构建生产版本

```bash
npm run build
```

产物在 `dist/` 目录，可部署到 Nginx 或由 FastAPI 静态文件托管。
