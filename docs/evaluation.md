# Evaluation

这个项目的 eval 目标是证明系统工程可信度：检索能找到资料，回答能带来源，Persona Agent 能按步骤使用用户给的牌。第一版不评价“占卜准不准”，也不急着接第三方平台。

## Eval 和测试的区别

普通测试回答“代码有没有坏”。例如 rerank 排序是否正确、API 返回结构是否符合预期。

AI eval 回答“模型系统质量有没有退步”。例如同一个问题换 prompt 后，检索来源是否变差；Agent 是否漏用了某张牌；生成回答是否引入用户没有给的牌。

## 本项目的三层评估

1. **检索评估**
   - 输入：用户问题。
   - 检查：是否返回文档、期望来源是否出现在 top-k、期望关键词是否出现在上下文。
   - 价值：证明 RAG 不是盲答。

2. **回答评估**
   - 输入：问题 + 检索上下文。
   - 检查：回答是否非空、是否能覆盖期望关键词、是否有来源片段支撑。
   - 价值：证明生成结果可以回到资料。

3. **Agent 行为评估**
   - 输入：问题 + reader_id + 三张牌。
   - 检查：是否使用全部用户牌、是否出现额外牌、是否执行完整步骤、是否返回 knowledge docs 和 similar cases。
   - 价值：证明 LangGraph 流程和约束在工作。

## 数据格式

RAG 样例放在 `data/evals/rag_knowledge.jsonl`：

```json
{
  "id": "rag_001",
  "query": "What makes a deck a Tarot deck?",
  "mode": "资料检索",
  "top_k": 5,
  "expected_sources": ["the-tarot-history-symbolism-and-divination-9781440649752-1440649758.pdf"],
  "expected_terms": ["Major Arcana", "Fool", "trumps"],
  "notes": "Checks whether retrieval finds the passage defining Tarot."
}
```

Agent 样例放在 `data/evals/persona_reading.jsonl`：

```json
{
  "id": "agent_001",
  "reader_id": "tarotist_1",
  "question": "我最近适合换实习方向吗？",
  "cards": [
    {"name": "权杖二", "orientation": "正位"},
    {"name": "宝剑八", "orientation": "逆位"},
    {"name": "星币三", "orientation": "正位"}
  ],
  "must_include_cards": ["权杖二", "宝剑八", "星币三"],
  "forbidden_cards": [],
  "expected_behavior": ["使用全部三张牌", "不要新增无关牌", "结合行动建议"]
}
```

## 运行方式

完整评估会调用 LLM：

```powershell
$AuxRoot = "E:\for-LLM\AUXI\Tarot_Persona_Agent"
& "$AuxRoot\.venv-clean\Scripts\python.exe" scripts\run_eval.py
```

如果只想验证检索和结构，不调用 LLM：

```powershell
$AuxRoot = "E:\for-LLM\AUXI\Tarot_Persona_Agent"
& "$AuxRoot\.venv-clean\Scripts\python.exe" scripts\run_eval.py --skip-generation
```

输出文件：

- `data/reports/eval_report.json`：机器可读的完整结果。
- `docs/evaluation_report.md`：适合放进项目展示的 Markdown 报告。

## 如何使用失败案例

失败案例不是坏事。它们是下一轮改进的输入。

- 检索失败：检查 query、切块、metadata、rerank 权重或向量索引。
- 回答失败：检查 prompt 是否要求引用资料，或上下文是否不足。
- 漏牌/加牌：检查 `generate_reading` 的系统提示、重试逻辑和 forbidden card 检查。
- steps 缺失：检查 LangGraph 节点或 fallback 路径。

每次修改 prompt、rerank、模型、索引或案例数据后，都重新运行 `scripts/run_eval.py`，比较报告结果是否退步。
