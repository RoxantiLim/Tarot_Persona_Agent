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
        image_count = sum(
            1
            for path in reader_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
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

    if not config.vision_api_key or not config.vision_base_url or not config.vision_model:
        st.warning("还没有配置视觉模型。截图案例抽取需要在 `.env` 中填写 `VISION_API_KEY`、`VISION_BASE_URL`、`VISION_MODEL`。")
    else:
        st.success("视觉模型配置已检测到，可以运行截图抽取脚本。")

    st.markdown(
        """
后续流程：
1. 配置 `VISION_API_KEY`、`VISION_BASE_URL`、`VISION_MODEL`。
2. 先试跑 `python scripts\\extract_cases.py tarotist_1 5 5`，确认抽取质量。
3. 全量运行 `python scripts\\extract_cases.py tarotist_1 0 5` 生成候选案例。
4. 运行 `python scripts\\promote_case_candidates.py tarotist_1`，把完整候选自动写入 `tarotist_1_reviewed.jsonl`，待人工处理的写入 `tarotist_1_needs_review.jsonl`。
"""
    )

    preview_options = ["不预览"] + [path.name for path in sorted(config.cases_dir.glob("*.jsonl"))]
    preview_file = st.selectbox("预览案例文件", preview_options)
    if preview_file != "不预览":
        rows = load_jsonl_preview(config.cases_dir / preview_file, limit=5)
        st.json(rows, expanded=False)


    render_case_review_workspace(config)


def render_case_review_workspace(config: AppConfig) -> None:
    st.divider()
    st.subheader("人工审核工作台")
    st.caption("从 needs_review 中挑选可用案例，修正后加入 reviewed。Agent 只检索 reviewed 文件。")

    reader_id = st.selectbox("审核占卜师", ["tarotist_1", "tarotist_2"], key="review_reader_id")
    needs_path = config.cases_dir / f"{reader_id}_needs_review.jsonl"
    reviewed_path = config.cases_dir / f"{reader_id}_reviewed.jsonl"

    needs_rows = load_jsonl_rows(needs_path)
    reviewed_count = count_jsonl_lines(reviewed_path) if reviewed_path.exists() else 0
    col_a, col_b = st.columns(2)
    col_a.metric("待审核", len(needs_rows))
    col_b.metric("已入库 reviewed", reviewed_count)

    undo_key = f"last_removed_review_{reader_id}"
    if undo_key in st.session_state:
        removed = st.session_state[undo_key]
        undo_label = case_option_label(removed.get("index", 0), removed["row"])
        col_undo, col_hint = st.columns([0.28, 0.72])
        with col_undo:
            if st.button("撤回上一个移除", key=f"undo_remove_{reader_id}"):
                restore_index = min(removed.get("index", len(needs_rows)), len(needs_rows))
                needs_rows.insert(restore_index, removed["row"])
                write_jsonl_rows(needs_path, needs_rows)
                queue_review_index(reader_id, restore_index, len(needs_rows))
                del st.session_state[undo_key]
                st.success("已撤回上一个移除。")
                st.rerun()
        with col_hint:
            st.caption(f"可撤回：{undo_label}")

    if not needs_rows:
        st.info(f"没有找到待审核案例：{needs_path}")
        return

    options = list(range(len(needs_rows)))
    select_key = f"review_index_{reader_id}"
    pending_index_key = f"review_pending_index_{reader_id}"
    if pending_index_key in st.session_state:
        st.session_state[select_key] = min(st.session_state[pending_index_key], len(needs_rows) - 1)
        del st.session_state[pending_index_key]

    selected_index = st.selectbox(
        "选择待审核条目",
        options,
        format_func=lambda idx: case_option_label(idx, needs_rows[idx]),
        key=select_key,
    )
    row = needs_rows[selected_index]

    left, right = st.columns([0.9, 1.1])
    with left:
        st.markdown("**原始信息**")
        source_image = first_source_image(row)
        if source_image:
            st.caption(source_image)
            image_path = Path(source_image)
            if image_path.exists():
                st.image(str(image_path), use_container_width=True)
            else:
                st.warning("本地截图路径不存在，可能移动过文件。")
        st.json(row, expanded=False)

    with right:
        st.markdown("**编辑为完整案例**")
        default_cards = case_cards_to_text(row.get("cards", []))
        with st.form(f"review_form_{reader_id}_{selected_index}"):
            question = st.text_area("问题", value=str(row.get("question", "")), height=90)
            background = st.text_area("背景", value=str(row.get("background", "")), height=70)
            spread = st.text_input("牌阵", value=str(row.get("spread", "无牌阵三张牌") or "无牌阵三张牌"))
            cards_text = st.text_area(
                "牌面（一行一张：牌名 | 正位/逆位）",
                value=default_cards,
                height=110,
                placeholder="星币一 | 逆位\n恶魔 | 逆位\n星币四 | 逆位",
            )
            reader_answer = st.text_area("占卜师回答", value=str(row.get("reader_answer", "")), height=180)
            followups_text = st.text_area(
                "追问/反馈（可选，一行一条：speaker | text）",
                value=case_followups_to_text(row.get("followups", [])),
                height=90,
            )
            notes = st.text_input("备注", value=str(row.get("notes", row.get("reason", "")) or ""))
            remove_after_approve = st.checkbox("通过后从待审核池移除", value=True)

            save_pending = st.form_submit_button("保存修改到待审核")
            approve = st.form_submit_button("通过审核并加入 reviewed", type="primary")
            discard = st.form_submit_button("从待审核池移除")

        edited_case, validation_errors = build_reviewed_case(
            original=row,
            reader_id=reader_id,
            reviewed_path=reviewed_path,
            question=question,
            background=background,
            spread=spread,
            cards_text=cards_text,
            reader_answer=reader_answer,
            followups_text=followups_text,
            notes=notes,
        )

        with st.expander("预览将保存的 JSON", expanded=False):
            st.json(edited_case, expanded=False)

        if save_pending:
            needs_rows[selected_index] = edited_case | {"quality": "needs_review"}
            write_jsonl_rows(needs_path, needs_rows)
            queue_review_index(reader_id, selected_index + 1, len(needs_rows))
            st.success("已保存到待审核文件。")
            st.rerun()

        if approve:
            if validation_errors:
                st.error("；".join(validation_errors))
            else:
                append_jsonl_row(reviewed_path, edited_case)
                if remove_after_approve:
                    del needs_rows[selected_index]
                    write_jsonl_rows(needs_path, needs_rows)
                    queue_review_index(reader_id, selected_index, len(needs_rows))
                else:
                    queue_review_index(reader_id, selected_index + 1, len(needs_rows))
                st.success(f"已加入 reviewed：{edited_case['case_id']}")
                st.rerun()

        if discard:
            st.session_state[undo_key] = {"row": row, "index": selected_index}
            del needs_rows[selected_index]
            write_jsonl_rows(needs_path, needs_rows)
            queue_review_index(reader_id, selected_index, len(needs_rows))
            st.success("已从待审核池移除，可用上方按钮撤回。")
            st.rerun()


def queue_review_index(reader_id: str, requested_index: int, total_rows: int) -> None:
    if total_rows <= 0:
        st.session_state[f"review_pending_index_{reader_id}"] = 0
        return
    st.session_state[f"review_pending_index_{reader_id}"] = max(0, min(requested_index, total_rows - 1))


def case_option_label(index: int, row: dict[str, Any]) -> str:
    image_name = Path(first_source_image(row)).name if first_source_image(row) else "unknown"
    quality = row.get("quality", row.get("status", "needs_review"))
    question = str(row.get("question", row.get("reason", ""))).replace("\n", " ")
    return f"{index + 1}. {image_name} | {quality} | {question[:36]}"


def first_source_image(row: dict[str, Any]) -> str:
    if row.get("source_images"):
        return str(row["source_images"][0])
    if row.get("source_image"):
        return str(row["source_image"])
    return ""


def case_cards_to_text(cards: list[dict[str, Any]]) -> str:
    lines = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        name = str(card.get("name", "")).strip()
        orientation = str(card.get("orientation", "")).strip()
        if name or orientation:
            lines.append(f"{name} | {orientation}")
    return "\n".join(lines)


def case_followups_to_text(followups: list[dict[str, Any]]) -> str:
    lines = []
    for item in followups or []:
        if not isinstance(item, dict):
            continue
        speaker = str(item.get("speaker", "unknown")).strip()
        text = str(item.get("text", "")).strip()
        if text:
            lines.append(f"{speaker} | {text}")
    return "\n".join(lines)


def parse_cards_text(cards_text: str) -> tuple[list[dict[str, str]], list[str]]:
    cards = []
    errors = []
    for line_no, raw_line in enumerate(cards_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line:
            name, orientation = [part.strip() for part in line.split("|", 1)]
        else:
            parts = line.replace("，", " ").replace(",", " ").split()
            name = " ".join(parts[:-1]).strip()
            orientation = parts[-1].strip() if parts else ""
        if orientation not in {"正位", "逆位"}:
            errors.append(f"第 {line_no} 行牌面方向必须是 正位 或 逆位")
            continue
        if not name:
            errors.append(f"第 {line_no} 行缺少牌名")
            continue
        cards.append({"name": name, "orientation": orientation})
    return cards, errors


def parse_followups_text(followups_text: str) -> list[dict[str, str]]:
    followups = []
    for raw_line in followups_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line:
            speaker, text = [part.strip() for part in line.split("|", 1)]
        else:
            speaker, text = "unknown", line
        if text:
            followups.append({"speaker": speaker or "unknown", "text": text})
    return followups


def build_reviewed_case(
    original: dict[str, Any],
    reader_id: str,
    reviewed_path: Path,
    question: str,
    background: str,
    spread: str,
    cards_text: str,
    reader_answer: str,
    followups_text: str,
    notes: str,
) -> tuple[dict[str, Any], list[str]]:
    cards, card_errors = parse_cards_text(cards_text)
    source_images = original.get("source_images") or ([original["source_image"]] if original.get("source_image") else [])
    case_id = str(original.get("case_id") or next_manual_case_id(reviewed_path, reader_id))
    edited_case = {
        "reader_id": reader_id,
        "case_id": case_id,
        "question": question.strip(),
        "background": background.strip(),
        "spread": spread.strip() or "无牌阵三张牌",
        "cards": cards,
        "reader_answer": reader_answer.strip(),
        "followups": parse_followups_text(followups_text),
        "source_images": source_images,
        "case_type": original.get("case_type", "tieba_screenshot"),
        "quality": "reviewed",
        "privacy_status": "manual_reviewed",
        "notes": notes.strip(),
    }

    errors = list(card_errors)
    if not edited_case["question"]:
        errors.append("问题不能为空")
    if not edited_case["reader_answer"]:
        errors.append("占卜师回答不能为空")
    if not edited_case["cards"]:
        errors.append("至少需要一张牌")
    return edited_case, errors


def next_manual_case_id(reviewed_path: Path, reader_id: str) -> str:
    existing = count_jsonl_lines(reviewed_path) if reviewed_path.exists() else 0
    return f"{reader_id}_manual_{existing + 1:04d}"


def append_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_jsonl_file(path)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def backup_jsonl_file(path: Path) -> None:
    if not path.exists():
        return
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                value = {"raw": line.strip(), "parse_error": True}
            if isinstance(value, dict):
                rows.append(value)
            else:
                rows.append({"value": value})
    return rows


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


def load_jsonl_preview(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"raw": line.strip(), "parse_error": True})
            if len(rows) >= limit:
                break
    return rows


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
