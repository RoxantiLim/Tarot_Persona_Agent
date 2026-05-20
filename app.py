from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from src.tarot_agent.agent_graph import run_persona_reading
from src.tarot_agent.cards import MAJOR_ARCANA, MINOR_ARCANA, card_display_names, random_three_card_draw
from src.tarot_agent.config import AppConfig, dependency_report
from src.tarot_agent.persona import DEFAULT_PERSONAS, load_persona, save_default_personas, save_persona
from src.tarot_agent.rag_chain import answer_knowledge_query, retrieve_context
from src.tarot_agent.schemas import PersonaProfile
from src.tarot_agent.vector_store import index_exists


st.set_page_config(
    page_title="Tarot Knowledge Companion",
    page_icon="",
    layout="wide",
)


def init_state() -> None:
    st.session_state.setdefault("knowledge_history", [])
    st.session_state.setdefault("agent_history", [])
    st.session_state.setdefault("last_random_draw", [])


def sidebar(config: AppConfig) -> tuple[str, bool]:
    st.sidebar.title("Tarot Companion")
    page = st.sidebar.radio(
        "页面",
        ["知识库助手", "占卜 Agent", "数据与画像", "项目状态"],
        index=0,
    )
    dev_mode = st.sidebar.toggle("开发者视图", value=False)
    st.sidebar.caption(f"Embedding: {config.embedding_model}")
    st.sidebar.caption(f"LLM: {config.deepseek_model}")
    return page, dev_mode


def knowledge_page(config: AppConfig, dev_mode: bool) -> None:
    st.title("塔罗学习知识库助手")
    st.caption("用于牌意查询、主题学习和资料检索。结果会保留在本次会话历史中。")

    if not index_exists(config):
        st.warning("还没有检测到知识库索引。请先运行 `python scripts\\ingest_documents.py`。")

    mode_options = ["牌意查询", "主题学习", "资料检索"]
    if hasattr(st, "segmented_control"):
        mode = st.segmented_control("模式", mode_options, default="牌意查询")
    else:
        mode = st.radio("模式", mode_options, horizontal=True)

    topic = "通用"
    orientation = "不限定"
    card_name = ""

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
                entry = {
                    "time": now_text(),
                    "mode": mode,
                    "query": query,
                    "docs": docs,
                }
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
                entry = {
                    "time": now_text(),
                    "mode": mode,
                    "query": query,
                    "result": result,
                }
            st.session_state.knowledge_history.insert(0, entry)

    render_knowledge_history(dev_mode)


def render_knowledge_history(dev_mode: bool) -> None:
    st.divider()
    col_title, col_action = st.columns([1, 0.18])
    with col_title:
        st.subheader("本次会话结果")
    with col_action:
        if st.button("清空", key="clear_knowledge_history"):
            st.session_state.knowledge_history.clear()
            st.rerun()

    if not st.session_state.knowledge_history:
        st.info("还没有生成内容。")
        return

    for idx, entry in enumerate(st.session_state.knowledge_history):
        title = f"{entry['time']} | {entry['mode']} | {entry['query'][:40]}"
        with st.expander(title, expanded=idx == 0):
            if entry["mode"] == "资料检索":
                docs = entry["docs"]
                if not docs:
                    st.info("没有检索到结果。")
                for doc_idx, doc in enumerate(docs, start=1):
                    meta = doc.metadata
                    st.markdown(f"**{doc_idx}. {meta.get('source_file', 'unknown')} / 第 {meta.get('page', '?')} 页**")
                    st.write(doc.page_content)
            else:
                result = entry["result"]
                st.markdown(result.answer)
                if result.error:
                    st.warning(result.error)
                with st.expander("引用来源", expanded=True):
                    if not result.sources:
                        st.info("没有可展示的引用来源。")
                    for source in result.sources:
                        st.markdown(f"- {source}")
                if dev_mode:
                    with st.expander("开发者视图：检索片段"):
                        for doc_idx, doc in enumerate(result.context_docs, start=1):
                            st.markdown(f"**Chunk {doc_idx}: {doc.metadata}**")
                            st.write(doc.page_content)


def persona_page(config: AppConfig, dev_mode: bool) -> None:
    st.title("多风格塔罗占卜 Agent")
    st.caption("第一版支持无牌阵三张牌：系统随机抽牌，或用户自行提供牌面。结果会保留在本次会话历史中。")

    readers = ["tarotist_1", "tarotist_2"]
    col_left, col_right = st.columns([1, 1])
    with col_left:
        reader_id = st.selectbox("占卜师风格", readers)
        question = st.text_area("你的问题", placeholder="例如：我和前任还有机会复合吗？", height=130)
        draw_mode = st.radio("抽牌模式", ["系统随机抽三张牌", "我自行提供三张牌"], horizontal=True)
        compare = st.toggle("同题并排对比", value=False)
    with col_right:
        card_inputs = draw_controls(draw_mode)

    if st.button("生成解读", type="primary") and question.strip():
        if draw_mode == "系统随机抽三张牌":
            card_inputs = random_three_card_draw()
            st.session_state.last_random_draw = card_inputs
        entry_readers = ["tarotist_1", "tarotist_2"] if compare else [reader_id]
        with st.spinner("Agent 正在检索知识库、案例和风格画像..."):
            results = [
                {
                    "reader_id": rid,
                    "result": run_persona_reading(config, rid, question, card_inputs),
                }
                for rid in entry_readers
            ]
        st.session_state.agent_history.insert(
            0,
            {
                "time": now_text(),
                "question": question,
                "draw_mode": draw_mode,
                "cards": card_inputs,
                "results": results,
            },
        )

    render_agent_history(dev_mode)


def draw_controls(draw_mode: str) -> list[dict[str, str]]:
    if draw_mode == "系统随机抽三张牌":
        st.info("点击“生成解读”后，系统会从 78 张牌中不放回随机抽取 3 张，并为每张牌随机正位/逆位。")
        if st.session_state.last_random_draw:
            st.markdown("上一次随机抽牌：")
            st.write(cards_to_text(st.session_state.last_random_draw))
        return []

    cards = card_display_names()
    card_1 = st.selectbox("第一张牌", cards, index=0)
    card_2 = st.selectbox("第二张牌", cards, index=1)
    card_3 = st.selectbox("第三张牌", cards, index=2)
    orientations = st.columns(3)
    with orientations[0]:
        o1 = st.selectbox("第一张方向", ["正位", "逆位"], key="o1")
    with orientations[1]:
        o2 = st.selectbox("第二张方向", ["正位", "逆位"], key="o2")
    with orientations[2]:
        o3 = st.selectbox("第三张方向", ["正位", "逆位"], key="o3")
    return [
        {"name": card_1, "orientation": o1},
        {"name": card_2, "orientation": o2},
        {"name": card_3, "orientation": o3},
    ]


def render_agent_history(dev_mode: bool) -> None:
    st.divider()
    col_title, col_action = st.columns([1, 0.18])
    with col_title:
        st.subheader("本次会话占卜记录")
    with col_action:
        if st.button("清空", key="clear_agent_history"):
            st.session_state.agent_history.clear()
            st.rerun()

    if not st.session_state.agent_history:
        st.info("还没有生成占卜回答。")
        return

    for idx, entry in enumerate(st.session_state.agent_history):
        with st.expander(f"{entry['time']} | {entry['draw_mode']} | {entry['question'][:40]}", expanded=idx == 0):
            st.markdown("**问题**")
            st.write(entry["question"])
            st.markdown("**本次无牌阵三张牌**")
            st.write(cards_to_text(entry["cards"]))
            if len(entry["results"]) == 2:
                cols = st.columns(2)
                for col, item in zip(cols, entry["results"]):
                    with col:
                        st.subheader(item["reader_id"])
                        st.markdown(item["result"].answer)
                        if dev_mode:
                            show_agent_debug(item["result"])
            else:
                item = entry["results"][0]
                st.subheader(item["reader_id"])
                st.markdown(item["result"].answer)
                if dev_mode:
                    show_agent_debug(item["result"])


def show_agent_debug(result) -> None:
    with st.expander("开发者视图：LangGraph / Agent 状态"):
        st.json(result.debug)
    with st.expander("知识库片段"):
        for doc in result.knowledge_docs:
            st.markdown(f"**{doc.metadata}**")
            st.write(doc.page_content)
    with st.expander("相似案例"):
        if not result.similar_cases:
            st.info("当前没有已审核案例可检索。")
        for case in result.similar_cases:
            st.json(case)


def data_page(config: AppConfig) -> None:
    st.title("数据与画像")
    tabs = st.tabs(["文档入库", "占卜案例", "风格画像"])
    with tabs[0]:
        render_ingest_report(config)
    with tabs[1]:
        render_case_status(config)
    with tabs[2]:
        render_persona_editor(config)


def render_ingest_report(config: AppConfig) -> None:
    report_path = config.reports_dir / "ingest_report.json"
    st.subheader("Doc 入库状态")
    if not report_path.exists():
        st.warning("还没有入库报告。请先运行 `python scripts\\ingest_documents.py`。")
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))
    st.metric("已入库 chunks", report.get("total_chunks", 0))
    rows = []
    for item in report.get("files", []):
        needs_ocr_pages = item.get("needs_ocr_pages", [])
        rows.append(
            {
                "文件": item.get("file", ""),
                "已提取页数": item.get("text_pages", 0),
                "chunks": item.get("chunks", 0),
                "需 OCR 页数": len(needs_ocr_pages),
                "状态": "已入库" if item.get("chunks", 0) else "未入库/需 OCR",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)
    with st.expander("需要 OCR 的页码明细"):
        st.json(report.get("needs_ocr", {}))
    st.caption("说明：第一版只入库可直接提取文字的 PDF 页面；扫描页会列在 needs_ocr 中。")


def render_case_status(config: AppConfig) -> None:
    st.subheader("占卜案例状态")
    reader_dirs = sorted([p for p in config.project_root.glob("Tarotist-*") if p.is_dir()])
    raw_rows = []
    for reader_dir in reader_dirs:
        image_count = len(list(reader_dir.glob("*.jpg"))) + len(list(reader_dir.glob("*.png")))
        raw_rows.append({"原始目录": reader_dir.name, "截图数量": image_count})
    st.markdown("**原始截图目录**")
    st.dataframe(raw_rows, hide_index=True, use_container_width=True)

    case_rows = []
    for path in sorted(config.cases_dir.glob("*.jsonl")):
        case_rows.append({"文件": path.name, "行数": count_jsonl_lines(path), "大小": path.stat().st_size})
    st.markdown("**结构化案例文件**")
    if case_rows:
        st.dataframe(case_rows, hide_index=True, use_container_width=True)
    else:
        st.info("当前还没有结构化案例文件。也就是说：截图还没有真正录入案例库。")

    st.markdown(
        """
后续流程：
1. 配置 `VISION_API_KEY`、`VISION_BASE_URL`、`VISION_MODEL`。
2. 运行 `python scripts\\extract_cases.py tarotist_1` 生成候选案例。
3. 人工审核候选案例，把高质量样本保存为 `data/cases/tarotist_1_reviewed.jsonl`。
"""
    )


def render_persona_editor(config: AppConfig) -> None:
    st.subheader("占卜师风格画像")
    reader_id = st.selectbox("选择占卜师", ["tarotist_1", "tarotist_2"], key="persona_reader")

    col1, col2 = st.columns([0.25, 0.75])
    with col1:
        if st.button("重置为默认画像"):
            save_default_personas(config, overwrite=True)
            st.success("已重置默认画像。")
            st.rerun()

    profile = load_persona(config, reader_id)
    raw = json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)
    edited = st.text_area("JSON 画像，可人工审核修改", value=raw, height=420)
    if st.button("保存画像", type="primary"):
        try:
            parsed = PersonaProfile.model_validate_json(edited)
            save_persona(config, parsed)
            st.success(f"已保存 {parsed.reader_id} 的风格画像。")
        except Exception as exc:
            st.error(f"JSON 不合法或字段不完整：{exc}")


def status_page(config: AppConfig) -> None:
    st.title("项目状态")
    st.subheader("依赖检查")
    report = dependency_report()
    st.dataframe(
        [{"package": name, "installed": installed} for name, installed in report.items()],
        hide_index=True,
        use_container_width=True,
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
    st.write(f"大阿卡纳：{len(MAJOR_ARCANA)} 张，小阿卡纳：{len(MINOR_ARCANA)} 张，总计：{len(card_display_names())} 张")
    st.subheader("会话内存")
    st.write(
        {
            "knowledge_history_count": len(st.session_state.knowledge_history),
            "agent_history_count": len(st.session_state.agent_history),
        }
    )


def cards_to_text(cards: list[dict[str, str]]) -> str:
    return "；".join(f"{card['name']}（{card['orientation']}）" for card in cards)


def count_jsonl_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def now_text() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main() -> None:
    init_state()
    config = AppConfig.load()
    page, dev_mode = sidebar(config)
    if page == "知识库助手":
        knowledge_page(config, dev_mode)
    elif page == "占卜 Agent":
        persona_page(config, dev_mode)
    elif page == "数据与画像":
        data_page(config)
    else:
        status_page(config)


if __name__ == "__main__":
    main()
