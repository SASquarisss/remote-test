# Backend (后端) 公共业务逻辑文档

## 1. 模块定位
- **入口文件**: `backend/app.py`
- **关联文件**: `backend/parser.py`, `scripts/generate_prompt.py` 等。
- **职责**: 作为 Flask API 服务器，为 Workspace (解析) 和 Database (案例库) 提供接口支持。处理大模型调度、Prompt 生成、JSON 清洗与本体映射、向量化与持久化存储。

## 2. 核心路由与分发
- **Workspace 接口**:
  - 核心解析触发、检索资产打包 (`_build_retrieval_bundle` 等内部方法及相关路由)。
- **Database 接口**:
  - 读取 static/saved cases，提供列表展示与过滤。
- **端口规范**:
  - Flask 服务默认运行在 `9120` 端口（或未来的统一端口 `8000`）。
  - Vite 前端服务运行在 `5174`。

## 3. 核心机制与防坑点
### 3.1 环境变量依赖
- 必须通过 `python-dotenv` 自动加载 `.env`，尤其确保 `DEEPSEEK_API_KEY` 存在，否则会在调用 LLM 时报 `HTTP 500` 错误。
- 若涉及 Cross Encoder 等高显存模型，需配置 `NV_CUDA_DISABLE_SYSMEM_FALLBACK="1"` 防止 OOM 导致死机。

### 3.2 截断与数据完整性
- **禁止在后端对关键图谱信息做随意截断**：
  - 过去在 `_build_retrieval_bundle` 或 `_retrieval_short_text` 中大量使用数组切片（如 `[:4]`）导致前端图谱或文本出现 `...`，造成信息丢失。**现已全部禁用**。
  - 对于流式输出（SSE），为防前端网络超时，可做宏观大段落截断（如单篇1500字限制），但资产内的图谱属性和链路文本必须全量下发。

### 3.3 Milvus 与向量存储
- **禁止底层序列化引发段错误**: 
  - 在纯 Python 多线程环境混用 `pymilvus` (gRPC) 和 PyTorch 极易引发 `Segmentation fault`。
  - **解决方案**: 
    1. 弃用 `pymilvus`，改用 Python `requests` 纯 HTTP API (`/v1/vector/search`)。
    2. 注意修复 Milvus HTTP API 有时返回非法拼接 JSON (如 `{"code":100...}{"code":100...}`) 的边缘 Case，需手动截取 `split("}{")[0] + "}"`。
    3. 传递 Milvus Document 对象前，务必清理 metadata 中的超大数组 (`embedding` 等)。

### 3.4 动态链路说明生成
- 后端的 `_retrieval_graph_payload` 等方法负责组装检索资产链路说明。
- 必须确保 `description` 和 `path_label` 是根据具体传入的实体内容动态拼装（例如 `f"从争点「{content}」出发..."`），不可写死静态模板。