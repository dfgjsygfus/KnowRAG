# KnowPET
基于rag的知识库问答系统

## 检索评测

仓库内置 15 条种子问题，用于评估向量检索的 `Recall@K`、`MRR`，并根据可回答与不可回答问题的分数分布推荐 `RAG_MIN_SCORE`。

确保 Milvus 已启动、种子文档已经入库，并配置好 Embedding API 后运行：

```powershell
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_seed.jsonl --top-k 5
```

评测报告默认写入 `evaluation/reports/`。线上检索会记录不包含正文和向量的结构化元数据日志，可通过以下配置关闭：

```text
RETRIEVAL_LOG_ENABLED=false
```
