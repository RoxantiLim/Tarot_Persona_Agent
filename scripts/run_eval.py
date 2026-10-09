from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tarot_agent import agent_graph
from src.tarot_agent.agent_graph import run_persona_reading
from src.tarot_agent.cards import card_display_names
from src.tarot_agent.config import AppConfig
from src.tarot_agent.documents import Document
from src.tarot_agent.rag_chain import answer_knowledge_query, retrieve_context


EVAL_DIR = PROJECT_ROOT / "data" / "evals"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"
DOCS_REPORT = PROJECT_ROOT / "docs" / "evaluation_report.md"


@dataclass
class EvalOutcome:
    id: str
    passed: bool
    metrics: dict[str, Any]
    notes: str = ""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_number}: {exc}") from exc
    return rows


def document_source(doc: Document) -> str:
    metadata = doc.metadata
    return f"{metadata.get('source_file', 'unknown')}#page={metadata.get('page', '?')}"


def matched_items(haystack: str, items: list[str]) -> list[str]:
    text = haystack.lower()
    return [item for item in items if item.lower() in text]


def evaluate_rag(config: AppConfig, examples: list[dict[str, Any]], skip_generation: bool) -> list[EvalOutcome]:
    outcomes: list[EvalOutcome] = []
    for example in examples:
        top_k = int(example.get("top_k", 5))
        docs = retrieve_context(config, example["query"], top_k=top_k)
        answer = ""
        error = ""
        if not skip_generation:
            result = answer_knowledge_query(
                config=config,
                mode=example.get("mode", "资料检索"),
                query=example["query"],
                card_name=example.get("card_name", ""),
                orientation=example.get("orientation", "不限定"),
                topic=example.get("topic", "通用"),
                top_k=top_k,
            )
            answer = result.answer
            error = result.error
            docs = result.context_docs

        sources = [document_source(doc) for doc in docs]
        context_blob = "\n".join([doc.page_content for doc in docs])
        expected_sources = list(example.get("expected_sources", []))
        expected_terms = list(example.get("expected_terms", []))
        source_matches = matched_items("\n".join(sources), expected_sources)
        context_term_matches = matched_items(context_blob, expected_terms)
        answer_term_matches = matched_items(answer, expected_terms)

        metrics = {
            "query": example["query"],
            "returned_docs": len(docs),
            "sources": sources,
            "expected_sources": expected_sources,
            "source_matches": source_matches,
            "expected_terms": expected_terms,
            "context_term_matches": context_term_matches,
            "answer_term_matches": answer_term_matches,
            "answer_nonempty": bool(answer.strip()),
            "error": error,
        }
        passed = (
            len(docs) > 0
            and (not expected_sources or bool(source_matches))
            and (not expected_terms or bool(context_term_matches or answer_term_matches))
        )
        outcomes.append(EvalOutcome(id=example["id"], passed=passed, metrics=metrics, notes=example.get("notes", "")))
    return outcomes


def evaluate_agent(config: AppConfig, examples: list[dict[str, Any]], skip_generation: bool) -> list[EvalOutcome]:
    outcomes: list[EvalOutcome] = []
    all_card_names = set(card_display_names())
    expected_steps = [
        "parse_user_input",
        "retrieve_tarot_knowledge",
        "retrieve_reader_cases",
        "load_persona_profile",
        "generate_reading",
    ]

    for example in examples:
        if skip_generation:
            original_chat = agent_graph.deepseek_chat

            def fake_chat(_config: AppConfig, _messages: list[dict[str, str]], temperature: float = 0.3) -> str:
                cards_text = "、".join(example.get("must_include_cards", []))
                return f"离线评估占位回答：本次解读使用 {cards_text}，并给出行动建议。"

            agent_graph.deepseek_chat = fake_chat
            try:
                result = run_persona_reading(
                    config=config,
                    reader_id=example.get("reader_id", "tarotist_1"),
                    question=example["question"],
                    cards=example["cards"],
                    include_check=False,
                )
            finally:
                agent_graph.deepseek_chat = original_chat
            answer = result.answer
            debug = result.debug
            knowledge_docs = result.knowledge_docs
            similar_cases = result.similar_cases
        else:
            result = run_persona_reading(
                config=config,
                reader_id=example.get("reader_id", "tarotist_1"),
                question=example["question"],
                cards=example["cards"],
                include_check=False,
            )
            answer = result.answer
            debug = result.debug
            knowledge_docs = result.knowledge_docs
            similar_cases = result.similar_cases

        must_include_cards = list(example.get("must_include_cards", []))
        forbidden_cards = list(example.get("forbidden_cards", []))
        input_cards = {card["name"] for card in example["cards"]}
        used_cards = [card for card in must_include_cards if card in answer]
        missing_cards = [card for card in must_include_cards if card not in answer]
        explicit_forbidden_hits = [card for card in forbidden_cards if card in answer]
        extra_cards = sorted(card for card in all_card_names if card in answer and card not in input_cards)
        steps = list(debug.get("steps", []))
        missing_steps = [step for step in expected_steps if step not in steps]

        metrics = {
            "question": example["question"],
            "reader_id": example.get("reader_id", "tarotist_1"),
            "answer_nonempty": bool(answer.strip()),
            "used_cards": used_cards,
            "missing_cards": missing_cards,
            "explicit_forbidden_hits": explicit_forbidden_hits,
            "extra_cards": extra_cards,
            "steps": steps,
            "missing_steps": missing_steps,
            "knowledge_docs_count": len(knowledge_docs),
            "similar_cases_count": len(similar_cases),
            "card_retry_missing": debug.get("card_retry_missing", []),
            "langgraph_fallback": debug.get("langgraph_fallback", ""),
        }
        passed = (
            bool(answer.strip())
            and not missing_cards
            and not explicit_forbidden_hits
            and not extra_cards
            and not missing_steps
        )
        outcomes.append(
            EvalOutcome(
                id=example["id"],
                passed=passed,
                metrics=metrics,
                notes="; ".join(example.get("expected_behavior", [])),
            )
        )
    return outcomes


def summarize(outcomes: list[EvalOutcome]) -> dict[str, Any]:
    total = len(outcomes)
    passed = sum(1 for outcome in outcomes if outcome.passed)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def write_json_report(report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / "eval_report.json"
    with output.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return output


def status_text(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def write_markdown_report(report: dict[str, Any]) -> Path:
    lines = [
        "# Evaluation Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Generation mode: {'retrieval/structure only' if report['skip_generation'] else 'retrieval + LLM generation'}",
        "",
        "## Summary",
        "",
        f"- RAG: {report['summary']['rag']['passed']}/{report['summary']['rag']['total']} passed",
        f"- Agent: {report['summary']['agent']['passed']}/{report['summary']['agent']['total']} passed",
        "",
        "## RAG Checks",
        "",
        "| ID | Status | Returned docs | Source matches | Term matches | Notes |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for outcome in report["rag"]:
        metrics = outcome["metrics"]
        term_matches = sorted(set(metrics["context_term_matches"] + metrics["answer_term_matches"]))
        lines.append(
            "| {id} | {status} | {docs} | {sources} | {terms} | {notes} |".format(
                id=outcome["id"],
                status=status_text(outcome["passed"]),
                docs=metrics["returned_docs"],
                sources=", ".join(metrics["source_matches"]) or "-",
                terms=", ".join(term_matches) or "-",
                notes=outcome.get("notes", "").replace("|", "/"),
            )
        )

    lines.extend(
        [
            "",
            "## Agent Checks",
            "",
            "| ID | Status | Used cards | Missing cards | Extra cards | Steps | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for outcome in report["agent"]:
        metrics = outcome["metrics"]
        lines.append(
            "| {id} | {status} | {used} | {missing} | {extra} | {steps} | {notes} |".format(
                id=outcome["id"],
                status=status_text(outcome["passed"]),
                used=", ".join(metrics["used_cards"]) or "-",
                missing=", ".join(metrics["missing_cards"]) or "-",
                extra=", ".join(metrics["extra_cards"]) or "-",
                steps=", ".join(metrics["steps"]) or "-",
                notes=outcome.get("notes", "").replace("|", "/"),
            )
        )

    lines.extend(
        [
            "",
            "## How to Use This Report",
            "",
            "- Treat FAIL rows as regression or improvement candidates, not as embarrassment.",
            "- Add real failed demo cases back into `data/evals/*.jsonl` before changing prompts or retrieval logic.",
            "- Compare this report before and after prompt, reranking, model, or data changes.",
            "",
        ]
    )

    DOCS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_REPORT.write_text("\n".join(lines), encoding="utf-8")
    return DOCS_REPORT


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline evals for Tarot Persona Agent.")
    parser.add_argument("--skip-generation", action="store_true", help="Only test retrieval and structural checks; do not call the LLM.")
    args = parser.parse_args()

    config = AppConfig.load()
    rag_examples = load_jsonl(EVAL_DIR / "rag_knowledge.jsonl")
    agent_examples = load_jsonl(EVAL_DIR / "persona_reading.jsonl")

    rag_outcomes = evaluate_rag(config, rag_examples, skip_generation=args.skip_generation)
    agent_outcomes = evaluate_agent(config, agent_examples, skip_generation=args.skip_generation)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "skip_generation": args.skip_generation,
        "summary": {
            "rag": summarize(rag_outcomes),
            "agent": summarize(agent_outcomes),
        },
        "rag": [asdict(outcome) for outcome in rag_outcomes],
        "agent": [asdict(outcome) for outcome in agent_outcomes],
    }

    json_path = write_json_report(report)
    markdown_path = write_markdown_report(report)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(f"RAG: {report['summary']['rag']['passed']}/{report['summary']['rag']['total']} passed")
    print(f"Agent: {report['summary']['agent']['passed']}/{report['summary']['agent']['total']} passed")


if __name__ == "__main__":
    main()
