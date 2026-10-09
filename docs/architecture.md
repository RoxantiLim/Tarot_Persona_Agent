# Architecture

这个项目由本地资料处理、FastAPI 服务、Next.js 前端和 Persona Agent 组成。核心目标不是把塔罗内容写死在 prompt 里，而是让 Agent 在回答前先检索资料和案例，再把来源、牌面和占卜师画像合成到一次解读中。

## 系统总览

```mermaid
flowchart LR
    User["用户 / 朋友试用"] --> Web["Next.js 前端<br/>web/"]
    Friend["Cloudflare Quick Tunnel<br/>trycloudflare.com"] --> Web
    Web --> Proxy["Next.js /api/* 代理"]
    Proxy --> API["FastAPI<br/>api/main.py"]
    API --> RAG["RAG 检索链<br/>src/tarot_agent/rag_chain.py"]
    API --> Agent["LangGraph Persona Agent<br/>src/tarot_agent/agent_graph.py"]
    RAG --> Store["ChromaDB / NumPy 向量索引<br/>data/indexes/"]
    RAG --> Chunks["资料切块<br/>data/processed/document_chunks.jsonl"]
    Agent --> Cases["相似案例<br/>data/cases/*_reviewed.jsonl"]
    Agent --> Personas["占卜师画像<br/>data/personas/"]
    RAG --> LLM["DeepSeek OpenAI-compatible API"]
    Agent --> LLM
```

## 知识库问答流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant W as Next.js
    participant A as FastAPI
    participant R as RAG Chain
    participant V as Vector Store
    participant L as LLM

    U->>W: 输入牌意/主题/资料问题
    W->>A: POST /api/knowledge/query
    A->>R: answer_knowledge_query()
    R->>V: retrieve_context(query, top_k)
    V-->>R: 候选文档 + retrieval_score
    R->>R: rerank_documents()
    R->>L: prompt + context docs
    L-->>R: 回答
    R-->>A: answer + sources + documents
    A-->>W: JSON
    W-->>U: 回答、来源、片段
```

## Persona Agent 流程

```mermaid
flowchart TD
    Start["输入问题 + 三张牌 + reader_id"] --> Parse["parse_user_input<br/>拼接检索 query"]
    Parse --> Knowledge["retrieve_tarot_knowledge<br/>检索塔罗知识"]
    Knowledge --> Cases["retrieve_reader_cases<br/>检索相似案例"]
    Cases --> Persona["load_persona_profile<br/>加载占卜师画像"]
    Persona --> Generate["generate_reading<br/>生成解读"]
    Generate --> Check{"include_check?"}
    Check -->|是| Style["style_and_grounding_check<br/>风格与用牌自检"]
    Check -->|否| End["返回 answer/debug/docs/cases"]
    Style --> End
```

## 临时分享链路

```mermaid
flowchart LR
    Friend["朋友浏览器"] --> CF["Cloudflare Quick Tunnel<br/>随机 trycloudflare.com"]
    CF --> LocalWeb["本机 Next.js<br/>127.0.0.1:3000"]
    LocalWeb --> LocalApi["本机 FastAPI<br/>127.0.0.1:8787"]
    LocalApi --> LocalData["本机私有资料/索引/模型缓存"]
```

`scripts/start_share.ps1` 只把 Next.js 前端暴露给 Cloudflare，不直接暴露 FastAPI。朋友访问公网链接时，请求先到前端，再由前端的 `/api/*` 代理转发到本机 FastAPI。

Cloudflare Quick Tunnel 只适合测试和开发：链接是随机临时地址，不承诺生产稳定性。用完后运行 `scripts/stop_share.ps1` 关闭 tunnel。

## 私有数据边界

- `Doc/`、`Tarotist-*`、`Cards-png/`、`data/indexes/`、`data/processed/` 和模型缓存默认留在本机。
- `.env` 存放 API key，不提交到 Git。
- 面向实习展示时，建议公开代码、架构、截图、评估方法和脱敏样例，不公开原始资料与完整索引。
