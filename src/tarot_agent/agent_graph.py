from __future__ import annotations

from typing import Any, TypedDict

from .cases import retrieve_similar_cases
from .config import AppConfig
from .llm import deepseek_chat
from .persona import load_persona
from .prompts import PERSONA_READING_TEMPLATE, STYLE_CHECK_TEMPLATE
from .rag_chain import format_context, retrieve_context
from .schemas import AgentResult


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


def _cards_text(cards: list[dict[str, str]]) -> str:
    return "；".join(f"{card['name']}（{card.get('orientation', '正位')}）" for card in cards)


def parse_user_input(state: ReadingState) -> ReadingState:
    cards_text = _cards_text(state["cards"])
    state["query"] = f"{state['question']} {cards_text}"
    state.setdefault("steps", []).append("parse_user_input")
    return state


def retrieve_tarot_knowledge(config: AppConfig):
    def node(state: ReadingState) -> ReadingState:
        state["knowledge_docs"] = retrieve_context(config, state["query"], top_k=5)
        state.setdefault("steps", []).append("retrieve_tarot_knowledge")
        return state

    return node


def retrieve_reader_cases(config: AppConfig):
    def node(state: ReadingState) -> ReadingState:
        state["similar_cases"] = retrieve_similar_cases(config, state["reader_id"], state["query"], limit=3)
        state.setdefault("steps", []).append("retrieve_reader_cases")
        return state

    return node


def load_persona_profile(config: AppConfig):
    def node(state: ReadingState) -> ReadingState:
        state["persona"] = load_persona(config, state["reader_id"]).model_dump()
        state.setdefault("steps", []).append("load_persona_profile")
        return state

    return node


def generate_reading(config: AppConfig):
    def node(state: ReadingState) -> ReadingState:
        case_context = "\n\n".join(
            f"问题：{case.get('question', '')}\n牌面：{case.get('cards', [])}\n回答：{case.get('reader_answer', '')}"
            for case in state.get("similar_cases", [])
        ) or "未检索到相似案例。"
        prompt = PERSONA_READING_TEMPLATE.format(
            persona=state["persona"],
            question=state["question"],
            cards=_cards_text(state["cards"]),
            knowledge_context=format_context(state.get("knowledge_docs", [])),
            case_context=case_context,
        )
        state["answer"] = deepseek_chat(config, [{"role": "user", "content": prompt}], temperature=0.45)
        state.setdefault("steps", []).append("generate_reading")
        return state

    return node


def style_and_grounding_check(config: AppConfig):
    def node(state: ReadingState) -> ReadingState:
        prompt = STYLE_CHECK_TEMPLATE.format(
            persona=state["persona"],
            cards=_cards_text(state["cards"]),
            answer=state.get("answer", ""),
        )
        state["check"] = deepseek_chat(config, [{"role": "user", "content": prompt}], temperature=0)
        state.setdefault("steps", []).append("style_and_grounding_check")
        return state

    return node


def run_persona_reading(
    config: AppConfig,
    reader_id: str,
    question: str,
    cards: list[dict[str, str]],
) -> AgentResult:
    initial_state: ReadingState = {
        "reader_id": reader_id,
        "question": question,
        "cards": cards,
        "steps": [],
    }
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(ReadingState)
        graph.add_node("parse_user_input", parse_user_input)
        graph.add_node("retrieve_tarot_knowledge", retrieve_tarot_knowledge(config))
        graph.add_node("retrieve_reader_cases", retrieve_reader_cases(config))
        graph.add_node("load_persona_profile", load_persona_profile(config))
        graph.add_node("generate_reading", generate_reading(config))
        graph.add_node("style_and_grounding_check", style_and_grounding_check(config))

        graph.set_entry_point("parse_user_input")
        graph.add_edge("parse_user_input", "retrieve_tarot_knowledge")
        graph.add_edge("retrieve_tarot_knowledge", "retrieve_reader_cases")
        graph.add_edge("retrieve_reader_cases", "load_persona_profile")
        graph.add_edge("load_persona_profile", "generate_reading")
        graph.add_edge("generate_reading", "style_and_grounding_check")
        graph.add_edge("style_and_grounding_check", END)
        final_state = graph.compile().invoke(initial_state)
    except Exception as exc:
        final_state = initial_state
        final_state = parse_user_input(final_state)
        final_state = retrieve_tarot_knowledge(config)(final_state)
        final_state = retrieve_reader_cases(config)(final_state)
        final_state = load_persona_profile(config)(final_state)
        final_state = generate_reading(config)(final_state)
        final_state = style_and_grounding_check(config)(final_state)
        final_state["langgraph_fallback"] = str(exc)

    return AgentResult(
        answer=final_state.get("answer", ""),
        debug={
            "reader_id": reader_id,
            "steps": final_state.get("steps", []),
            "style_check": final_state.get("check", ""),
            "langgraph_fallback": final_state.get("langgraph_fallback", ""),
        },
        knowledge_docs=final_state.get("knowledge_docs", []),
        similar_cases=final_state.get("similar_cases", []),
    )
