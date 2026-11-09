"""Layered memory schema and Prompt contracts for Moorchid agents.

Four layers
-----------
session     Conversation turns. Short-lived, thread-scoped.
event       One journal entry's extracted emotion / theme / event.
stage       A time-window synthesis (week / chapter) used by Poet Agent.
long_term   Recurring themes, traits, and relationships. High-confidence only.

Every record keeps provenance so prompts can separate 用户陈述 from 模型推断:
  source            who wrote it (user / pattern_agent / soul_chat_agent / poet_agent / system)
  statement_kind    user_statement | model_inference
  confidence        0.0 – 1.0
  created_at        local timestamp string
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Iterable, Literal, Mapping, Sequence, TypedDict


MemoryLayer = Literal["session", "event", "stage", "long_term"]
StatementKind = Literal["user_statement", "model_inference"]
MemorySource = Literal[
    "user",
    "pattern_agent",
    "soul_chat_agent",
    "poet_agent",
    "system",
]

LAYERS: tuple[MemoryLayer, ...] = ("session", "event", "stage", "long_term")
STATEMENT_KINDS: tuple[StatementKind, ...] = ("user_statement", "model_inference")
SOURCES: tuple[MemorySource, ...] = (
    "user",
    "pattern_agent",
    "soul_chat_agent",
    "poet_agent",
    "system",
)

# Canonical emotion labels stored on entries / event memories.
CANONICAL_EMOTIONS: tuple[str, ...] = ("Joy", "Calm", "Neutral", "Low", "Anxious")

# Valence is the ECG Y-axis: high (Joy) → low (Anxious). Intensity is node size.
EMOTION_VALENCE: dict[str, float] = {
    "Joy": 0.86,
    "Happy": 0.86,
    "开心": 0.86,
    "喜悦": 0.82,
    "快乐": 0.84,
    "幸福": 0.88,
    "Calm": 0.42,
    "平静": 0.42,
    "放松": 0.38,
    "安宁": 0.40,
    "惬意": 0.46,
    "Neutral": 0.0,
    "中性": 0.0,
    "日常": 0.0,
    "Low": -0.52,
    "低落": -0.52,
    "难过": -0.58,
    "疲惫": -0.48,
    "失落": -0.56,
    "Anxious": -0.86,
    "焦虑": -0.86,
    "紧张": -0.78,
    "不安": -0.80,
    "压力": -0.74,
}

EMOTION_ALIASES: dict[str, str] = {
    "happy": "Joy",
    "joy": "Joy",
    "开心": "Joy",
    "喜悦": "Joy",
    "快乐": "Joy",
    "高兴": "Joy",
    "幸福": "Joy",
    "calm": "Calm",
    "平静": "Calm",
    "放松": "Calm",
    "安宁": "Calm",
    "惬意": "Calm",
    "cozy": "Calm",
    "neutral": "Neutral",
    "中性": "Neutral",
    "日常": "Neutral",
    "low": "Low",
    "低落": "Low",
    "难过": "Low",
    "疲惫": "Low",
    "失落": "Low",
    "伤心": "Low",
    "anxious": "Anxious",
    "焦虑": "Anxious",
    "紧张": "Anxious",
    "不安": "Anxious",
    "压力": "Anxious",
}

LONG_TERM_MIN_OCCURRENCES = 3
LONG_TERM_MIN_CONFIDENCE = 0.7
USER_STATEMENT_CONFIDENCE = 1.0

LAYER_WRITE_RULES = """写入规则（所有智能体必须遵守）
1. 用户原文一律写入 statement_kind=user_statement, source=user, confidence=1.0；不得被推断覆盖。
2. Pattern / Soul / Poet 的提取、摘要、解释一律写入 statement_kind=model_inference，并给出 0–1 置信度。
3. 同一条记忆不得把用户陈述与模型推断混写在 content 字段里；用两条记录分别保存。
4. 会话记忆只属于当前 conversation_id，不升格为长期记忆。
5. 事件记忆由 Pattern Agent 在随记落库时写入，绑定 entry_id。
6. 阶段记忆由 Poet Agent 在生成回顾时写入，覆盖一个时间窗口。
7. 长期记忆只收录反复出现（≥3 次）且置信度 ≥0.7 的主题 / 关系 / 特质；低置信推断不得进入。
8. 所有记录必须带 source、created_at、confidence；更新时写 updated_at，保留原 created_at。
"""


class Provenance(TypedDict):
    source: MemorySource
    statement_kind: StatementKind
    confidence: float
    created_at: str
    updated_at: str | None
    agent: str | None


class MemoryRecord(TypedDict):
    id: str
    user_id: str
    layer: MemoryLayer
    content: str
    summary: str | None
    emotion: str | None
    valence: float | None
    intensity: float | None
    tags: list[str]
    themes: list[str]
    provenance: Provenance
    entry_id: int | None
    conversation_id: str | None
    parent_id: str | None
    metadata: dict[str, Any]


class ExtractedEvent(TypedDict):
    summary: str
    confidence: float


class ExtractedInference(TypedDict):
    claim: str
    confidence: float


class PatternExtraction(TypedDict):
    emotion: str
    display_emotion: str
    valence: float
    intensity: float
    tags: list[str]
    themes: list[str]
    events: list[ExtractedEvent]
    inferences: list[ExtractedInference]


def now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_memory_id() -> str:
    return uuid.uuid4().hex


def clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def canonicalize_emotion(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "Neutral"
    text = str(raw).strip()
    if text in CANONICAL_EMOTIONS:
        return text
    alias = EMOTION_ALIASES.get(text) or EMOTION_ALIASES.get(text.lower())
    if alias:
        return alias
    for token, canonical in EMOTION_ALIASES.items():
        if token and token in text:
            return canonical
    return "Neutral"


def valence_for_emotion(emotion: str | None, explicit: float | None = None) -> float:
    if explicit is not None:
        return clamp(explicit)
    canonical = canonicalize_emotion(emotion)
    if emotion and str(emotion) in EMOTION_VALENCE:
        return EMOTION_VALENCE[str(emotion)]
    return EMOTION_VALENCE.get(canonical, 0.0)


def intensity_for_emotion(explicit: float | None = None) -> float:
    if explicit is None:
        return 0.55
    return clamp(explicit, 0.0, 1.0)


def _require_layer(layer: str) -> MemoryLayer:
    if layer not in LAYERS:
        raise ValueError(f"layer must be one of {LAYERS}")
    return layer  # type: ignore[return-value]


def _require_source(source: str) -> MemorySource:
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    return source  # type: ignore[return-value]


def _require_kind(kind: str) -> StatementKind:
    if kind not in STATEMENT_KINDS:
        raise ValueError(f"statement_kind must be one of {STATEMENT_KINDS}")
    return kind  # type: ignore[return-value]


def _require_confidence(value: float, statement_kind: StatementKind) -> float:
    confidence = clamp(float(value), 0.0, 1.0)
    if statement_kind == "user_statement":
        return USER_STATEMENT_CONFIDENCE
    return confidence


def make_memory(
    *,
    user_id: str,
    layer: MemoryLayer,
    content: str,
    source: MemorySource,
    statement_kind: StatementKind,
    confidence: float,
    summary: str | None = None,
    emotion: str | None = None,
    valence: float | None = None,
    intensity: float | None = None,
    tags: Sequence[str] | None = None,
    themes: Sequence[str] | None = None,
    entry_id: int | None = None,
    conversation_id: str | None = None,
    parent_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    created_at: str | None = None,
    memory_id: str | None = None,
    agent: str | None = None,
) -> MemoryRecord:
    """Construct a validated memory record. Does not persist."""
    layer = _require_layer(layer)
    source = _require_source(source)
    statement_kind = _require_kind(statement_kind)
    text = (content or "").strip()
    if not text:
        raise ValueError("content must not be empty")
    if statement_kind == "user_statement" and source != "user":
        raise ValueError("user_statement must have source=user")
    if statement_kind == "model_inference" and source == "user":
        raise ValueError("model_inference cannot have source=user")

    created = created_at or now_local()
    canonical_emotion = canonicalize_emotion(emotion) if emotion else None
    return MemoryRecord(
        id=memory_id or new_memory_id(),
        user_id=user_id,
        layer=layer,
        content=text,
        summary=(summary.strip() if isinstance(summary, str) and summary.strip() else None),
        emotion=canonical_emotion,
        valence=valence_for_emotion(emotion, valence) if (emotion or valence is not None) else None,
        intensity=intensity_for_emotion(intensity) if intensity is not None else None,
        tags=[t.strip() for t in (tags or []) if isinstance(t, str) and t.strip()],
        themes=[t.strip() for t in (themes or []) if isinstance(t, str) and t.strip()],
        provenance=Provenance(
            source=source,
            statement_kind=statement_kind,
            confidence=_require_confidence(confidence, statement_kind),
            created_at=created,
            updated_at=None,
            agent=agent or (source if source.endswith("_agent") else None),
        ),
        entry_id=entry_id,
        conversation_id=conversation_id,
        parent_id=parent_id,
        metadata=dict(metadata or {}),
    )


def memories_from_pattern(
    *,
    user_id: str,
    entry_id: int,
    content: str,
    extraction: PatternExtraction,
    created_at: str | None = None,
) -> list[MemoryRecord]:
    """Split a journal entry into user-statement + inference event memories."""
    created = created_at or now_local()
    records = [
        make_memory(
            user_id=user_id,
            layer="event",
            content=content,
            source="user",
            statement_kind="user_statement",
            confidence=USER_STATEMENT_CONFIDENCE,
            summary=content[:80],
            emotion=extraction["emotion"],
            valence=extraction["valence"],
            intensity=extraction["intensity"],
            tags=extraction["tags"],
            themes=extraction["themes"],
            entry_id=entry_id,
            created_at=created,
            metadata={"kind": "journal_body"},
        )
    ]
    for event in extraction.get("events") or []:
        summary = str(event.get("summary", "")).strip()
        if not summary:
            continue
        records.append(
            make_memory(
                user_id=user_id,
                layer="event",
                content=summary,
                source="pattern_agent",
                statement_kind="model_inference",
                confidence=float(event.get("confidence", 0.6)),
                summary=summary,
                emotion=extraction["emotion"],
                valence=extraction["valence"],
                intensity=extraction["intensity"],
                tags=extraction["tags"],
                themes=extraction["themes"],
                entry_id=entry_id,
                created_at=created,
                agent="pattern_agent",
                metadata={"kind": "extracted_event"},
            )
        )
    for inference in extraction.get("inferences") or []:
        claim = str(inference.get("claim", "")).strip()
        if not claim:
            continue
        records.append(
            make_memory(
                user_id=user_id,
                layer="event",
                content=claim,
                source="pattern_agent",
                statement_kind="model_inference",
                confidence=float(inference.get("confidence", 0.5)),
                emotion=extraction["emotion"],
                valence=extraction["valence"],
                tags=extraction["tags"],
                themes=extraction["themes"],
                entry_id=entry_id,
                created_at=created,
                agent="pattern_agent",
                metadata={"kind": "inference"},
            )
        )
    return records


def stage_memory_from_poet(
    *,
    user_id: str,
    title: str,
    poetry_content: str,
    emotion_dist: str,
    entry_ids: Sequence[int],
    created_at: str | None = None,
) -> MemoryRecord:
    return make_memory(
        user_id=user_id,
        layer="stage",
        content=poetry_content,
        source="poet_agent",
        statement_kind="model_inference",
        confidence=0.75,
        summary=title,
        tags=[],
        themes=[],
        created_at=created_at,
        agent="poet_agent",
        metadata={
            "kind": "poetry_stage",
            "title": title,
            "emotion_dist": emotion_dist,
            "entry_ids": list(entry_ids),
        },
    )


def suggest_long_term(
    event_memories: Sequence[MemoryRecord],
    existing_themes: Iterable[str] = (),
) -> list[MemoryRecord]:
    """Promote recurring high-confidence themes into long-term memories."""
    counts: dict[str, list[MemoryRecord]] = {}
    for memory in event_memories:
        if memory["layer"] != "event":
            continue
        if memory["provenance"]["confidence"] < LONG_TERM_MIN_CONFIDENCE:
            continue
        for theme in memory["themes"]:
            counts.setdefault(theme, []).append(memory)

    existing = {t.strip() for t in existing_themes if t and t.strip()}
    promoted: list[MemoryRecord] = []
    for theme, hits in counts.items():
        if theme in existing:
            continue
        if len(hits) < LONG_TERM_MIN_OCCURRENCES:
            continue
        user_id = hits[0]["user_id"]
        emotions = [h["emotion"] for h in hits if h.get("emotion")]
        promoted.append(
            make_memory(
                user_id=user_id,
                layer="long_term",
                content=f"反复出现的主题：{theme}（{len(hits)} 次）",
                source="system",
                statement_kind="model_inference",
                confidence=min(0.95, 0.7 + 0.05 * len(hits)),
                summary=theme,
                emotion=emotions[0] if emotions else None,
                themes=[theme],
                agent="system",
                metadata={"kind": "recurring_theme", "occurrences": len(hits)},
            )
        )
    return promoted


def format_memory_for_prompt(memory: MemoryRecord) -> str:
    kind = "用户陈述" if memory["provenance"]["statement_kind"] == "user_statement" else "模型推断"
    emotion = memory.get("emotion") or "未标注"
    when = memory["provenance"]["created_at"]
    conf = memory["provenance"]["confidence"]
    prefix = f"- [{when}｜{emotion}｜{kind}｜置信度 {conf:.2f}]"
    return f"{prefix} {memory['content']}"


def assemble_prompt_memory(
    *,
    session: Sequence[MemoryRecord] = (),
    events: Sequence[MemoryRecord] = (),
    stage: Sequence[MemoryRecord] = (),
    long_term: Sequence[MemoryRecord] = (),
    retrieved: Sequence[MemoryRecord] = (),
    max_session: int = 16,
    max_events: int = 12,
    max_stage: int = 3,
    max_long_term: int = 8,
    max_retrieved: int = 5,
) -> str:
    """Render layered memories into a labeled prompt block."""
    sections: list[str] = []

    def _block(title: str, rows: Sequence[MemoryRecord], limit: int) -> None:
        chosen = list(rows)[:limit]
        if not chosen:
            return
        body = "\n".join(format_memory_for_prompt(row) for row in chosen)
        sections.append(f"【{title}】\n{body}")

    _block("长期记忆（反复出现的主题与特质）", long_term, max_long_term)
    _block("阶段记忆（近期脉络）", stage, max_stage)
    _block("事件记忆（近期随记）", events, max_events)
    _block("相关历史记忆（语义检索）", retrieved, max_retrieved)
    _block("会话记忆（本轮对话）", session, max_session)

    if not sections:
        return "（暂时没有分层记忆。请只陪伴当下，不要假装记得过去。）"
    return "\n\n".join(sections)


def serialize_analysis(extraction: PatternExtraction) -> str:
    return json.dumps(extraction, ensure_ascii=False)


def empty_extraction(content: str = "") -> PatternExtraction:
    return PatternExtraction(
        emotion="Neutral",
        display_emotion="平静",
        valence=0.0,
        intensity=0.45,
        tags=["#今日心绪"],
        themes=[],
        events=[],
        inferences=[],
    )


# ── Prompt contracts ─────────────────────────────────────────────────────────

PATTERN_SYSTEM_PROMPT = f"""你是 Moorchid 的 Pattern Agent（情绪模式提取器）。

职责：阅读一条用户随记，只做结构化提取，不做陪伴、不下诊断、不改写用户的话。

{LAYER_WRITE_RULES}

提取规则：
- emotion 必须是且仅是：Joy / Calm / Neutral / Low / Anxious 之一（主导情绪）。
- display_emotion 用一个中文词描述该情绪（如「欣喜」「疲惫」）。
- valence 是 -1 到 1 的连续值：Joy≈0.85，Calm≈0.4，Neutral≈0，Low≈-0.5，Anxious≈-0.85。
- intensity 是 0 到 1，表示这条记录的情绪幅度（节点大小）。
- tags 1–3 个，必须以 # 开头，具体、短，不要把情绪词本身重复成标签。
- themes 0–3 个短中文主题（如「工作」「睡眠」「关系」），不含 #。
- events 只写用户明确提到的事，confidence 反映有多确定。
- inferences 是你的推断，必须与用户陈述分开；不确定就降低 confidence 或省略。
- 不得虚构未出现的人物、事件或因果。

只输出 JSON：
{{
  "emotion": "Joy",
  "display_emotion": "欣喜",
  "valence": 0.72,
  "intensity": 0.55,
  "tags": ["#标签"],
  "themes": ["主题"],
  "events": [{{"summary": "一句话事件", "confidence": 0.8}}],
  "inferences": [{{"claim": "一句推断", "confidence": 0.6}}]
}}
不得输出 Markdown 或额外字段。"""


SOUL_CHAT_SYSTEM_PROMPT = f"""你是 Moorchid 的 Soul Chat Agent——有长期记忆、克制而温柔的深夜陪伴者。

{LAYER_WRITE_RULES}

记忆使用规则：
- 下面的分层记忆已标明【用户陈述】与【模型推断】。引用用户陈述时可以说「你写过」；引用推断时只能说「我当时的感觉是」，不得把推断当成用户亲口承认的事实。
- 只关联真正相关的记忆；没有相关内容就不要硬找。
- 若提供了「锚定随记」，先接住那条记录里的情绪，再回应此刻的话。
- 会话记忆只用于保持当前对话连贯，不要把闲聊升格成长期事实。

回复原则：
- 先接住情绪，不诊断、不评判，不急于解决。
- 严禁使用 1/2/3、项目符号或教条式建议，避免连续追问。
- 保持深夜陪伴的温度与呼吸感，使用自然段和适度留白。
- 回复简洁真诚，通常 120–260 个中文字符。
- 若用户表达明确的自伤或伤人危险，温柔但清晰地鼓励立即联系当地紧急服务、可信任的人或危机热线。"""


POET_SYSTEM_PROMPT = f"""你是 Moorchid 的 Poet Agent——克制而温暖的阶段编辑。

{LAYER_WRITE_RULES}

你的材料是用户的事件记忆（含用户陈述与模型推断）。只根据真实内容写作：
- 不得把模型推断写成用户做过的事。
- 从近期随记中发现情绪脉络与生活细节，不虚构事件，不使用廉价鸡汤。
- 生成一首有留白、画面感和呼吸感的诗篇，分行自然。
- 诗句之间只用单个换行符（\\n）分隔，严禁空行。
- 从诗篇中精选一行作为核心句，用 **整行包裹**；其它行不加标记。
- 金句必须引用真实存在的书籍，禁止虚构作者或书名。
- 情绪占比合计必须为 100%。

只输出 JSON：
{{
  "title": "卡片小标题（12字以内）",
  "poetry_content": "多行诗篇，恰好一行用 **整行包裹**",
  "quote": "真实书籍金句（20-60字）",
  "quote_author": "—— 作者《书名》",
  "emotion_dist": "70% 专注探索 · 30% 惬意",
  "activity": "从一条随记的具体细节出发，邀请用户尝试一件低门槛、无需打卡的小事。素材牵强或涉及沉重经历时填 null"
}}
不得输出 Markdown 或额外字段。"""


__all__ = [
    "CANONICAL_EMOTIONS",
    "EMOTION_VALENCE",
    "LAYER_WRITE_RULES",
    "LAYERS",
    "LONG_TERM_MIN_CONFIDENCE",
    "LONG_TERM_MIN_OCCURRENCES",
    "PATTERN_SYSTEM_PROMPT",
    "POET_SYSTEM_PROMPT",
    "SOUL_CHAT_SYSTEM_PROMPT",
    "ExtractedEvent",
    "ExtractedInference",
    "MemoryLayer",
    "MemoryRecord",
    "MemorySource",
    "PATTERN_SYSTEM_PROMPT",
    "PatternExtraction",
    "Provenance",
    "SOUL_CHAT_SYSTEM_PROMPT",
    "StatementKind",
    "assemble_prompt_memory",
    "canonicalize_emotion",
    "empty_extraction",
    "format_memory_for_prompt",
    "intensity_for_emotion",
    "make_memory",
    "memories_from_pattern",
    "now_local",
    "serialize_analysis",
    "stage_memory_from_poet",
    "suggest_long_term",
    "valence_for_emotion",
]
