from __future__ import annotations

import streamlit as st

from src.tarot_agent.agent_graph import run_persona_reading
from src.tarot_agent.cards import MAJOR_ARCANA, MINOR_ARCANA, card_display_names
from src.tarot_agent.config import AppConfig, dependency_report
from src.tarot_agent.rag_chain import answer_knowledge_query, retrieve_context
from src.tarot_agent.vector_store import index_exists


st.set_page_config(
    page_title="Tarot Knowledge Companion",
    page_icon="",
    layout="wide",
)


def sidebar(config: AppConfig) -> tuple[str, bool]:
    st.sidebar.title("Tarot Companion")
    page = st.sidebar.radio(
        "页面",
        ["知识库助手", "占卜 Agent", "项目状态"],
        index=0,
    )
    dev_mode = st.sidebar.toggle("开发者视图", value=False)
    st.sidebar.caption(f"Embedding: {config.embedding_model}")
    st.sidebar.caption(f"LLM: {config.deepseek_model}")
    return page, dev_mode


def knowledge_page(config: AppConfig, dev_mode: bool) -> None:
    st.title("塔罗学习知识库助手")
    st.caption("用于牌意查询、主题学习和资料检索。第一版以资料整理和引用为主。")

    if not index_exists(config):
        st.warning("还没有检测到 ChromaDB 知识库。请先运行 `python scripts\\ingest_documents.py`。")

    mode_options = ["牌意查询", "主题学习", "资料检索"]
    if hasattr(st, "segmented_control"):
        mode = st.segmented_control("模式", mode_options, default="牌意查询")
    else:
        mode = st.radio("模式", mode_options, horizontal=True)

    topic = "通用"
    orientation = "不限定"
    card_name = ""
    free_text = ""

    if mode == "牌意查询":
        col1, col2, col3 = st.columns([1.2, 1, 1])
        with col1:
            card_name = st.selectbox("牌名", card_display_names(), index=0)
        with col2:
            orientation = st.selectbox("正逆位", ["不限定", "正位", "逆位"])
        with col3:
            topic = st.selectbox("主题", ["通用", "感情", "事业", "学习", "人际", "灵性成长"])
        free_text = st.text_area("补充问题", placeholder="例如：圣杯二逆位在感情复合里怎么理解？")
        query = " ".join(part for part in [card_name, orientation, topic, free_text] if part)
    elif mode == "主题学习":
        query = st.text_area(
            "学习主题",
            placeholder="例如：死亡牌的转化象征；宝剑牌组和理性冲突的关系",
            height=110,
        )
    else:
        query = st.text_input("检索关键词", placeholder="例如：恋人逆位 感情")

    top_k = st.slider("召回片段数", min_value=2, max_value=10, value=5)

    if st.button("开始", type="primary") and query.strip():
        with st.spinner("检索和整理中..."):
            if mode == "资料检索":
                docs = retrieve_context(config, query, top_k=top_k)
                st.subheader("检索结果")
                if not docs:
                    st.info("没有检索到结果。请确认已经构建知识库。")
                for idx, doc in enumerate(docs, start=1):
                    meta = doc.metadata
                    st.markdown(
                        f"**{idx}. {meta.get('source_file', 'unknown')} / 第 {meta.get('page', '?')} 页**"
                    )
                    st.write(doc.page_content)
            else:
                result = answer_knowledge_query(
                    config=config,
                    mode=mode,
                    query=query,
                    card_name=card_name,
                    orientation=orientation,
                    topic=topic,
                    top_k=top_k,
                )
                st.markdown(result.answer)
                if result.error:
                    st.warning(result.error)
                with st.expander("引用来源", expanded=True):
                    if not result.sources:
                        st.info("没有可展示的引用来源。")
                    for source in result.sources:
                        st.markdown(f"- {source}")
                if dev_mode:
                    with st.expander("开发者视图：检索片段", expanded=True):
                        for idx, doc in enumerate(result.context_docs, start=1):
                            st.markdown(f"**Chunk {idx}: {doc.metadata}**")
                            st.write(doc.page_content)


def persona_page(config: AppConfig, dev_mode: bool) -> None:
    st.title("多风格塔罗占卜 Agent")
    st.caption("第一版支持问题 + 三张牌，无牌阵解读。普通视图隐藏技术依据。")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        readers = ["tarotist_1", "tarotist_2"]
        reader_id = st.selectbox("占卜师风格", readers)
        question = st.text_area("你的问题", placeholder="例如：我和前任还有机会复合吗？", height=130)
    with col_right:
        cards = card_display_names()
        card_1 = st.selectbox("第一张牌", cards, index=0)
        card_2 = st.selectbox("第二张牌", cards, index=1)
        card_3 = st.selectbox("第三张牌", cards, index=2)
        orientations = st.columns(3)
        with orientations[0]:
            o1 = st.selectbox("第一张方向", ["正位", "逆位", "不确定"], key="o1")
        with orientations[1]:
            o2 = st.selectbox("第二张方向", ["正位", "逆位", "不确定"], key="o2")
        with orientations[2]:
            o3 = st.selectbox("第三张方向", ["正位", "逆位", "不确定"], key="o3")

    compare = st.toggle("同题并排对比", value=False)
    if st.button("生成解读", type="primary") and question.strip():
        card_inputs = [
            {"name": card_1, "orientation": o1},
            {"name": card_2, "orientation": o2},
            {"name": card_3, "orientation": o3},
        ]
        with st.spinner("Agent 正在检索知识库、案例和风格画像..."):
            if compare:
                cols = st.columns(2)
                for col, rid in zip(cols, ["tarotist_1", "tarotist_2"]):
                    result = run_persona_reading(config, rid, question, card_inputs)
                    with col:
                        st.subheader(rid)
                        st.markdown(result.answer)
                        if dev_mode:
                            show_agent_debug(result)
            else:
                result = run_persona_reading(config, reader_id, question, card_inputs)
                st.markdown(result.answer)
                if dev_mode:
                    show_agent_debug(result)


def show_agent_debug(result) -> None:
    with st.expander("开发者视图：LangGraph / Agent 状态", expanded=True):
        st.json(result.debug)
    with st.expander("知识库片段"):
        for doc in result.knowledge_docs:
            st.markdown(f"**{doc.metadata}**")
            st.write(doc.page_content)
    with st.expander("相似案例"):
        for case in result.similar_cases:
            st.json(case)


def status_page(config: AppConfig) -> None:
    st.title("项目状态")
    st.subheader("依赖检查")
    report = dependency_report()
    st.dataframe(
        [{"package": name, "installed": installed} for name, installed in report.items()],
        hide_index=True,
    )
    st.subheader("路径")
    st.write(
        {
            "project_root": str(config.project_root),
            "doc_dir": str(config.doc_dir),
            "chroma_dir": str(config.chroma_dir),
            "cases_dir": str(config.cases_dir),
            "model_cache_dir": str(config.model_cache_dir),
        }
    )
    st.subheader("牌表")
    st.write(f"大阿卡纳：{len(MAJOR_ARCANA)} 张，小阿卡纳：{len(MINOR_ARCANA)} 张")


def main() -> None:
    config = AppConfig.load()
    page, dev_mode = sidebar(config)
    if page == "知识库助手":
        knowledge_page(config, dev_mode)
    elif page == "占卜 Agent":
        persona_page(config, dev_mode)
    else:
        status_page(config)


if __name__ == "__main__":
    main()
