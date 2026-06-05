# 桌宠在线问答 MVP 设计

日期：2026-06-05

## 目标

实现一个以静态小狗图片为入口的桌宠问答 MVP。用户点击桌宠展开问答面板，输入一个问题后，桌宠通过 KnowRAG 后端检索本地知识库并流式展示答案与引用来源。

## 本轮范围

- 创建 Tauri + Vue 3 桌宠客户端。
- 使用用户提供的小狗 PNG 作为静态桌宠图片。
- 桌宠窗口透明、置顶、可拖动。
- 点击小狗展开或收起单轮问答面板。
- 面板通过流式 API 展示答案。
- 回答完成后展示引用来源，可展开查看原文。
- 后端无检索结果时返回“资料不足”，不调用生成模型。
- 保留现有 Web 管理台和 `/api/retrieval/search` 检索测试接口。

## 非目标

- 不做动画、语音、多轮会话、长期记忆、拖拽入库、托盘菜单和安装器。
- 不做知识库选择；MVP 使用当前 Milvus collection 中的全部已入库内容。
- 不引入 LangChain 等编排框架。

## 后端设计

新增 OpenAI-compatible 生成客户端，复用 `.env` 中的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL`。客户端调用 `/chat/completions` 并解析 SSE 数据。

新增 `POST /api/chat/stream`：

```json
{
  "question": "ChiefArchitect 的职责是什么？",
  "top_k": 5
}
```

接口使用 SSE 返回以下事件：

```text
event: status
data: {"state":"thinking"}

event: sources
data: {"sources":[...]}

event: delta
data: {"content":"..."}

event: done
data: {"state":"success"}
```

错误使用 `event: error` 返回可展示消息。检索为空时直接发送空来源、“我在资料里没有找到足够信息。”和 `done`。

RAG Prompt 要求模型仅基于提供的上下文回答，资料不足时明确说明，并使用 `[1]`、`[2]` 引用来源。

## 桌宠设计

新增独立 `desktop-pet/` 前端项目。窗口默认仅显示静态小狗；点击小狗展开右侧问答面板。面板包含问题输入框、发送按钮、流式答案区域和来源折叠列表。

客户端状态仅用于文案：

- `idle`：等待点击或提问。
- `thinking`：正在检索资料。
- `answering`：正在流式接收回答。
- `success`：回答完成。
- `empty`：资料不足。
- `error`：后端或模型调用失败。

## 错误处理

- 后端不可用：面板提示无法连接知识库服务。
- 未配置生成模型：SSE 返回配置缺失错误。
- 检索失败或生成失败：SSE 返回错误事件，客户端恢复可再次提问状态。
- 空问题：客户端阻止发送，后端 Pydantic 校验拒绝。

## 测试与验收

- 单元测试覆盖生成客户端流解析、Prompt 构造、空检索短路和流式问答事件。
- 路由测试覆盖 `/api/chat/stream` 的 SSE 响应。
- 后端完整测试通过。
- 桌宠前端生产构建和 Tauri Rust 检查通过。
- 手动启动时可以点击小狗展开面板并提交问题。
