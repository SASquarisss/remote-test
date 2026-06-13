# Database (案例库浏览器) 业务逻辑文档

## 1. 模块定位
- **入口文件**: `visualization/ontology-refactored/index.database.html`
- **核心前端文件**:
  - `src/components/database/` 下的相关组件（通常包括搜索栏、列表页、图谱概览等）。
- **职责**: 针对已保存的案例资产（Saved Cases）和待处理的数据湖（Data Lake）进行宏观的检索、浏览、批处理操作与可视化展示。

## 2. 核心功能区块
### 2.1 已保存案例 (Saved Cases)
- 承接 Workspace 产出的、经过人工核对或机器确认写入的检索资产 (Retrieval Bundle)。
- **操作**: 支持全文检索、元数据过滤（如按案由、审级筛选），点击单条记录可查看案例的概览图谱和解析文本。
- **与 Workspace 的边界**: 这里偏向于**只读与检索利用**，不再进行深度的节点拖拽、编辑和重连。

### 2.2 数据湖候选池 (Data Lake)
- 管理尚未经过深度解析的原始裁判文书或文档。
- **操作**: 列表浏览、批量勾选、触发“发送至 Workspace 解析”或后台批量自动解析。

## 3. 前后端交互
- **专属 API**:
  - 获取列表: `GET /api/v1/database/cases`
  - 检索/过滤: `POST /api/v1/database/search`
  - *(具体路由以后端 app.py 中的实际定义为准)*
- **隔离原则**:
  - Database 页面的状态管理（如搜索词、翻页页码）应与 Workspace 完全独立。
  - 从 Database 跳转到 Workspace 解析特定案例时，通常通过 URL 参数（如 `?case_id=xxx`）传递上下文。

## 4. 待办与扩展 (TODOs)
*(该模块处于持续迭代中，目前需注意确保两端样式库的兼容，且不要将 Workspace 复杂的编辑逻辑侵入到 Database 的纯浏览逻辑中。)*