# KnowRAG 用户问题意图路由设计

日期：2026-06-06

## 目标

用户向桌面宠物提问后，系统先识别问题意图，再决定是否检索知识库。

第一版只支持两类意图：

- `knowledge_query`：知识库问题，执行 Milvus 检索并基于引用回答。
- `casual_chat`：闲聊问题，不检索知识库，直接调用当前生成模型回答。

## 路由策略

采用“规则优先、模型兜底、失败默认检索”的策略。

### 规则识别

以下类型直接识别为闲聊：

- 问候，例如“你好”“早上好”。
- 感谢，例如“谢谢”“辛苦了”。
- 身份交流，例如“你是谁”“你叫什么名字”。
- 简短告别，例如“再见”“拜拜”。

以下类型直接识别为知识库问题：

- 明确提到“文档”“资料”“知识库”。
- 包含常见知识询问表达，例如“是什么”“怎么”“如何”“为什么”。
- 包含代码标识特征，例如 `snake_case()`、大写常量名。

### 模型兜底

规则无法判断时，调用当前 OpenAI-compatible 生成模型进行二分类。

模型必须返回 JSON：

```json
{
  "intent": "knowledge_query",
  "confidence": 0.82,
  "reason": "用户询问系统实现细节"
}
```

置信度低于 `0.65`、返回格式错误或模型调用失败时，默认使用 `knowledge_query`。

## 组件

### Schema

`backend/app/schemas/query_routing.py`

- `QueryIntent`：意图枚举。
- `QueryRoute`：意图、置信度、原因和识别方式。

### Service

`backend/app/services/query_router.py`

- 执行规则识别。
- 调用可注入的分类客户端进行模型兜底。
- 校验模型 JSON。
- 在低置信度或错误时返回知识库意图。

### 问答编排

`stream_rag_answer()` 在检索前调用 Query Router，并新增 SSE 事件：

```text
event: routing
data: {"intent":"knowledge_query","confidence":0.9,"method":"rule"}
```

`knowledge_query` 保持当前 RAG 流程。

`casual_chat` 不执行检索，发送空 sources，并使用不要求引用的闲聊 Prompt 调用当前生成模型。

## 错误处理

- 意图分类模型失败：回退到 `knowledge_query`。
- 意图分类 JSON 无效：回退到 `knowledge_query`。
- 低置信度：回退到 `knowledge_query`。
- 闲聊生成失败：沿用当前 SSE 通用错误处理。

## 配置

```text
QUERY_ROUTER_MIN_CONFIDENCE=0.65
QUERY_ROUTER_LLM_ENABLED=true
```

关闭模型路由后，规则无法判断的问题直接进入知识库检索。

## 测试

- 问候和感谢被识别为闲聊。
- 明确知识问题被识别为知识库问题。
- 模糊问题使用模型分类。
- 低置信度和模型错误默认走知识库。
- 闲聊不调用检索服务。
- 知识库问题保持现有检索和引用行为。
- SSE 返回 routing 事件。

## 验收标准

- 用户输入“你好”时不调用 Milvus。
- 用户输入“ChiefArchitect 的职责是什么？”时执行知识库检索。
- 分类服务不可用时不影响知识库问答。
- 完整 Python 与桌面宠物测试通过。
