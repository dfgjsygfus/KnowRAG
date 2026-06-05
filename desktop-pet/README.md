# KnowRAG Desktop Pet

静态小狗桌宠 MVP。点击小狗展开单轮问答面板，答案通过 KnowRAG 后端流式返回，并展示引用来源。

## 配置

在项目根目录 `.env` 中配置：

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

`OPENAI_BASE_URL` 使用 OpenAI-compatible API 的 `/v1` 地址，客户端会自动追加 `/chat/completions`。
未配置 `OPENAI_*` 时，会自动复用现有 `SILICONFLOW_API_KEY` 和 `SILICONFLOW_BASE_URL`，默认对话模型为 `Qwen/Qwen3-8B`。

`RAG_MIN_SCORE` 控制检索相关度阈值，默认 `0.55`。低于阈值的片段不会交给生成模型。

## 开发运行

先启动 Milvus 和 FastAPI 后端，再运行桌宠：

```powershell
uvicorn main:app --reload
cd desktop-pet
npm.cmd install
npm.cmd run tauri dev
```

仅预览问答界面：

```powershell
cd desktop-pet
npm.cmd run dev
```

Windows 构建 Tauri 需要安装 Microsoft C++ Build Tools（Desktop development with C++）和 WebView2。
