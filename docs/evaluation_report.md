# Evaluation Report

Generated at: 2026-06-12T18:08:44
Generation mode: retrieval/structure only

## Summary

- RAG: 5/5 passed
- Agent: 3/3 passed

## RAG Checks

| ID | Status | Returned docs | Source matches | Term matches | Notes |
| --- | --- | ---: | --- | --- | --- |
| rag_001 | PASS | 5 | the-tarot-history-symbolism-and-divination-9781440649752-1440649758.pdf | trumps | Checks whether retrieval finds the passage defining Tarot by its fifth suit and major arcana. |
| rag_002 | PASS | 5 | the-tarot-history-symbolism-and-divination-9781440649752-1440649758.pdf | Fool, Magician, Marseilles | Checks major arcana ordering and naming evidence. |
| rag_003 | PASS | 5 | the-tarot-history-symbolism-and-divination-9781440649752-1440649758.pdf | Death, Tower | Checks retrieval of historical context involving missing or varied trumps. |
| rag_004 | PASS | 5 | the-tarot-history-symbolism-and-divination-9781440649752-1440649758.pdf | High Priestess, Papesse, Waite-Smith | Checks source-backed retrieval for a naming/history question. |
| rag_005 | PASS | 5 | the-tarot-history-symbolism-and-divination-9781440649752-1440649758.pdf | Hebrew, Levi, Magician | Checks retrieval on occult correspondence material. |

## Agent Checks

| ID | Status | Used cards | Missing cards | Extra cards | Steps | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| agent_001 | PASS | 权杖二, 宝剑八, 星币三 | - | - | parse_user_input, retrieve_tarot_knowledge, retrieve_reader_cases, load_persona_profile, generate_reading | 使用全部三张牌; 不要新增无关牌; 结合行动建议 |
| agent_002 | PASS | 圣杯三, 宝剑侍从, 节制 | - | - | parse_user_input, retrieve_tarot_knowledge, retrieve_reader_cases, load_persona_profile, generate_reading | 使用全部三张牌; 不要新增无关牌; 解释关系与沟通张力 |
| agent_003 | PASS | 星币八, 隐士, 权杖六 | - | - | parse_user_input, retrieve_tarot_knowledge, retrieve_reader_cases, load_persona_profile, generate_reading | 使用全部三张牌; 不要新增无关牌; 给出可执行建议 |

## How to Use This Report

- Treat FAIL rows as regression or improvement candidates, not as embarrassment.
- Add real failed demo cases back into `data/evals/*.jsonl` before changing prompts or retrieval logic.
- Compare this report before and after prompt, reranking, model, or data changes.
