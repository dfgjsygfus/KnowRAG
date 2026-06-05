# KnowRAG 检索评测与阈值校准设计

日期：2026-06-05

## 目标

为当前向量检索链路建立可重复执行的离线评测闭环，并为 `RAG_MIN_SCORE` 提供数据驱动的推荐值。

第一版使用 15 条种子问题：

- 10 条资料内可回答问题。
- 3 条精确关键词或代码问题。
- 2 条资料外不可回答问题。

## 方案

采用轻量 JSONL 数据集和 Python 脚本，不引入新的评测框架依赖。

评测数据保存到 `evaluation/retrieval_seed.jsonl`。每条记录包含：

```json
{
  "id": "chief-001",
  "question": "ChiefArchitect 的核心职责是什么？",
  "answerable": true,
  "expected_source_paths": ["docs/2.2.1 Agent - ChiefArchitect（总架构师）.md"],
  "expected_heading_keywords": ["核心职责"]
}
```

不可回答问题设置 `answerable: false`，不填写期望来源。

## 组件

### 评测服务

`backend/app/services/retrieval_evaluation.py` 负责：

- 加载和校验 JSONL 数据。
- 调用可注入的检索函数。
- 判断命中结果是否满足期望来源和标题关键词。
- 计算 Recall@K、MRR。
- 汇总可回答问题与不可回答问题的最高分。
- 遍历候选阈值，推荐平衡正确接受和正确拒答的阈值。

### 命令行脚本

`scripts/evaluate_retrieval.py` 负责运行真实检索并输出 JSON 报告：

```powershell
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_seed.jsonl --top-k 5
```

报告保存到 `evaluation/reports/`，该目录加入 `.gitignore`。

### 检索日志

`retrieval_service.retrieve_query()` 在一次检索完成后记录结构化 JSON 日志，包含：

- query
- top_k
- collection
- elapsed_ms
- total
- 命中 chunk ID 和 score

不记录 embedding 向量、API Key 或完整文档内容。

通过 `RETRIEVAL_LOG_ENABLED` 控制是否启用，默认启用。

## 指标定义

- `Recall@K`：可回答问题中，期望 chunk 是否出现在 Top K。
- `MRR`：第一个正确结果排名倒数的平均值。
- `answerable_top_scores`：可回答问题的最高检索分数。
- `unanswerable_top_scores`：不可回答问题的最高检索分数。
- `recommended_min_score`：在候选阈值中，使可回答问题正确接受率与不可回答问题正确拒绝率平均值最高的阈值。

阈值相同时优先选择更高阈值，减少资料不足时的幻觉风险。

## 错误处理

- JSONL 格式错误时指出具体行号。
- 缺少问题 ID、问题文本或 `answerable` 时拒绝运行。
- 可回答问题没有期望来源或标题关键词时拒绝运行。
- 单条检索失败时记录错误并继续评测，其指标按未命中计算。

## 测试

- 评测集加载和字段校验。
- Recall@K 与 MRR 计算。
- 不可回答问题处理。
- 阈值推荐。
- 检索失败继续执行。
- 检索结构化日志不包含向量和正文。

## 验收标准

- 15 条种子评测集可被成功加载。
- 使用 Fake Retriever 的单元测试可以稳定验证指标和阈值逻辑。
- 真实脚本可调用当前 Milvus 检索链路并输出报告。
- 完整 Python 测试与桌面宠物测试继续通过。

## 首次真实基线

在 2026-06-05 使用当前 Milvus 索引和 `top_k=5` 运行：

- Recall@5：0.4615
- MRR：0.3013
- 推荐最低分：0.494734

默认 `RAG_MIN_SCORE` 取便于维护且接近推荐值的 `0.50`。当前召回仍有明显提升空间，后续应优先增加混合检索与重排，而不是继续单独降低阈值。
