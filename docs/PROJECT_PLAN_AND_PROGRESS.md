# Tarot Knowledge Companion + Tarot Persona Agent

更新时间：2026-05-22

## 项目定位

这个仓库是一个分阶段完成的塔罗学习与占卜 Agent 项目，目标有两个：

1. 做一个真正可用的个人塔罗知识库助手，用来查阅、学习、复盘资料。
2. 在知识库基础上，结合真实占卜案例，做出多位不同风格的塔罗占卜 Agent，用于实习项目展示。

项目运行形态是一个本地 Streamlit Web 应用，侧边栏切换不同页面。普通视图偏朋友试用，开发者视图展示检索、案例、LangGraph 节点和自检信息。

## 总体方案

### 项目一：塔罗学习知识库助手

目标：把 `Doc/` 下的塔罗 PDF 做成本地 RAG 知识库。

技术路线：

- 文档解析：PyMuPDF 读取 PDF 文本页。
- 扫描页处理：第一版不做 OCR，标记为 `needs_ocr` 并跳过。
- 切块方式：按页内段落切 chunk，保留来源文件、页码、语言、内容类型、chunk id。
- Embedding：本地 `BAAI/bge-m3`。
- 向量检索：当前默认使用本地 numpy 向量索引，ChromaDB 保留为可选。
- 生成模型：DeepSeek OpenAI-compatible API。
- 应用界面：Streamlit。

功能模式：

- 牌意查询：选择 78 张牌、正逆位、主题，结合资料解释。
- 主题学习：围绕历史、象征学、牌组、体系生成学习笔记。
- 资料检索：直接返回原文片段、来源文件和页码。

回答结构：

- 核心理解
- 不同资料观点
- 结合主题解释
- 学习笔记
- 引用来源

### 项目二：多风格塔罗占卜 Agent

目标：复用项目一知识库，再引入真实贴吧占卜案例，构建不同占卜师风格的 Agent。

技术路线：

- 案例来源：`Tarotist-1/` 等截图目录。
- 案例抽取：第一版采用“本地 OCR + DeepSeek 文本结构化”。
- 入库规则：只自动入库“问题 + 占卜师文字写出的牌面 + 回答”完整的案例。
- 不入库内容：随机数不入库；用户上传牌图但文字没有牌名的案例进入人工标注池。
- 脱敏：自动处理手机号、邮箱、微信/QQ 等明显隐私。
- Persona：每位占卜师维护一个 `persona_profile`，包含语气、回答结构、判断习惯、常用表达、避免事项。
- Agent 编排：LangGraph 六节点流程。

LangGraph 第一版节点：

1. 解析用户问题和三张牌。
2. 检索塔罗知识库。
3. 检索该占卜师相似案例。
4. 加载 persona profile。
5. 生成占卜回答。
6. 检查风格和依据。

占卜输入模式：

- 系统随机抽牌：用户只输入问题，系统从 78 张牌中随机抽 3 张，并随机正逆位。
- 用户自行提供牌：用户输入问题，并选择 3 张牌及正逆位。

展示功能：

- 单占卜师回答。
- 同题并排对比。
- 普通视图隐藏技术细节。
- 开发者视图展示知识库片段、相似案例、LangGraph 节点和自检结果。

## 当前进度

### 已完成

- 已创建单仓库 Streamlit 多页面应用。
- 已接入 DeepSeek OpenAI-compatible API 配置。
- 已接入本地 `BAAI/bge-m3` embedding。
- 已构建知识库检索链路。
- 已完成知识库助手三个模式：
  - 牌意查询
  - 主题学习
  - 资料检索
- 已加入会话记忆，生成内容不会因下一次操作立刻消失。
- 已加入占卜 Agent 两种抽牌模式：
  - 系统随机三张牌
  - 用户指定三张牌
- 已加入占卜师画像编辑页面。
- 已加入数据状态页面，可查看文档入库、案例文件、画像 JSON。
- 已将项目上传到 GitHub public 仓库。

### 知识库状态

当前已入库 chunk：916。

已处理资料：

- `the-tarot-history-symbolism-and-divination...pdf`：361 chunks，12 页需要 OCR。
- `其实你已经很塔罗了（图文版）.pdf`：273 chunks。
- `塔罗的藏宝.pdf`：188 chunks。
- `塔罗逆位精解.pdf`：94 chunks，1 页需要 OCR。

暂未入库的扫描书：

- `《经典塔罗攻略秘籍》1.pdf`：0 chunks，89 页需要 OCR。
- `《经典塔罗攻略秘籍》2.pdf`：0 chunks，99 页需要 OCR。
- `《经典塔罗攻略秘籍》3.pdf`：0 chunks，120 页需要 OCR。

说明：第一版按计划只处理可直接提取文字的 PDF。扫描 PDF OCR 是后续增强项。

### 占卜案例状态

`Tarotist-1/` 原始截图：115 张。

已经完成：

- 115 张截图全部跑完 OCR + 结构化抽取。
- 候选文件：`data/cases/tarotist_1_candidates.jsonl`
- 候选案例总数：227 条。
- 已自动入库完整案例：163 条。
- 已入库文件：`data/cases/tarotist_1_reviewed.jsonl`
- 需要人工处理候选：70 条。
- 待处理文件：`data/cases/tarotist_1_needs_review.jsonl`
- 其中需要人工牌图标注：6 条。
- 完全没抽出案例的截图：4 张。
- 当前没有剩余 API 错误。

技术说明：

- `deepseek-v4-pro` 当前接口不接受 OpenAI 格式 `image_url` 图片输入。
- 因此已改为“本地 RapidOCR 识别截图文字 + DeepSeek 文本模型结构化案例”。
- 案例抽取模型单独配置为 `CASE_EXTRACT_MODEL`，默认 `deepseek-chat`，速度明显更快。

## 当前文件入口

- 应用入口：`app.py`
- 启动脚本：`scripts/start_app.ps1`
- 停止脚本：`scripts/stop_app.ps1`
- 文档入库脚本：`scripts/ingest_documents.py`
- 截图案例抽取脚本：`scripts/extract_cases.py`
- 候选案例晋级脚本：`scripts/promote_case_candidates.py`
- 配置模板：`.env.example`
- 占卜师画像：`data/personas/`
- 案例库：`data/cases/`
- OCR 文本缓存：`data/processed/ocr/`

## 下一步计划

### 第一优先级：把案例质量变成可控资产

1. 在应用的“数据与画像 -> 占卜案例”页面抽查 `tarotist_1_reviewed.jsonl`。
2. 人工查看 `tarotist_1_needs_review.jsonl`：
   - 能补牌名的补牌名。
   - OCR 明显错乱的删除或修正。
   - 不完整案例保留为待处理，不进入 reviewed。
3. 从 163 条 reviewed 中选出 50-100 条高质量样本，作为第一版风格学习主样本。
4. 基于高质量样本更新 `tarotist_1` 的 persona profile。

### 第二优先级：让 Agent 回答更像“项目展示”

1. 调整 Agent prompt，减少生硬模板感。
2. 增强“同题并排对比”页面，让不同占卜师差异更容易展示。
3. 开发者视图中展示：
   - 检索到的知识库片段
   - 命中的相似案例
   - persona profile 摘要
   - LangGraph 节点执行结果
4. 增加“回答保存/复制/历史记录导出”能力。

### 第三优先级：补齐第二位占卜师

1. 放入 `Tarotist-2/` 原始截图。
2. 运行案例抽取：
   - `python scripts\extract_cases.py tarotist_2 0 5`
   - `python scripts\promote_case_candidates.py tarotist_2`
3. 人工筛选第二位占卜师高质量案例。
4. 生成并人工修改 `tarotist_2` persona profile。
5. 做同题对比展示。

### 第四优先级：知识库增强

1. 对扫描 PDF 做 OCR。
2. 把 `《经典塔罗攻略秘籍》1/2/3.pdf` 入库。
3. 优化 chunk 标签：
   - 牌意
   - 逆位
   - 历史
   - 象征
   - 牌阵
   - 案例/解读
4. 增加文档管理页面，显示哪些页已入库、哪些页需要 OCR。

### 第五优先级：简历与面试展示包装

1. 更新 README，写清楚项目亮点、架构图、运行方式。
2. 准备一组固定 demo：
   - 知识库资料检索 demo
   - 牌意查询 demo
   - 同题双占卜师对比 demo
   - 开发者视图 demo
3. 准备面试讲法：
   - 为什么用 RAG
   - 为什么不用微调
   - 为什么用 LangGraph
   - 如何处理 OCR、脱敏、案例质量
   - 如何评估 Agent 输出是否可信

## 暂时不做

- 不做商业发布。
- 不做模型微调。
- 不做自动识别用户上传牌图。
- 不做复杂多牌阵系统。
- 不把版权资料、原始截图、API key 上传到 GitHub。

