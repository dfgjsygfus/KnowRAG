# KnowRAG / KnowPET

KnowRAG 是一个本地知识库问答项目，包含 FastAPI 后端、文档入库管理台、Milvus/Milvus Lite 向量检索、RAG 流式问答，以及一个可选的 Tauri 桌面宠物客户端。

项目当前主要面向个人知识库和桌面助手场景：上传 Markdown/文本资料，切分并写入向量库，然后通过管理台或桌宠进行检索问答。

## 功能概览

- 文档管理：上传 `.md`、`.markdown`、`.txt`，保存到本地 SQLite 元数据表。
- 离线入库：Markdown 清洗、结构化切分、Embedding、写入 Milvus。
- 混合检索：Dense vector + BM25 sparse vector，中文 BM25 使用 Jieba tokenizer。
- RAG 问答：基于检索结果生成带来源的回答，支持 SSE 流式输出。
- 意图路由：区分知识库问答、闲聊等请求，减少不必要检索。
- 管理台：后端内置 `/admin` 页面，可上传、入库、预览文档并配置对话模型。
- 桌面宠物：Tauri + Vue 桌宠窗口，支持轻量输入框、完整聊天、管理台窗口和右键菜单。
- 评测脚本：支持 retrieval 召回评测和端到端回答质量评测。

## 项目结构

```text
.
├── backend/                 # FastAPI 路由、RAG、检索、入库、配置服务
│   └── app/
│       ├── api/             # /api/documents /api/ingestion /api/retrieval /api/chat /api/settings
│       ├── schemas/         # Pydantic 请求/响应模型
│       └── services/        # 文档、切分、Milvus、Embedding、RAG、模型配置等逻辑
├── desktop-pet/             # Tauri + Vue 桌面宠物客户端
├── frontend/                # 后端直接服务的静态管理台页面：/admin
├── evaluation/              # 检索评测数据集和报告
├── infra/milvus/            # Docker 版 Milvus Compose 配置
├── scripts/                 # 评测、Milvus 启停等脚本
├── tests/                   # 后端单元测试
├── data/                    # 本地运行数据，包含 SQLite / Milvus Lite / 模型设置等
├── main.py                  # FastAPI 应用入口
└── requirements.txt         # Python 依赖
```

## 环境要求

后端：

- Python 3.10+
- 可访问 SiliconFlow Embedding API，或替换为兼容的 embedding 服务
- 默认使用 Milvus Lite，无需 Docker

桌宠：

- Node.js 18+
- Rust 工具链
- Tauri 2 运行环境

如果只使用后端管理台，可以不安装桌宠相关依赖。

## 快速启动后端

1. 创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 准备环境变量：

```powershell
copy .env.example .env
```

至少需要配置：

```text
SILICONFLOW_API_KEY=你的 SiliconFlow API Key
```

如果要通过 `.env` 直接配置生成模型，也可以填写：

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

也可以启动后在管理台的“模型设置”里保存 DeepSeek、Qwen 或自定义 OpenAI-compatible 模型配置。管理台保存的配置位于 `data/chat_model_settings.json`。

4. 启动后端：

```powershell
python main.py
```

如果需要热更新：

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- 后端根路径：http://127.0.0.1:8000/
- 管理台：http://127.0.0.1:8000/admin
- OpenAPI 文档：http://127.0.0.1:8000/docs

## 使用管理台

打开 `http://127.0.0.1:8000/admin` 后可以完成常用流程：

1. 上传 Markdown 或文本文件。
2. 在文档列表中预览内容。
3. 点击“入库”或“全部入库”，将文档切分、向量化并写入 Milvus。
4. 在模型设置中配置对话模型并测试连接。
5. 使用桌宠或 API 进行问答。

管理台默认使用当前后端地址作为 API 地址。也可以在浏览器 localStorage 中设置 `knowrag-api-base` 指向其它后端。

## Milvus 配置

项目默认使用 Milvus Lite，数据保存在本地文件中，适合个人开发和轻量知识库。

代码默认值：

```text
MILVUS_LITE_ENABLED=true
MILVUS_LITE_PATH=./data/milvus.db
MILVUS_COLLECTION=knowrag_chunks
MILVUS_VECTOR_DIM=4096
MILVUS_METRIC_TYPE=COSINE
```

如果 `.env` 中没有写 `MILVUS_LITE_ENABLED`，代码会按 `true` 处理。

如需切换为 Docker 版 Milvus：

```powershell
python scripts/start_milvus.py
```

停止 Docker 版 Milvus：

```powershell
python scripts/stop_milvus.py
```

切换到 Docker 版时，建议在 `.env` 中显式配置：

```text
MILVUS_LITE_ENABLED=false
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION=knowrag_chunks
```

注意：Milvus Lite 和 Docker 版 Milvus 的数据不互通，切换后需要重新入库文档。

## 桌面宠物

桌宠位于 `desktop-pet/`，通过后端 `/api/chat/stream` 进行流式问答。

安装依赖：

```powershell
cd desktop-pet
npm install
```

开发运行：

```powershell
npm run tauri dev
```

只启动 Vite 前端预览：

```powershell
npm run dev
```

构建前端资源：

```powershell
npm run build
```

运行桌宠前，请先启动后端。桌宠默认连接：

```text
http://127.0.0.1:8000
```

如需修改后端地址，可以在 `desktop-pet/.env` 中设置：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

桌宠主要入口：

- 主宠物窗口：`PetMain.vue`
- 轻量输入框：`PetChatInput.vue`
- 完整聊天面板：`FullChatPanel.vue`
- 桌宠内置管理台：`AdminView.vue`

## API 入口

常用接口：

```text
POST   /api/documents/upload          上传文档
GET    /api/documents                 获取文档列表
GET    /api/documents/{id}            获取文档详情和 chunk 元数据
POST   /api/documents/{id}/index      对文档执行入库
DELETE /api/documents/{id}            删除文档

POST   /api/ingestion/clean           清洗 Markdown
POST   /api/ingestion/chunk           清洗并切分 Markdown
POST   /api/ingestion/vectorize       生成 embedding 预览
POST   /api/ingestion/index           执行完整离线入库

POST   /api/retrieval/search          检索 chunk
POST   /api/chat/stream               SSE 流式 RAG 问答

GET    /api/settings/chat-model       获取对话模型配置
PUT    /api/settings/chat-model       保存对话模型配置
POST   /api/settings/chat-model/test  测试对话模型连接
```

## 检索和 RAG 配置

主要环境变量：

```text
CHUNK_MAX_TOKENS=700
CHUNK_OVERLAP_TOKENS=100
CHUNK_MIN_TOKENS=80

SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-8B
SILICONFLOW_EMBEDDING_BATCH_SIZE=16
SILICONFLOW_EMBEDDING_TIMEOUT_SECONDS=60

RAG_MIN_SCORE=0.83
RAG_RERANK_TOP_N=20
RETRIEVAL_LOG_ENABLED=true
RETRIEVAL_DENSE_WEIGHT=0.1
RETRIEVAL_SPARSE_WEIGHT=0.9
RETRIEVAL_CANDIDATE_LIMIT=20

QUERY_ROUTER_MIN_CONFIDENCE=0.65
QUERY_ROUTER_EMBEDDING_THRESHOLD=0.70
QUERY_ROUTER_LLM_ENABLED=true
```

当前默认混合检索偏向中文 BM25：

```text
WeightedRanker(dense=0.1, sparse=0.9)
```

如果你的文档更偏语义问答，可以尝试提高 `RETRIEVAL_DENSE_WEIGHT`，并用评测脚本重新验证。

## 评测

检索评测数据集：

```text
evaluation/retrieval_seed.jsonl
```

运行 retrieval 评测：

```powershell
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_seed.jsonl --top-k 5
```

报告默认写入：

```text
evaluation/reports/
```

最近一次 30 条评测的结果示例：

```text
Cases: 30
Errors: 0
Recall@5: 0.9565
MRR: 0.9130
Precision@1: 0.8696
Recommended RAG_MIN_SCORE: 0.863217
```

端到端 RAG 回答评测：

```powershell
python scripts/evaluate_rag_answer.py --dataset evaluation/retrieval_seed.jsonl
```

回答评测会调用生成模型作为 judge，运行前需要确认模型配置可用。

## 测试

后端测试：

```powershell
python -m unittest
```

桌宠前端测试：

```powershell
cd desktop-pet
npm test
```

桌宠构建检查：

```powershell
cd desktop-pet
npm run build
```

## 常见问题

### 1. 入库时报 `Missing SILICONFLOW_API_KEY`

`.env` 中没有配置 `SILICONFLOW_API_KEY`，或者当前启动目录读不到 `.env`。项目会同时尝试读取当前目录和项目根目录下的 `.env`。

### 2. 检索评测全部报错

先看报告里的 `error` 字段：

- Embedding 请求失败：检查 `SILICONFLOW_API_KEY`、网络和 base URL。
- Milvus 连接失败：确认 Milvus Lite 路径可写，或 Docker 版 Milvus 已启动。
- `valid=false`：说明评测过程中存在异常，不能把 Recall/MRR 当作有效质量指标。

### 3. 修改 chunk 参数后效果没变

已经入库的文档不会自动重切分。需要删除旧文档或重新入库，才能让新的 `CHUNK_MAX_TOKENS`、`CHUNK_OVERLAP_TOKENS` 等配置生效。

### 4. 切换 Milvus Lite 和 Docker Milvus 后检索不到文档

两者的数据不共享。切换后需要重新上传或重新入库文档。

### 5. 桌宠无法回答或一直显示错误

先确认：

- 后端正在运行：http://127.0.0.1:8000/
- 桌宠的 `VITE_API_BASE_URL` 指向正确后端。
- 管理台里对话模型连接测试通过。
- 知识库文档已经入库。

## 开发提示

- 本地数据默认写入 `data/`，包括 SQLite、Milvus Lite 和模型设置。
- `.env` 不应提交到 Git。
- `evaluation/reports/` 中的评测报告用于对比检索质量。
- 修改 RAG 阈值、检索权重、chunk 策略后，建议至少跑一轮 retrieval 评测。
