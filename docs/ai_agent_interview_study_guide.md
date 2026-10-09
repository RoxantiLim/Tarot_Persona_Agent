# AI Agent 实习面试项目学习文档

本文档根据当前简历和本项目 `Tarot Persona Agent` 的实际代码整理，目标是帮助你从“项目主要由 Codex 辅助完成”过渡到“我能作为项目负责人讲清楚设计、流程、细节和边界”。

建议学习顺序：

1. 先背熟“项目 2 分钟介绍”和“核心一句话”。
2. 再理解 LangGraph Agent 的每个节点输入输出。
3. 再理解 RAG 从入库到检索的数据结构。
4. 最后练习面试官追问和参考回答。

---

## 1. 项目一句话定位

这个项目不是单纯的聊天机器人，而是一个本地运行的“塔罗知识库 + 多 Persona 解读 Agent”。

它有两条主线：

1. 知识库助手：用户问牌意、主题、资料出处，系统从 PDF 知识库检索片段，再让 LLM 基于资料回答。
2. Persona Agent：用户输入问题和三张牌，系统检索塔罗资料、召回相似历史案例、加载占卜师画像，再生成不同风格的解读。

面试时可以这样说：

> 我这个项目更偏 workflow-based Agent，不是完全开放式自主 Agent。我用 LangGraph 把问题解析、知识检索、案例召回、Persona 加载、回答生成和结果校验拆成可观察节点，重点是让 RAG、历史案例和角色画像稳定协同。

---

## 2. 项目 2 分钟介绍背诵版

> 我做的是一个本地运行的塔罗 Persona Agent 项目，目标不是让模型凭空占卜，而是把领域资料、历史案例和不同占卜师画像结合起来，生成可追溯、风格稳定的回答。
>
> 系统分成资料入库、RAG 检索、Persona Agent 和前端展示几部分。资料入库阶段，我用 PyMuPDF 提取 PDF 文本，扫描页用 RapidOCR，按段落切成 chunk，并给每个 chunk 保存来源文件、页码、内容类型、质量状态和权重。embedding 使用本地 BAAI/bge-m3，向量库使用 ChromaDB，同时保留 NumPy fallback。
>
> 用户做知识库查询时，系统先向量召回候选片段，再根据质量权重 rerank，并限制同页 chunk 数，最后让 DeepSeek 基于资料生成回答和来源。
>
> 用户做占卜解读时，我用 LangGraph 编排 Agent 流程：先把问题和三张牌拼成 query，检索塔罗知识，再召回对应占卜师的相似案例，然后加载结构化 Persona 画像，最后生成回答。生成后还会检查是否漏用了用户给的牌，如果漏牌会触发一次重试。
>
> 这个项目目前是本地 Demo，不是生产系统。它的核心链路已经跑通，有 7 份 PDF、1653 个入库 chunk、260 条审核案例，并且有基础单元测试和离线 eval。后续我会优先优化案例向量检索、评估体系、日志和部署安全。

---

## 3. 当前项目真实数字

这些数字非常适合在面试里主动说出来，会显得项目真实、具体、有工程痕迹。

- PDF 资料：7 份。
- 提取文本块：1738 个 chunk。
- 实际进入索引：1653 个 chunk。
- 排除低价值 chunk：85 个。
- 降权 chunk：95 个。
- 文本页：806 页。
- OCR 页：310 页。
- 仍需 OCR 或质量处理页：11 页。
- 审核案例：`tarotist_1` 有 140 条，`tarotist_2` 有 120 条。
- 当前向量库后端：ChromaDB。
- 离线 eval：RAG 5/5 通过，Agent 3/3 通过。

可以这样说：

> 当前项目不是空 Demo，已经有真实资料入库和案例数据。知识库来自 7 份 PDF，最终 1653 个有效 chunk 进入索引；两个占卜师各有 reviewed 案例，总计 260 条。评估上有基础的 RAG 和 Agent 离线检查，当前结构评估是 RAG 5/5、Agent 3/3 通过。

---

## 4. 系统分层

项目分四层：

1. 核心 Python 模块：`src/tarot_agent/`
   负责配置、PDF 入库、embedding、向量检索、RAG、Persona、案例召回、LangGraph Agent。

2. FastAPI：`api/main.py`
   把 Python 能力封装成本地 HTTP API，给前端调用。

3. Next.js 前端：`web/`
   提供用户侧页面：知识库助手、占卜解读、状态页。

4. Streamlit 后台：`app.py`
   更像内部管理台，用于资料入库、案例审核、画像编辑、状态检查。

核心文件：

- `src/tarot_agent/agent_graph.py`：Persona Agent 工作流。
- `src/tarot_agent/rag_chain.py`：知识库检索与回答。
- `src/tarot_agent/pdf_ingest.py`：PDF/OCR/切块入库。
- `src/tarot_agent/vector_store.py`：ChromaDB 和 NumPy 向量索引。
- `src/tarot_agent/persona.py`：占卜师画像加载。
- `src/tarot_agent/cases.py`：截图案例抽取、清洗、相似案例召回。
- `api/main.py`：FastAPI 接口入口。
- `web/app/reading/page.tsx`：占卜解读页面。
- `web/app/knowledge/page.tsx`：知识库助手页面。

---

## 5. LangGraph Agent 深入讲解

### 5.1 Agent 的本质

这个 Agent 的本质是：用一个共享的 `ReadingState` 字典，在多个节点之间逐步补充信息。

每个节点不是独立聊天，而是：

> 读取 State 的一部分，完成一个明确任务，再往 State 写入新的字段。

`ReadingState` 大致如下：

```python
class ReadingState(TypedDict, total=False):
    reader_id: str
    question: str
    cards: list[dict[str, str]]
    query: str
    knowledge_docs: list[Any]
    similar_cases: list[dict[str, Any]]
    persona: dict[str, Any]
    answer: str
    check: str
    steps: list[str]
```

你可以把 `ReadingState` 理解成 Agent 的“工作台”。一开始工作台上只有用户输入，后面每个节点往上面放新材料。

### 5.2 初始输入

入口函数是 `run_persona_reading()`。

初始 State：

```python
initial_state = {
    "reader_id": reader_id,
    "question": question,
    "cards": cards,
    "steps": [],
}
```

比如用户输入：

```json
{
  "reader_id": "tarotist_1",
  "question": "我最近适合换实习方向吗？",
  "cards": [
    {"name": "权杖二", "orientation": "正位"},
    {"name": "宝剑八", "orientation": "逆位"},
    {"name": "星币三", "orientation": "正位"}
  ]
}
```

这时 State 里只有：

- `reader_id`：选择哪个占卜师风格。
- `question`：用户问题。
- `cards`：三张牌。
- `steps`：执行步骤记录。

---

### 5.3 节点 1：parse_user_input

输入：

```python
reader_id
question
cards
steps
```

做的事：

它把用户问题和三张牌拼成一个检索 query。

```python
cards_text = "权杖二（正位）；宝剑八（逆位）；星币三（正位）"
state["query"] = f"{question} {cards_text}"
```

输出新增：

```python
query
steps += ["parse_user_input"]
```

为什么需要这个节点？

因为后面检索知识库和案例库时，不能只搜用户问题，也要把牌面带进去。比如用户问“适合换方向吗”，如果不带牌，检索会很泛；带上“权杖二、宝剑八、星币三”之后，系统更容易找到对应牌意和相关案例。

面试回答：

> 这个节点负责把用户输入标准化成后续检索可用的 query。它不是复杂 NLP，而是把问题和牌面合并，保证知识检索和案例召回都能感知本次牌面。

---

### 5.4 节点 2：retrieve_tarot_knowledge

输入：

```python
query
config
```

调用：

```python
retrieve_context(config, state["query"], top_k=5, profile="agent")
```

输出新增：

```python
knowledge_docs
steps += ["retrieve_tarot_knowledge"]
```

`knowledge_docs` 是从塔罗 PDF 知识库里检索出来的文档片段。每个文档片段本质上是一个 LangChain `Document`：

```python
Document(
    page_content="这段资料正文...",
    metadata={
        "chunk_id": "...",
        "source_file": "...pdf",
        "page": 12,
        "content_type": "牌意",
        "quality_status": "keep",
        "retrieval_score": 0.72,
        "rerank_score": 0.72
    }
)
```

为什么 `profile="agent"`？

`agent` profile 会更偏向保留质量状态为 `keep` 的 chunk，把 `downrank` 的内容放后面。原因是 Agent 最终要生成面向用户的解读，不能让目录页、列表页、弱相关片段干扰回答。

面试回答：

> 这个节点给 Agent 提供领域知识依据。它不是让模型凭空解释牌，而是先从本地知识库里找和问题、牌面相关的资料片段，后面生成回答时作为参考上下文。

---

### 5.5 节点 3：retrieve_reader_cases

输入：

```python
reader_id
query
config
```

调用：

```python
retrieve_similar_cases(config, reader_id, query, limit=3)
```

输出新增：

```python
similar_cases
steps += ["retrieve_reader_cases"]
```

它会读取：

```text
data/cases/tarotist_1_reviewed.jsonl
data/cases/tarotist_2_reviewed.jsonl
```

每条案例大概包含：

```json
{
  "question": "用户问题",
  "background": "背景",
  "cards": [
    {"name": "星币一", "orientation": "逆位"}
  ],
  "reader_answer": "占卜师当时的回答",
  "reader_id": "tarotist_1"
}
```

注意：当前案例召回是关键词重合打分，不是向量检索。

它会把 query 里的词，和案例的 `question`、`background`、`reader_answer`、`cards` 拼起来比较，取最相似的几条。

为什么需要历史案例？

- 知识库解决的是“这张牌一般是什么意思”。
- 案例解决的是“这个占卜师面对类似问题通常怎么表达、怎么组织判断”。

面试回答：

> 我把知识资料和历史案例分开处理。知识库提供事实和牌意依据，历史案例提供风格和回答习惯。当前案例召回是关键词匹配，后续可以升级为 embedding 检索。

---

### 5.6 节点 4：load_persona_profile

输入：

```python
reader_id
config
```

调用：

```python
load_persona(config, reader_id)
```

输出新增：

```python
persona
steps += ["load_persona_profile"]
```

它会加载：

```text
data/personas/tarotist_1.json
data/personas/tarotist_2.json
```

画像结构不是一句“你是某某”，而是：

```json
{
  "reader_id": "tarotist_1",
  "display_name": "Tarotist 1",
  "tone": "直接、坦诚、略带口语化...",
  "answer_structure": ["先概括牌面整体基调..."],
  "common_phrases": ["牌面来说", "感觉", "这边建议"],
  "reasoning_style": "以牌面元素和正逆位为核心...",
  "avoid": ["过度美化或安慰", "使用复杂玄学术语"]
}
```

为什么要结构化？

因为结构化画像比一句 prompt 更稳定。模型能清楚知道：语气是什么、结构是什么、常用表达是什么、不能做什么。

面试回答：

> Persona 不是简单角色扮演，而是结构化配置。这样新增一个占卜师时，不需要改代码，只要新增一个 JSON 画像和对应案例即可。

---

### 5.7 节点 5：generate_reading

这是最核心节点。

输入：

```python
persona
question
cards
knowledge_docs
similar_cases
config
```

它先把相似案例拼成文本：

```text
问题：...
牌面：...
回答：...
```

如果没有案例，就写：

```text
未检索到相似案例。
```

然后把所有材料放进 `PERSONA_READING_TEMPLATE`：

```python
persona
question
cards
knowledge_context
case_context
```

其中 `knowledge_context` 来自 `format_context()`，格式大概是：

```text
[1] 来源：xxx.pdf 第 12 页
资料正文...

[2] 来源：yyy.pdf 第 35 页
资料正文...
```

它还额外设置了一个 system prompt：

```text
你是塔罗占卜回答生成器。
必须严格使用用户本次提供的牌面。
本次牌面只有：xxx。
禁止替换、增删或改写成其他牌。
```

这很关键。因为历史案例和知识库里可能出现其他牌名，如果不约束，模型可能会被上下文带偏。

输出新增：

```python
answer
steps += ["generate_reading"]
```

还有一个重要逻辑：漏牌重试。

生成后会调用：

```python
_missing_user_cards(answer, state["cards"])
```

如果用户给了三张牌，但回答里没出现某张牌名，就重新生成一次，并要求必须逐一使用这些牌。

输出可能额外新增：

```python
card_retry_missing
```

面试回答：

> generate_reading 节点不是简单把 prompt 发给模型。它会组合四类上下文：用户问题、本次牌面、知识库资料、历史案例、Persona 画像。生成后还会检查回答是否漏用了用户牌面，如果漏牌就触发一次低温重试。

---

### 5.8 节点 6：style_and_grounding_check

输入：

```python
persona
cards
answer
config
```

输出：

```python
check
steps += ["style_and_grounding_check"]
```

它调用 `STYLE_CHECK_TEMPLATE`，让模型检查：

1. 是否使用了用户牌面。
2. 是否符合风格。
3. 是否有过度绝对化。
4. 需要修改的建议。

注意：这个节点是可选的。

`run_persona_reading(..., include_check=True)` 时会跑；当前 Next.js 前端默认传的是 `include_check=false`，所以普通生成默认不跑这个节点。

面试回答：

> 我保留了一个风格和 grounding 检查节点，用于开发调试或质量评估。前端默认不开，是为了减少一次 LLM 调用和延迟，但后端支持开启。

---

### 5.9 LangGraph 边关系

图结构当前是线性的：

```text
parse_user_input
  -> retrieve_tarot_knowledge
  -> retrieve_reader_cases
  -> load_persona_profile
  -> generate_reading
  -> style_and_grounding_check 可选
  -> END
```

为什么当前没有复杂分支？

因为这个项目强调稳定可控，而不是让模型自由规划。它更像业务工作流 Agent。

面试回答：

> 当前 LangGraph 主要用来显式管理状态和节点，而不是做复杂自主规划。这样优点是流程可解释、可调试、适合 Demo 和业务原型。

---

### 5.10 LangGraph 失败兜底

`run_persona_reading()` 有一个 `try/except`。

如果 LangGraph 导入、编译或执行失败，它会手动按相同顺序调用这些节点：

```python
parse_user_input()
retrieve_tarot_knowledge()
retrieve_reader_cases()
load_persona_profile()
generate_reading()
style_and_grounding_check()
```

并写入：

```python
langgraph_fallback
```

这个设计很实用：即使 LangGraph 环境有问题，核心业务流程仍能跑。

面试回答：

> 我做了 LangGraph fallback。如果图编译或执行失败，系统会降级成普通函数链，保证 Demo 不会因为编排框架问题完全不可用。

---

### 5.11 最终返回结构

最后返回的是 `AgentResult`：

```python
AgentResult(
    answer=最终回答,
    debug={
        "reader_id": reader_id,
        "steps": [...],
        "style_check": "...",
        "card_retry_missing": [...],
        "langgraph_fallback": "..."
    },
    knowledge_docs=检索资料,
    similar_cases=相似案例
)
```

前端主要展示 `answer` 和引用资料；debug 更多给开发者排查。

---

## 6. RAG 入库到检索完整数据结构

### 6.1 总链路

RAG 从 PDF 到回答，经历了这些形态：

```text
PDF 文件
 -> page text
 -> DocumentChunk
 -> LangChain Document
 -> embedding vector
 -> ChromaDB / NumPy index
 -> retrieved Document
 -> reranked Document
 -> prompt context
 -> RAGResult / AgentResult
```

这条链路一定要背熟。面试官追问 RAG 细节时，你就按这条线讲。

---

### 6.2 第 1 层：原始 PDF

资料放在：

```text
Doc/
```

当前有 7 份 PDF。系统不会直接在用户提问时读 PDF，因为那样太慢。PDF 是离线入库时处理的。

入口脚本：

```text
scripts/ingest_documents.py
```

它会调用：

```python
ingest_pdfs_to_chunks(config)
write_processed_outputs(config, chunks, report)
build_vector_store(config, documents)
```

面试回答：

> 文档处理是离线阶段完成的。用户在线提问时只查已经构建好的索引，不会现场解析 PDF。

---

### 6.3 第 2 层：page text

每页 PDF 会被提取成：

```python
(page_index, text, extraction_method)
```

比如：

```python
(12, "这页提取出来的正文...", "pdf_text")
```

如果文字层太少，且开启 OCR，就可能是：

```python
(35, "OCR 识别出来的正文...", "ocr")
```

同时会记录：

```python
needs_ocr
stats
```

`stats` 里有：

```python
text_pages
ocr_pages
ocr_cache_hits
ocr_error_pages
```

为什么要保存 `extraction_method`？

因为后续评估质量时，OCR 内容可能比 PDF 文字层更容易出错。metadata 里保留这个字段，方便排查“这个错误是不是 OCR 造成的”。

---

### 6.4 第 3 层：DocumentChunk

这是入库阶段最核心的数据结构：

```python
class DocumentChunk(BaseModel):
    chunk_id: str
    source_file: str
    page: int
    chunk_index: int
    language: Literal["zh", "en", "mixed", "unknown"]
    content_type: str
    extraction_method: Literal["pdf_text", "ocr"]
    quality_status: Literal["keep", "downrank", "exclude"]
    quality_reasons: list[str]
    retrieval_weight: float
    text: str
```

举个例子：

```json
{
  "chunk_id": "塔罗逆位精解-p95-c0",
  "source_file": "塔罗逆位精解.pdf",
  "page": 95,
  "chunk_index": 0,
  "language": "zh",
  "content_type": "牌意",
  "extraction_method": "ocr",
  "quality_status": "keep",
  "quality_reasons": [],
  "retrieval_weight": 1.0,
  "text": "这段是具体牌意解释..."
}
```

字段作用：

- `chunk_id`：唯一 ID，用来写入 ChromaDB。
- `source_file`：回答时展示来源。
- `page`：回答时展示页码。
- `chunk_index`：同一页里的第几个 chunk。
- `language`：中文、英文、混合。
- `content_type`：牌意、历史、象征学、牌阵、占卜方法等。
- `extraction_method`：来自 PDF 文本层还是 OCR。
- `quality_status`：是否保留、降权、排除。
- `quality_reasons`：为什么降权或排除。
- `retrieval_weight`：rerank 时乘到分数上。
- `text`：真正进入知识库的正文。

面试官如果问“metadata 存了什么”，你就按这个讲。

---

### 6.5 第 4 层：质量过滤

入库时不是所有 chunk 都进索引。系统会判断：

```text
keep      正常保留
downrank  保留但降权
exclude   直接排除
```

会排除的内容包括：

- 目录页。
- 索引页。
- 参考文献。
- 版权页。
- 出版信息。
- 致谢、献词。
- 太短的碎片。
- 纯列表。
- 标题页。

降权内容包括：

- 信息密度较低的列表型内容。
- 较短但仍可能有价值的文本。

权重是：

```python
keep = 1.0
downrank = 0.45
exclude = 0.0
```

这就是为什么当前提取了 1738 个 chunk，但实际入库是 1653 个。

面试回答：

> 我在 RAG 入库阶段做了质量过滤，不是把所有 PDF 文本都丢进向量库。目录、版权页、参考文献这类内容会排除，弱信息片段会降权，这能减少检索噪声。

---

### 6.6 第 5 层：LangChain Document

`DocumentChunk` 不能直接给向量库，需要转换成 `Document`：

```python
Document(
    page_content=chunk.text,
    metadata={
        "chunk_id": chunk.chunk_id,
        "source_file": chunk.source_file,
        "page": chunk.page,
        "chunk_index": chunk.chunk_index,
        "language": chunk.language,
        "content_type": chunk.content_type,
        "extraction_method": chunk.extraction_method,
        "quality_status": chunk.quality_status,
        "quality_reasons": ",".join(chunk.quality_reasons),
        "retrieval_weight": chunk.retrieval_weight,
    }
)
```

注意：`exclude` 的 chunk 不会转换。

所以真正进入索引的是：

```text
keep + downrank
```

核心区别：

- `DocumentChunk` 是我们自己定义的入库数据结构。
- `Document` 是 LangChain 兼容的数据结构，用来给检索和向量库使用。

---

### 6.7 第 6 层：Embedding 向量

每个 `Document.page_content` 会被 embedding 模型转成向量。

当前模型：

```text
BAAI/bge-m3
```

代码里会设置：

```python
HF_HOME
SENTENCE_TRANSFORMERS_HOME
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

意思是尽量使用本地缓存，不在运行时联网下载。

生成向量后会 normalize：

```python
vectors = vectors / norm
```

为什么要 normalize？

因为后面用点积计算相似度时，向量已经归一化，点积就接近 cosine similarity。

---

### 6.8 第 7 层：向量索引

当前会写两个东西：

1. NumPy fallback：

```text
data/indexes/local_vectors/vectors.npy
data/indexes/local_vectors/documents.jsonl
```

2. ChromaDB：

```text
data/indexes/chroma/chroma.sqlite3
```

ChromaDB 里每条记录包括：

```python
ids = chunk_id
documents = page_content
metadatas = metadata
embeddings = vector
```

为什么同时保留 NumPy？

因为 ChromaDB 是主要检索后端，但本地 Demo 阶段可能遇到 Chroma 依赖、版本或数据损坏问题。NumPy fallback 可以保证最基本的向量检索仍然能跑。

面试回答：

> 我没有完全依赖单一向量库。构建索引时会写 Chroma，同时写本地 NumPy 向量矩阵和文档 JSONL，作为开发和恢复场景下的 fallback。

---

### 6.9 第 8 层：查询检索

输入：

```python
config
query
top_k
profile
```

比如知识库查询：

```python
retrieve_context(config, query, top_k=5, profile="knowledge")
```

Agent 查询：

```python
retrieve_context(config, query, top_k=5, profile="agent")
```

流程：

1. 检查索引是否存在。
2. 计算候选数量：

```python
candidate_k = max(top_k * 4, top_k)
```

如果 top_k=5，就先拿 20 个候选。

3. 根据配置选择检索模式：

```python
RETRIEVAL_MODE=vector
```

走向量检索。

如果是：

```python
RETRIEVAL_MODE=keyword
```

走关键词检索。

4. 向量检索会调用：

```python
store.similarity_search(query, k=candidate_k)
```

5. 每个返回文档会带上：

```python
retrieval_score
```

---

### 6.10 第 9 层：rerank

rerank 的核心公式：

```python
rerank_score = retrieval_score * retrieval_weight
```

如果一个 chunk 相似度很高，但是质量状态是 `downrank`，权重只有 0.45，那么它会被往后排。

同时：

```python
quality_status == "exclude"
```

会被直接跳过。

`profile="knowledge"` 和 `profile="agent"` 的区别：

- `knowledge`：按照 rerank_score 排。
- `agent`：更优先 keep，再补 downrank。

为什么 Agent 更严格？

因为 Agent 生成用户可见回答，低质量资料更容易干扰风格和结论。所以 Agent profile 先取高质量内容。

---

### 6.11 第 10 层：限制同页 chunk

它会限制：

```python
max_chunks_per_page = 2
```

同一个 PDF 同一页最多拿两个 chunk。

为什么？

因为向量检索可能连续召回同一页拆出来的多个相邻 chunk。如果不限制，上下文会被同一页内容占满，导致资料多样性下降。

面试回答：

> 我在 rerank 后还限制了同页 chunk 数，避免 top-k 被同一页的相邻片段占满，让上下文覆盖更多来源。

---

### 6.12 第 11 层：format_context

它把 Document 列表转成 prompt 里的资料上下文：

```text
[1] 来源：xxx.pdf 第 12 页
正文内容...

[2] 来源：yyy.pdf 第 35 页
正文内容...
```

如果没有检索结果：

```text
未检索到资料。
```

这一步很重要，因为它把 metadata 里的来源变成模型可见的文本。模型回答时就能知道资料来自哪里。

---

### 6.13 第 12 层：RAGResult

知识库问答最终返回：

```python
RAGResult(
    answer=answer,
    sources=source_list(docs),
    context_docs=docs,
    error=error
)
```

如果没有检索到资料：

```python
error = "没有检索到知识库片段，回答依据有限。"
```

也就是说系统不会假装资料充分。

---

## 7. 知识库 RAG 完整复述版

面试时可以这样完整讲：

> 入库阶段，我从 `Doc/` 读取 PDF。每页先用 PyMuPDF 提取文字，如果文字太少就用 RapidOCR，并缓存 OCR 结果。然后按段落和句子边界切成 chunk，每个 chunk 保存来源文件、页码、语言、内容类型、提取方式、质量状态和检索权重。质量过滤会排除目录、版权页、参考文献等低价值内容，弱信息片段会降权。
>
> 接着我把有效 chunk 转成 LangChain Document，用本地 BAAI/bge-m3 生成 embedding。索引层同时写 ChromaDB 和 NumPy fallback。
>
> 查询阶段，系统先根据用户 query 做向量召回，不是直接拿 top-k，而是先拿 top-k 的 4 倍候选，再根据 retrieval_score 和 retrieval_weight 做 rerank，并限制同一页最多两个 chunk。最后把文档片段格式化成带来源的上下文，交给 LLM 生成回答。

---

## 8. FastAPI 和前端交互

FastAPI 主要接口：

- `GET /api/health`：检查 key、索引、模型、chunk 数、案例数。
- `GET /api/cards`：返回 78 张牌和随机三张牌。
- `GET /api/readers`：返回可选 tarotist。
- `POST /api/knowledge/query`：知识库问答或纯资料检索。
- `POST /api/reading/generate`：Persona Agent 生成解读。

前端不是直接请求 `127.0.0.1:8787`，而是走 Next.js 的 `/api/*` 代理，再由代理转发到 FastAPI。

这样 Cloudflare 分享时只暴露前端 3000，后端 8787 仍留在本机。

面试回答：

> 我把前端和后端解耦。前端通过 Next.js 的 `/api/*` 代理访问 FastAPI，这样本地分享时只暴露前端入口，不直接暴露 FastAPI 服务。后端接口负责封装 RAG 和 Agent 能力，前端只关心请求和展示。

---

## 9. 评估和测试

项目有两类检查：

### 9.1 单元测试

覆盖内容包括：

- RAG rerank 排序是否正确。
- `downrank` 权重是否生效。
- Agent profile 是否更优先 keep chunk。
- 同页 chunk 限制是否生效。
- keyword 和 vector 路径是否共享 rerank。
- 质量过滤是否能排除目录、版权页、参考文献、纯列表等。
- override 是否能强制 keep/downrank/exclude。

### 9.2 离线 Eval

Eval 不是判断“占卜准不准”，而是判断系统链路有没有退步。

RAG eval 检查：

- 是否返回文档。
- 期望来源是否出现在 top-k。
- 期望关键词是否出现在上下文或回答里。

Agent eval 检查：

- 是否使用全部用户牌。
- 是否出现额外牌。
- 是否执行完整步骤。
- 是否返回 knowledge docs 和 similar cases。

当前结果：

- RAG：5/5 passed。
- Agent：3/3 passed。

面试回答：

> 我没有把评估定义成“占卜准不准”，因为这很主观。第一版 eval 主要验证工程链路：RAG 是否能召回资料，回答是否有上下文支撑，Agent 是否完整执行步骤，是否漏用或乱加用户没有给的牌。

---

## 10. 高频面试问题与参考回答

### 10.1 请介绍一下你的项目

参考回答：

> 这是一个本地运行的塔罗知识库和多 Persona 解读 Agent。它把 PDF 资料处理成 RAG 知识库，同时把历史占卜案例和占卜师画像结构化。用户可以做知识库查询，也可以输入问题和三张牌，让系统根据知识库、相似案例和 Persona 风格生成解读。
>
> 技术上，后端核心是 Python、LangGraph、RAG、ChromaDB、FastAPI，前端是 Next.js。资料入库用 PyMuPDF 和 RapidOCR，embedding 用本地 BAAI/bge-m3，生成模型用 DeepSeek OpenAI-compatible API。

### 10.2 为什么需要 Agent，直接 RAG 不行吗？

参考回答：

> 直接 RAG 可以解决“回答有依据”的问题，但我的项目不只是检索资料然后回答。它还要处理问题和牌面拼接、知识检索、历史案例召回、Persona 画像加载、回答生成和用牌校验。这些步骤之间有状态依赖，所以我用 LangGraph 显式编排成 workflow-based Agent。

### 10.3 你的 Agent 算真正的 Agent 吗？

参考回答：

> 严格说它更偏 workflow-based Agent，而不是完全开放式自主规划 Agent。流程由 LangGraph 固定，模型主要在生成和检查节点里发挥作用。这样牺牲了一部分自由度，但提高了可解释性、稳定性和可调试性，更适合业务 Demo。

### 10.4 LangGraph 给你带来了什么？

参考回答：

> 如果只是线性函数调用，也能实现基本功能。但 LangGraph 让状态、节点和边显式化。每个节点读写哪些字段都很清楚，debug 时可以看 steps、中间检索结果、案例结果和最终回答。后续要加条件分支，比如检索不足时改写 query、校验失败时重试，也更自然。

### 10.5 你的 State 怎么设计？

参考回答：

> State 里包括 reader_id、question、cards、query、knowledge_docs、similar_cases、persona、answer、check 和 steps。一开始只有用户输入，后面每个节点逐步补充字段。比如 parse 节点写 query，检索节点写 knowledge_docs，案例节点写 similar_cases，画像节点写 persona，生成节点写 answer。

### 10.6 RAG 入库流程是什么？

参考回答：

> 入库阶段先从 `Doc/` 读取 PDF，每页用 PyMuPDF 提取文字；如果文字太少，就用 RapidOCR 做 OCR，并缓存结果。然后按段落和句子边界切 chunk，给每个 chunk 保存来源、页码、语言、内容类型、质量状态和权重。低价值 chunk 会被排除或降权。最后用 BAAI/bge-m3 生成 embedding，写入 ChromaDB 和 NumPy fallback。

### 10.7 chunk size 怎么设置？

参考回答：

> 当前默认最大约 900 字符，不是简单硬切。优先按段落切，超长段落按句子边界切，短尾部会合并。这样是为了让 chunk 既有完整语义，又不会太长导致召回不精确。

### 10.8 metadata 存了什么？

参考回答：

> 每个 chunk 的 metadata 包括 chunk_id、source_file、page、chunk_index、language、content_type、extraction_method、quality_status、quality_reasons 和 retrieval_weight。source_file 和 page 用于来源展示，quality_status 和 retrieval_weight 用于 rerank，extraction_method 用于判断错误是否来自 OCR。

### 10.9 为什么要先召回 top_k * 4？

参考回答：

> 因为原始向量相似度不一定等于最终可用性。有些片段相似度高但质量差，比如目录或列表。先多召回一些候选，再结合质量权重 rerank，可以提高最终 top-k 的质量。

### 10.10 为什么不是所有 chunk 都入库？

参考回答：

> PDF 里有大量对问答没帮助的内容，比如目录、版权页、参考文献、标题页。它们会污染检索结果，所以我在入库阶段做质量过滤，`exclude` 不入库，`downrank` 降权保留。

### 10.11 Agent 里的知识检索和知识库助手里的检索一样吗？

参考回答：

> 底层都是 `retrieve_context()`，但 profile 不同。知识库助手默认是 `knowledge`，Agent 使用 `agent` profile，会更优先高质量 keep chunk，减少低质量资料干扰最终解读。

### 10.12 案例召回也是向量检索吗？

参考回答：

> 目前不是。知识库资料使用向量检索，历史案例召回为了简单稳定，采用的是关键词重合打分。它会把 query 里的词和案例的问题、背景、回答、牌名做匹配，取分数最高的几条。后续可以升级成案例 embedding 检索或混合检索。

### 10.13 多 Persona 是怎么实现的？

参考回答：

> 我不是简单写“你是某某占卜师”，而是把占卜师风格拆成结构化画像，包括 tone、answer_structure、common_phrases、reasoning_style 和 avoid。生成时会把画像和该占卜师的历史案例一起放进上下文，让模型同时参考风格配置和真实案例。

### 10.14 如果角色风格和事实依据冲突，优先哪个？

参考回答：

> 优先事实依据。Persona 只能影响表达方式、关注重点和组织结构，不能改变资料和牌面事实。prompt 中也会要求必须使用用户本次提供的牌面，不能替换、增删或改写成其他牌。

### 10.15 怎么防止模型漏用用户给的牌？

参考回答：

> 生成节点里有一个简单的结构校验。回答生成后，会检查三张用户牌是否都出现在回答中。如果发现漏牌，会触发一次低温重试，并明确要求回答必须逐一使用这些牌，不能提及其他牌。

### 10.16 如果检索不到资料怎么办？

参考回答：

> 知识库问答会返回“没有检索到知识库片段，回答依据有限”。Agent 里如果资料不足，也会通过 prompt 告诉模型参考有限。更进一步可以加相似度阈值和检索不足分支，让系统明确提示当前知识库没有足够依据。

### 10.17 RAG 会不会幻觉？

参考回答：

> 会。RAG 只能降低幻觉，不能完全消除幻觉。如果检索内容错了、不相关，模型仍可能生成错误回答。所以我做了来源追踪、质量过滤、rerank，以及回答约束。后续还可以加 reranker、引用一致性检查和人工评估集。

### 10.18 项目最大难点是什么？

参考回答：

> 最大难点不是单个 API 调用，而是让 RAG、历史案例和 Persona 画像稳定协同。检索结果会影响事实依据，案例会影响风格，画像会影响表达方式。如果哪一部分太强或太弱，最终回答都会偏。所以我把流程拆成节点，并保留中间状态，方便定位问题。

### 10.19 项目目前有什么不足？

参考回答：

> 目前主要还是本地 Demo，不是生产系统。不足包括：案例召回还是关键词匹配，评估集规模还小，没有完整日志和监控，没有用户权限系统，也没有正式部署。后续我会优先优化案例向量检索、扩大 eval、补 trace 日志和权限控制。

### 10.20 如果让你把它做成团队内部工具，你会怎么改？

参考回答：

> 我会补四类能力。第一是知识库管理，包括文档上传、重建索引、来源查看。第二是可观测性，记录 query、召回片段、耗时、模型输出和错误。第三是评估体系，把真实失败案例加入 eval。第四是权限和部署，避免私有资料泄露，并把前后端和向量库部署成更稳定的服务。

---

## 11. 容易说错的地方

不要说：

> 案例召回也是 Chroma 向量检索。

正确说法：

> 知识库资料使用向量检索，历史案例当前是关键词打分召回，后续可以升级成 embedding 检索。

不要说：

> 这是完全自主 Agent。

正确说法：

> 这是 workflow-based Agent，流程由 LangGraph 固定，模型在生成和检查节点中发挥作用。

不要说：

> 用了 RAG 就不会幻觉。

正确说法：

> RAG 可以降低幻觉，但不能消除幻觉，检索质量、上下文组织和校验都很关键。

不要说：

> 前端有真正的服务端任务队列。

正确说法：

> 前端用浏览器内存 task store 和 localStorage 管理运行状态和历史记录，不是服务端异步队列。

不要说：

> 项目已经生产可用。

正确说法：

> 当前是完整本地原型，核心链路已跑通，但生产化还需要权限、日志、监控、评估和部署。

---

## 12. 面试官追问连招

### 连招 1：项目真实性

问：这个项目是你自己完整做的吗？哪些部分是你亲自实现的？

答：

> 这是个人项目，我借助 Codex 和 Claude Code 这类 AI 编程工具辅助开发，但核心流程我自己理解和整合。主要包括 PDF/OCR 入库、chunk 质量过滤、向量索引、RAG 检索、LangGraph Agent 编排、Persona 画像配置、相似案例召回、FastAPI 接口和 Next.js Demo。AI 工具提高了实现效率，但状态设计、数据流、prompt 约束和调试逻辑都需要我自己理解，否则项目出了问题没法定位。

问：那你最核心的代码是哪一块？

答：

> 我认为最核心的是 `agent_graph.py` 和 `rag_chain.py`。`agent_graph.py` 负责把问题解析、知识检索、案例召回、Persona 加载、回答生成串成可调试流程；`rag_chain.py` 负责检索、rerank、来源格式化和知识库回答。一个管 Agent 状态流，一个管 RAG 证据流。

### 连招 2：Agent 和 RAG 关系

问：为什么需要 Agent？直接 RAG 不行吗？

答：

> 直接 RAG 解决的是资料依据问题，但我的场景还有 Persona 风格、历史案例、牌面约束和校验问题。Agent 的价值是把这些步骤拆成有状态工作流，而不是一次 prompt 解决所有事。

问：Agent 自主性在哪里？

答：

> 我没有把它设计成完全自主规划型 Agent，而是可控 workflow。模型的智能主要体现在生成回答、风格迁移和检查节点；流程本身由 LangGraph 固定，保证稳定和可解释。

### 连招 3：RAG 质量

问：你怎么保证检索质量？

答：

> 我从入库和查询两端处理。入库时做质量过滤，排除目录、版权页、参考文献等低价值内容，对弱信息片段降权。查询时先召回 top-k 的 4 倍候选，再用 retrieval_score 乘 retrieval_weight 做 rerank，并限制同页 chunk 数。

问：如果检索到错误资料怎么办？

答：

> 模型可能会被错误资料带偏，所以需要来源追踪和评估。当前系统会返回 source_file 和 page，方便人工检查。后续可以加相似度阈值、reranker、引用一致性检查和冲突来源提示。

### 连招 4：多角色

问：你的多角色是不是只是 prompt 换一句话？

答：

> 不是。角色画像是结构化 JSON，包括语气、回答结构、常用表达、推理风格和避免事项。生成时还会召回对应 reader 的历史案例，让风格不只是靠一句身份设定，而是结合配置和真实示例。

问：怎么验证角色真的不同？

答：

> 当前主要是人工对比同一问题在不同 reader 下的关注点、表达结构和语气差异。后续可以加 persona consistency eval，比如检查常用表达、结构匹配度、人工评分和 LLM-as-judge 辅助评估。

---

## 13. 完整追问题库

这一部分用于集中刷题。前面的章节偏“理解项目”，这里偏“面试官怎么问、我怎么答”。建议你先把每题的核心答法记住，再根据自己真实项目情况补数字和例子。

### 13.1 自我介绍与动机

#### 1. 请你做一个 1 分钟自我介绍

参考回答：

> 我是冯家声，本科是电子信息工程，目前在汕头大学读通信工程硕士。我主要关注 AI Agent 和大模型应用开发，最近做了一个基于 RAG 与 LangGraph 的多 Persona 问答 Agent 项目。
>
> 这个项目的核心是把领域 PDF 文献和历史问答案例构建成本地知识库，通过语义检索、案例召回、角色画像加载和多步骤 Agent 编排，让系统能够根据不同角色风格生成回答。我在里面主要负责文档入库、OCR/PDF 解析、向量检索、LangGraph 工作流设计，以及 Streamlit/FastAPI/Next.js Demo 搭建。
>
> 我希望找 AI Agent 方向实习，是因为我对大模型从“聊天工具”变成“可调用工具、可管理状态、可接入知识和流程的应用系统”这件事很感兴趣，也希望在真实业务场景里提升工程化能力。

#### 2. 为什么想做 AI Agent，而不是普通后端、算法或前端？

参考回答：

> 我对 Agent 感兴趣是因为它处在模型能力和业务流程之间。普通大模型应用更多是一次 prompt 输入输出，而 Agent 需要考虑任务拆解、状态管理、工具调用、检索增强、异常处理和结果校验，更像一个可以被工程化的智能流程系统。
>
> 我本身有通信和 Transformer 相关背景，对模型原理有一定理解，同时也做过 RAG、LangGraph、FastAPI、Next.js 这类应用链路，所以我希望从 AI Agent 实习切入，把模型能力和真实产品需求结合起来。

#### 3. 你的优势是什么？

参考回答：

> 我的优势主要有三点。第一，我对 AI Agent 方向有持续投入，不只是看概念，而是自己做了完整 Demo，从文档处理、向量库、Agent 编排到前后端交互都跑了一遍。第二，我能快速学习和使用 AI 编程工具，比如 Claude Code、Codex，把它们用于需求拆解、代码生成和调试。第三，我有工科和研究背景，硕士课题涉及 Transformer 和视觉任务，所以我不只是会调 API，也愿意理解模型和系统背后的机制。

#### 4. 你希望在实习中获得什么？

参考回答：

> 我希望参与真实 AI Agent 或大模型应用项目，学习团队如何做需求拆解、Agent 架构设计、RAG 评估、工具调用安全和工程化部署。我也希望自己能承担具体模块，比如知识库构建、Agent 节点开发、接口封装或评估工具开发。

### 13.2 项目真实性拷打

#### 5. 这个项目是你自己完整做的吗？哪些部分是你亲自实现的？

参考回答：

> 这是个人项目，我借助 Codex 和 Claude Code 这类 AI 编程工具辅助开发，但核心流程我自己理解和整合。主要包括 PDF/OCR 入库、chunk 质量过滤、向量索引、RAG 检索、LangGraph Agent 编排、Persona 画像配置、相似案例召回、FastAPI 接口和 Next.js Demo。AI 工具提高了实现效率，但状态设计、数据流、prompt 约束和调试逻辑都需要我自己理解，否则项目出了问题没法定位。

#### 6. 这个项目目前到底跑到什么程度？是 Demo 还是可上线系统？

参考回答：

> 目前是本地 Demo 和原型系统，还不是生产级系统。它已经跑通了从文档入库、向量检索、Agent 编排到前端交互展示的完整链路，可以用于验证多角色 RAG 问答的思路。
>
> 但如果要上线，还需要补充权限控制、日志监控、批量评估、异常处理、部署配置和数据管理后台。我不会把它包装成生产系统，它现在更像一个可验证技术方案的原型。

#### 7. 你项目里用了 AI 编程工具，那怎么证明你自己理解代码？

参考回答：

> 我确实会用 Claude Code、Codex 辅助开发，比如生成初版代码、定位报错、优化结构。但核心流程我会自己拆解和验证。比如 LangGraph 的 State 设计、每个节点读写哪些字段、RAG 入库 metadata 怎么保存、检索结果如何进入 prompt，这些我都需要自己理解，否则项目一出问题根本没法调试。AI 工具能提高效率，但不能替代我对架构和数据流的判断。

#### 8. 你项目里最核心的代码是哪一块？

参考回答：

> 我认为最核心的是 `agent_graph.py` 和 `rag_chain.py`。`agent_graph.py` 负责把问题解析、知识检索、案例召回、Persona 加载、回答生成串成可调试流程；`rag_chain.py` 负责检索、rerank、来源格式化和知识库回答。一个管 Agent 状态流，一个管 RAG 证据流。

#### 9. 这个项目最大的技术难点是什么？

参考回答：

> 最大的难点是让 RAG、案例召回和 Persona 画像稳定协同。单独做检索或单独写角色 prompt 都不难，难的是回答既要有事实依据，又要有角色差异，还要能调试每一步为什么这样回答。

#### 10. 你怎么定位回答质量问题？

参考回答：

> 我会按链路拆：先看用户问题解析是否正确，再看检索结果是否相关，再看相似案例是否匹配，再看角色配置是否太弱或太强，然后看 prompt 是否约束清楚，最后看模型是否没有遵循指令。检索错就优化切分、embedding、top-k、rerank；检索对但回答错，就优化 prompt、上下文组织和校验节点。

### 13.3 RAG 深度追问

#### 11. 你的 RAG 流程具体是什么？

参考回答：

> 我的流程是：先用 PyMuPDF 读取 PDF 文本，如果文本层质量不好，就用 RapidOCR 处理扫描件；然后对文本做清洗，按段落和句子边界切成 chunk；给每个 chunk 保存来源文件、页码、chunk_id、质量状态等 metadata；再用 BAAI/bge-m3 生成 embedding，写入 ChromaDB 和 NumPy fallback。查询时对用户 query 做 embedding，召回候选片段，rerank 后把上下文交给 LLM 生成回答。

#### 12. chunk size 你怎么设？为什么？

参考回答：

> 当前默认最大约 900 字符，不是简单硬切。优先按段落切，超长段落按句子边界切，短尾部会合并。这样是为了让 chunk 既有完整语义，又不会太长导致召回不精确。

#### 13. 你怎么判断 chunk 切得好不好？

参考回答：

> 我会用一批测试问题去看 top-k 召回结果。好的 chunk 应该满足三个条件：第一，召回片段和问题语义相关；第二，片段本身语义完整；第三，回答所需的信息尽量集中在少量 chunk 里。如果经常召回碎片化内容，说明 chunk 太小或 overlap 不够；如果经常召回很长但不精确的片段，说明 chunk 太大。

#### 14. 为什么要做 OCR？

参考回答：

> 因为有些 PDF 是扫描件，直接用 PyMuPDF 提取文字会得到空文本或乱码。如果某页提取文字少于阈值，并且开启 OCR，就用 RapidOCR 识别图片文本。OCR 结果会缓存起来，避免每次入库重复识别。

#### 15. metadata 具体存了什么？

参考回答：

> 每个 chunk 的 metadata 包括 chunk_id、source_file、page、chunk_index、language、content_type、extraction_method、quality_status、quality_reasons 和 retrieval_weight。source_file 和 page 用于来源展示，quality_status 和 retrieval_weight 用于 rerank，extraction_method 用于判断错误是否来自 OCR。

#### 16. 为什么不是所有 chunk 都入库？

参考回答：

> PDF 里有大量对问答没帮助的内容，比如目录、版权页、参考文献、标题页。它们会污染检索结果，所以我在入库阶段做质量过滤，`exclude` 不入库，`downrank` 降权保留。

#### 17. 为什么要先召回 top_k * 4？

参考回答：

> 因为原始向量相似度不一定等于最终可用性。有些片段相似度高但质量差，比如目录或列表。先多召回一些候选，再结合质量权重 rerank，可以提高最终 top-k 的质量。

#### 18. top-k 设置多少？太多太少有什么问题？

参考回答：

> 一般从 top-3 到 top-5 开始。top-k 太少可能漏掉关键资料，top-k 太多会引入噪声，也会让 prompt 变长，增加回答发散风险。更好的方式不是盲目增大 top-k，而是先召回更多候选，再用 rerank 选出高质量片段。

#### 19. 为什么用向量检索，不直接关键词搜索？

参考回答：

> 关键词搜索适合精确匹配，但用户提问和文档表达可能不是同一套词。向量检索能根据语义相似度召回内容，更适合自然语言问答。但我不认为向量检索一定完全替代关键词搜索，后续可以做 BM25 加向量检索的混合检索，再用 reranker 重排。

#### 20. ChromaDB 在项目里承担什么角色？

参考回答：

> ChromaDB 是本地持久化向量库，用来存储知识片段、metadata 和 embedding。用户查询时，它负责根据 query embedding 找到语义相近的文档片段。项目里还保留了 NumPy fallback，作为本地开发和恢复方案。

#### 21. 为什么还要 NumPy fallback？

参考回答：

> ChromaDB 是主要后端，但本地开发可能遇到依赖、版本或索引损坏问题。NumPy fallback 保存 `vectors.npy` 和 `documents.jsonl`，可以用归一化向量点积做最基本的相似度检索，保证 Demo 不会因为 Chroma 问题完全不可用。

#### 22. RAG 怎么做来源追踪？

参考回答：

> 入库时每个 chunk 都保存 source_file、page、chunk_id 等 metadata。检索结果返回时，不只返回文本，也返回 metadata。回答生成时把来源一起放进上下文，前端也展示来源文件和页码，方便用户核对原始资料。

#### 23. 如果检索不到相关内容怎么办？

参考回答：

> 知识库问答会返回“没有检索到知识库片段，回答依据有限”。更进一步可以设置相似度阈值，如果 top-k 分数低于阈值，就走“依据不足”的分支，而不是让模型强行回答。

#### 24. 如果检索出来的内容是错的，模型会不会也跟着错？

参考回答：

> 会，所以 RAG 的质量高度依赖检索质量。模型不是事实校验器，如果上下文给错了，它可能基于错误上下文生成看起来合理的答案。所以需要保留来源、设置质量过滤、做 rerank、必要时做引用一致性检查。

#### 25. RAG 会不会幻觉？

参考回答：

> 会。RAG 只能降低幻觉，不能完全消除幻觉。如果检索内容错了、不相关，模型仍可能生成错误回答。所以我做了来源追踪、质量过滤、rerank，以及回答约束。后续还可以加 reranker、引用一致性检查和人工评估集。

### 13.4 LangGraph / Agent 追问

#### 26. 为什么需要 LangGraph？普通函数串起来不行吗？

参考回答：

> 如果只是简单的“检索然后回答”，普通函数确实可以。但我的项目涉及多个步骤和共享状态，比如问题解析、知识检索、案例召回、角色加载、回答生成、校验。后面还可能出现条件分支，比如校验失败后重新生成。LangGraph 的价值是把流程显式建模成节点和边，每个节点读写 State，流程更清楚，也更方便调试和扩展。

#### 27. 你的 State 里有什么字段？

参考回答：

> State 里包括 reader_id、question、cards、query、knowledge_docs、similar_cases、persona、answer、check 和 steps。一开始只有用户输入，后面每个节点逐步补充字段。比如 parse 节点写 query，检索节点写 knowledge_docs，案例节点写 similar_cases，画像节点写 persona，生成节点写 answer。

#### 28. 你的 Agent 算真正的 Agent 吗？

参考回答：

> 严格说它更偏 workflow-based Agent，而不是完全开放式自主规划 Agent。流程由 LangGraph 固定，模型主要在生成和检查节点里发挥作用。这样牺牲了一部分自由度，但提高了可解释性、稳定性和可调试性，更适合业务 Demo。

#### 29. ReAct 在你的项目里怎么体现？

参考回答：

> 我的项目没有完全采用开放式 ReAct 循环，而是借鉴了 ReAct 的思想：模型不是一次性生成最终答案，而是在流程中结合中间观察结果，比如检索结果、案例结果和校验结果，再进行下一步生成。如果后续让 Agent 决定是否继续检索、是否重新生成，就会更接近 ReAct。

#### 30. Function Calling 和你的工具调用有什么关系？

参考回答：

> Function Calling 可以让模型以结构化参数调用工具，比如检索知识库、查询案例库、读取角色配置。我的项目目前更多是由 LangGraph 固定节点调用工具，而不是完全由模型自由选择工具。固定节点更可控，模型自主 function calling 更灵活。

#### 31. Agent 什么时候应该停止？怎么避免无限循环？

参考回答：

> 当前流程是线性的，所以不会无限循环。如果后续加入“校验失败后重新生成”这种循环，就必须设置最大重试次数。比如最多重新生成 2 次，超过后返回当前最佳答案和提示。每个条件分支都应该有明确退出条件。

#### 32. Agent 中每个节点的输入输出是什么？

参考回答：

> 初始 State 只有 reader_id、question、cards 和 steps。parse 节点读取 question/cards，写 query；知识检索节点读取 query，写 knowledge_docs；案例召回节点读取 reader_id/query，写 similar_cases；画像节点读取 reader_id，写 persona；生成节点读取 persona、question、cards、knowledge_docs 和 similar_cases，写 answer；可选校验节点读取 answer/persona/cards，写 check。

#### 33. 如果 LangGraph 出问题怎么办？

参考回答：

> 我做了 fallback。如果 LangGraph 导入、编译或执行失败，系统会降级成普通函数链，按同样顺序手动调用每个节点，并把异常信息写进 debug 的 `langgraph_fallback` 字段。这样 Demo 不会因为编排框架问题完全不可用。

### 13.5 多 Persona 和案例追问

#### 34. 你所谓多角色，是不是只是 prompt 里换一句“你是某某”？

参考回答：

> 不是。角色画像是结构化 JSON，包括语气、回答结构、常用表达、推理风格和避免事项。生成时还会召回对应 reader 的历史案例，让风格不只是靠一句身份设定，而是结合配置和真实示例。

#### 35. Persona 画像里有哪些字段？

参考回答：

> 主要有 reader_id、display_name、tone、answer_structure、common_phrases、reasoning_style 和 avoid。tone 控制语气，answer_structure 控制组织方式，common_phrases 帮助保持表达习惯，reasoning_style 描述判断方式，avoid 约束不要出现的风格或风险表达。

#### 36. 历史案例和知识库资料有什么区别？

参考回答：

> 知识库资料解决“依据是什么”，比如牌意、历史、象征学解释；历史案例解决“类似问题通常怎么回答”，尤其是某个占卜师的表达结构和判断习惯。知识库偏事实依据，案例偏风格和示例。

#### 37. 案例召回也是向量检索吗？

参考回答：

> 目前不是。知识库资料使用向量检索，历史案例召回为了简单稳定，采用的是关键词重合打分。它会把 query 里的词和案例的问题、背景、回答、牌名做匹配，取分数最高的几条。后续可以升级成案例 embedding 检索或混合检索。

#### 38. 怎么验证不同 Persona 真的有差异？

参考回答：

> 当前主要是人工对比同一问题在不同 reader 下的关注点、表达结构和语气差异。后续可以加 persona consistency eval，比如检查常用表达、结构匹配度、人工评分和 LLM-as-judge 辅助评估。

#### 39. 如果角色风格和事实依据冲突，你优先哪个？

参考回答：

> 优先事实依据。Persona 只能影响表达方式、关注重点和组织结构，不能改变资料和牌面事实。prompt 中也会要求必须使用用户本次提供的牌面，不能替换、增删或改写成其他牌。

#### 40. 怎么防止模型漏用用户给的牌？

参考回答：

> 生成节点里有一个简单的结构校验。回答生成后，会检查三张用户牌是否都出现在回答中。如果发现漏牌，会触发一次低温重试，并明确要求回答必须逐一使用这些牌，不能提及其他牌。

### 13.6 工程化与前后端追问

#### 41. FastAPI 在项目里起什么作用？

参考回答：

> FastAPI 是本地后端服务层，把 RAG 和 Agent 能力封装成接口。前端不直接操作向量库或 LangGraph，而是通过 API 提交问题、选择角色、获取回答结果。这样前后端解耦，也方便后续接入更多客户端。

#### 42. 主要 API 有哪些？

参考回答：

> 主要有 `GET /api/health` 检查配置和索引状态，`GET /api/cards` 返回牌表，`GET /api/readers` 返回可选 Persona，`POST /api/knowledge/query` 做知识库问答或资料检索，`POST /api/reading/generate` 触发 Persona Agent 解读。

#### 43. Streamlit 和 Next.js 为什么都用了？

参考回答：

> Streamlit 更适合内部后台和快速调试，比如资料入库、案例审核、画像编辑、状态检查。Next.js 更接近真实用户侧产品，用于知识库助手和占卜解读体验。两者面向的使用场景不同。

#### 44. 前端请求为什么走 Next.js 代理？

参考回答：

> 前端默认请求 Next.js 的 `/api/*`，再由代理转发到本地 FastAPI。这样 Cloudflare 临时分享时只暴露前端 3000 端口，不直接暴露 FastAPI 8787，安全边界更清楚。

#### 45. 前端有没有真正的后端任务队列？

参考回答：

> 当前没有。前端用浏览器内存 task store 和 localStorage 管理“正在生成/查询”的状态和历史记录。它能做到切换页面后回来还能看到结果，但不是服务端异步任务队列。生产化时可以改成真正的后端任务和 trace 系统。

#### 46. 如果回答速度太慢，你会怎么优化？

参考回答：

> 我会先定位瓶颈，看是检索、模型调用还是多角色生成。PDF/OCR 入库应该离线做，不在用户请求时做。在线阶段可以减少 top-k 和上下文长度、缓存高频查询、使用流式输出、并发生成多个角色回答、把校验节点做成可选，或者选择更快的模型。

#### 47. 如果向量库挂了或模型 API 失败怎么办？

参考回答：

> 向量库方面有 NumPy fallback；模型 API 方面应该设置超时、错误提示和有限重试。当前 FastAPI 会把常见错误包装成用户可读信息，比如索引未准备、API key 未配置、模型请求超时。生产化还需要 trace_id 和日志系统。

### 13.7 评估、安全和边界追问

#### 48. 有没有做量化评估？

参考回答：

> 目前有第一版离线 eval，但还不完善。RAG eval 主要检查是否返回文档、期望来源是否在 top-k、期望关键词是否出现在上下文或回答里。Agent eval 主要检查是否使用全部用户牌、是否出现额外牌、是否执行完整步骤。当前结构评估 RAG 5/5、Agent 3/3 通过。后续需要扩大评估集和引入人工评分。

#### 49. 你怎么评估 RAG 的召回效果？

参考回答：

> 可以从 retrieval 和 generation 两层评估。检索层看 top-k 是否命中人工标注的相关文档，指标可以用 Recall@k、MRR、Precision@k。生成层看答案是否基于召回内容、是否引用正确、是否回答问题，可以人工评分，也可以用 LLM-as-judge 辅助。

#### 50. 这个项目不评估“占卜准不准”吗？

参考回答：

> 第一版不评估“占卜准不准”，因为这很主观，也不适合做工程质量指标。当前 eval 更关注系统能力是否稳定：RAG 是否能找资料，回答是否有上下文支撑，Agent 是否执行完整步骤，是否漏用或乱加用户没有给的牌。

#### 51. Agent 工具调用有什么安全风险？

参考回答：

> 风险主要是模型可能调用不该调用的工具，或者传入危险参数。比如文件删除、数据库写入、网络请求、执行命令这类工具都需要严格限制。解决方式包括工具白名单、参数 schema 校验、权限控制、人工确认高风险操作和日志审计。

#### 52. 如果用户 prompt injection，让模型忽略系统指令怎么办？

参考回答：

> 需要把用户输入和系统指令隔离，并且不要让用户内容覆盖系统规则。RAG 场景里，检索到的文档也可能包含恶意指令，所以要明确告诉模型：检索内容只是资料，不是指令。高风险操作不能只靠 prompt 防护，应该在工具层做权限校验。

#### 53. RAG 会不会泄露知识库里的敏感内容？

参考回答：

> 会有这个风险。用户可能通过提问诱导系统返回不该看的资料。所以生产环境需要权限控制，检索时根据用户身份过滤可访问文档。metadata 里可以保存权限标签，查询时做 filter。回答生成前也可以做敏感信息检测。

#### 54. 如果让你把这个 Demo 做成团队内部工具，你会怎么改？

参考回答：

> 我会补四类能力。第一是知识库管理，包括文档上传、重建索引、来源查看。第二是可观测性，记录 query、召回片段、耗时、模型输出和错误。第三是评估体系，把真实失败案例加入 eval。第四是权限和部署，避免私有资料泄露，并把前后端和向量库部署成更稳定的服务。

#### 55. 项目目前最大的不足是什么？

参考回答：

> 目前主要还是本地 Demo，不是生产系统。不足包括：案例召回还是关键词匹配，评估集规模还小，没有完整日志和监控，没有用户权限系统，也没有正式部署。后续我会优先优化案例向量检索、扩大 eval、补 trace 日志和权限控制。

---

## 14. 最后背诵清单

最值得背的 10 句话：

1. 这个项目更偏 workflow-based Agent，不是完全开放式自主 Agent。
2. 核心不是让模型回答塔罗问题，而是把资料、案例、Persona 和流程状态组织起来。
3. RAG 入库阶段先做 PDF/OCR，再切 chunk，再质量过滤，再 embedding 入库。
4. 每个 chunk 都保存 source_file、page、quality_status、retrieval_weight 等 metadata。
5. 检索时不是直接取 top-k，而是先召回 top-k 的 4 倍候选，再 rerank。
6. Agent profile 会更优先 keep chunk，减少低质量资料干扰最终解读。
7. 历史案例当前是关键词打分召回，不是向量检索。
8. Persona 是结构化 JSON，不是一句“你是某某”。
9. 生成后会检查是否漏用了用户给的三张牌，漏牌会触发一次重试。
10. 当前项目是完整本地原型，不是生产系统，后续要补评估、日志、权限和部署。

---

## 15. 一句话总结

> 这个项目的核心不是“让模型看起来会占卜”，而是把领域资料、历史案例、角色画像和 LangGraph 状态流组织成一个可检索、可追踪、可调试、可扩展的 Agent 应用原型。
