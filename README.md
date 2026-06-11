# KnowPET
基于rag的知识库问答系统

## 检索评测

仓库内置 15 条种子问题，用于评估向量检索的 `Recall@K`、`MRR`，并根据可回答与不可回答问题的分数分布推荐 `RAG_MIN_SCORE`。

确保 Milvus 已启动、种子文档已经入库，并配置好 Embedding API 后运行。报告中的
`valid=false` 表示存在检索错误，此时不能把 `Recall@K` 当作有效质量指标：

```powershell
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_seed.jsonl --top-k 5
```

评测报告默认写入 `evaluation/reports/`。线上检索会记录不包含正文和向量的结构化元数据日志，可通过以下配置关闭：

```text
RETRIEVAL_LOG_ENABLED=false
```

中文 BM25 使用 Jieba tokenizer。若 collection 是旧 schema 创建的，需要重建 collection
并重新索引文档后才会生效。

当前混合检索默认使用 `WeightedRanker(0.1, 0.9)`，即向量检索权重 0.1、
中文 BM25 权重 0.9；可通过 `RETRIEVAL_DENSE_WEIGHT`、`RETRIEVAL_SPARSE_WEIGHT`
和 `RETRIEVAL_CANDIDATE_LIMIT` 调整。
