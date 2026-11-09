"""DeepSeek-powered agents with deterministic demo-safe fallbacks for Moorchid."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, NotRequired, TypedDict, cast

from memory_schema import (
    PATTERN_SYSTEM_PROMPT,
    POET_SYSTEM_PROMPT,
    SOUL_CHAT_SYSTEM_PROMPT,
    PatternExtraction,
    assemble_prompt_memory,
    canonicalize_emotion,
    empty_extraction,
    intensity_for_emotion,
    make_memory,
    serialize_analysis,
    valence_for_emotion,
)


LOGGER = logging.getLogger(__name__)
MAX_ENTRY_CONTENT_CHARS = 1_000
MAX_CHAT_MESSAGES = 20
MAX_POET_ENTRIES = 50
MAX_RECENT_ENTRIES = 12
MAX_RETRIEVED_MEMORIES = 5


class PatternResult(PatternExtraction):
    """Backward-compatible alias — Pattern Agent now returns a full extraction."""


class PoetResult(TypedDict):
    title: str
    poetry_content: str
    quote: str
    quote_author: str
    emotion_dist: str
    activity: NotRequired[str | None]


Entry = Mapping[str, Any]
ChatMessage = Mapping[str, str]


_PATTERN_SYSTEM_PROMPT = PATTERN_SYSTEM_PROMPT
_POET_SYSTEM_PROMPT = POET_SYSTEM_PROMPT

_EMOTION_KEYWORDS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("Anxious", ("焦虑", "担心", "害怕", "紧张", "压力", "来不及", "说不过来", "失眠"), "#内心波澜", "关系"),
    ("Low",     ("累", "疲惫", "困", "熬夜", "撑不住", "没力气", "难过", "伤心", "哭", "失落", "孤独", "委屈"), "#情绪低谷", "休息"),
    ("Joy",     ("开心", "快乐", "惊喜", "幸福", "太棒", "喜欢", "完成", "做到", "收获", "成就", "顺利"), "#微小确幸", "成就"),
    ("Calm",    ("平静", "安静", "放松", "惬意", "散步", "晚风", "期待", "希望"), "#生活片刻", "日常"),
)

_TOPIC_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("学习", "考试", "论文", "作业", "导师", "课程", "答辩"), "#学术压力"),
    (("工作", "项目", "会议", "加班", "客户", "同事"), "#工作日常"),
    (("朋友", "家人", "恋爱", "喜欢的人", "关系", "聊天"), "#关系心事"),
    (("睡觉", "睡眠", "失眠", "熬夜", "休息"), "#睡眠状态"),
    (("跑步", "运动", "健身", "瑜伽", "散步"), "#身体感受"),
    (("读书", "电影", "音乐", "画画", "摄影"), "#兴趣时光"),
)


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _safe_text(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _get_client():
    """Lazily build an OpenAI-compatible client targeting DeepSeek."""
    from config import get_config

    config = get_config()
    if not config.deepseek_enabled:
        return None, config

    try:
        from openai import OpenAI
    except Exception as exc:
        LOGGER.warning("openai SDK not available; using local mock: %s", exc)
        return None, config

    try:
        client = OpenAI(
            api_key=cast(str, config.deepseek_api_key),
            base_url=config.deepseek_base_url,
            timeout=config.deepseek_timeout_seconds,
            max_retries=0,
        )
        return client, config
    except Exception as exc:
        LOGGER.warning("Failed to build DeepSeek client; using local mock: %s", exc)
        return None, config


def _call_deepseek(
    messages: list[dict[str, str]],
    *,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> str | None:
    """Call DeepSeek Chat Completions, returning ``None`` whenever fallback is needed."""
    client, config = _get_client()
    if client is None:
        return None

    request: dict[str, Any] = {
        "model": config.deepseek_model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        request["response_format"] = {"type": "json_object"}

    try:
        completion = client.chat.completions.create(**request)
    except Exception as exc:
        LOGGER.warning(
            "DeepSeek request unavailable; using local mock output (%s)",
            type(exc).__name__,
        )
        return None

    try:
        content = completion.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        return None

    if not content:
        return None

    cleaned = content.strip()
    return cleaned or None


def _parse_json_object(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _mock_pattern(content: str) -> PatternExtraction:
    lowered = content.lower()
    emotion = "Neutral"
    tags: list[str] = []
    themes: list[str] = []

    for candidate, keywords, fallback_tag, theme in _EMOTION_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            emotion = candidate
            tags.append(fallback_tag)
            themes.append(theme)
            break

    for keywords, tag in _TOPIC_KEYWORDS:
        if any(keyword in lowered for keyword in keywords) and tag not in tags:
            tags.append(tag)
        if len(tags) == 3:
            break

    if not tags:
        tags.append("#今日心绪")

    snippet = content.strip()[:48]
    return PatternExtraction(
        emotion=emotion,
        display_emotion=_display_emotion(emotion),
        valence=valence_for_emotion(emotion),
        intensity=0.62 if emotion != "Neutral" else 0.4,
        tags=tags[:3],
        themes=themes[:3],
        events=[{"summary": snippet, "confidence": 0.55}] if snippet else [],
        inferences=[],
    )


def _display_emotion(emotion: str) -> str:
    return {
        "Joy": "欣喜",
        "Calm": "平静",
        "Neutral": "日常",
        "Low": "低落",
        "Anxious": "焦虑",
    }.get(canonicalize_emotion(emotion), "心绪")


def _as_str_list(value: Any, *, prefix: str | None = None, limit: int = 3) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip()
        if prefix and not text.startswith(prefix):
            text = prefix + text.lstrip("#")
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _validate_pattern(data: dict[str, Any] | None) -> PatternExtraction | None:
    if data is None:
        return None
    emotion_raw = data.get("emotion")
    if not isinstance(emotion_raw, str) or not emotion_raw.strip():
        return None
    emotion = canonicalize_emotion(emotion_raw)
    tags = _as_str_list(data.get("tags"), prefix="#", limit=3)
    if not tags:
        tags = ["#今日心绪"]
    themes = _as_str_list(data.get("themes"), limit=3)
    display = data.get("display_emotion")
    display_emotion = display.strip() if isinstance(display, str) and display.strip() else _display_emotion(emotion)

    events: list[dict[str, Any]] = []
    raw_events = data.get("events")
    if isinstance(raw_events, list):
        for item in raw_events[:3]:
            if not isinstance(item, dict):
                continue
            summary = item.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                continue
            try:
                confidence = float(item.get("confidence", 0.6))
            except (TypeError, ValueError):
                confidence = 0.6
            events.append({"summary": summary.strip()[:120], "confidence": max(0.0, min(1.0, confidence))})

    inferences: list[dict[str, Any]] = []
    raw_inferences = data.get("inferences")
    if isinstance(raw_inferences, list):
        for item in raw_inferences[:3]:
            if not isinstance(item, dict):
                continue
            claim = item.get("claim")
            if not isinstance(claim, str) or not claim.strip():
                continue
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            inferences.append({"claim": claim.strip()[:160], "confidence": max(0.0, min(1.0, confidence))})

    try:
        valence = float(data["valence"]) if data.get("valence") is not None else valence_for_emotion(emotion)
    except (TypeError, ValueError):
        valence = valence_for_emotion(emotion)
    try:
        intensity = float(data["intensity"]) if data.get("intensity") is not None else 0.55
    except (TypeError, ValueError):
        intensity = 0.55

    return PatternExtraction(
        emotion=emotion,
        display_emotion=display_emotion[:8],
        valence=valence_for_emotion(emotion, valence),
        intensity=intensity_for_emotion(intensity),
        tags=tags,
        themes=themes,
        events=events,  # type: ignore[typeddict-item]
        inferences=inferences,  # type: ignore[typeddict-item]
    )


def run_pattern_agent(content: str) -> PatternExtraction:
    """Extract emotion, valence, themes and events from a journal entry."""
    validated_content = _require_text(content, "content")
    raw = _call_deepseek(
        [
            {"role": "system", "content": _PATTERN_SYSTEM_PROMPT},
            {"role": "user", "content": validated_content},
        ],
        json_mode=True,
        temperature=0.2,
    )
    return _validate_pattern(_parse_json_object(raw)) or _mock_pattern(validated_content)


def _entries_as_event_memories(entries: Sequence[Entry]) -> list:
    records = []
    for entry in entries:
        content = _safe_text(entry.get("content"), "")[:MAX_ENTRY_CONTENT_CHARS]
        if not content:
            continue
        user_id = _safe_text(entry.get("user_id"), "user")
        emotion = _safe_text(entry.get("emotion"), "Neutral")
        tags = entry.get("tags", []) if isinstance(entry.get("tags"), list) else []
        created_at = _safe_text(entry.get("created_at")) or None
        try:
            records.append(
                make_memory(
                    user_id=user_id or "user",
                    layer="event",
                    content=content,
                    source="user",
                    statement_kind="user_statement",
                    confidence=1.0,
                    emotion=emotion,
                    valence=entry.get("valence") if isinstance(entry.get("valence"), (int, float)) else None,
                    tags=tags,
                    entry_id=int(entry["id"]) if entry.get("id") is not None else None,
                    created_at=created_at,
                    metadata={"kind": "journal_body"},
                )
            )
        except Exception:
            continue
    return records


def _session_memories_from_chat(chat_history: Sequence[ChatMessage], user_id: str = "user") -> list:
    records = []
    for message in chat_history:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            continue
        try:
            if role == "user":
                records.append(
                    make_memory(
                        user_id=user_id,
                        layer="session",
                        content=content.strip(),
                        source="user",
                        statement_kind="user_statement",
                        confidence=1.0,
                        metadata={"kind": "chat_turn"},
                    )
                )
            else:
                records.append(
                    make_memory(
                        user_id=user_id,
                        layer="session",
                        content=content.strip(),
                        source="soul_chat_agent",
                        statement_kind="model_inference",
                        confidence=0.55,
                        agent="soul_chat_agent",
                        metadata={"kind": "chat_turn"},
                    )
                )
        except Exception:
            continue
    return records


def _build_soul_memory_section(
    history_entries: Sequence[Entry],
    chat_history: Sequence[ChatMessage],
    layered_memory: str | None = None,
    retrieved_memory: str = "",
) -> str:
    if layered_memory:
        if retrieved_memory:
            return f"{layered_memory}\n\n【相关历史记忆（语义检索）】\n{retrieved_memory}"
        return layered_memory

    events = _entries_as_event_memories(list(history_entries)[:MAX_RECENT_ENTRIES])
    session = _session_memories_from_chat(chat_history)
    block = assemble_prompt_memory(events=events, session=session)
    if retrieved_memory:
        return f"{block}\n\n【相关历史记忆（语义检索）】\n{retrieved_memory}"
    return block


def _soul_system_prompt(memory_section: str, anchor_note: str = "") -> str:
    anchor_block = f"\n\n【锚定随记】\n{anchor_note}" if anchor_note else ""
    return f"""{SOUL_CHAT_SYSTEM_PROMPT}

【分层记忆】
{memory_section}{anchor_block}"""


def _format_retrieved_memories(entries: Sequence[Entry]) -> str:
    try:
        from embeddings import default_embedding_service
        from vector_store import format_memory_hits, get_vector_store
    except Exception as exc:
        LOGGER.warning("Vector store components unavailable; skipping memory formatting: %s", exc)
        return ""

    user_id = ""
    recent_contents: set[str] = set()
    for entry in entries:
        candidate = _safe_text(entry.get("content"), "")[:MAX_ENTRY_CONTENT_CHARS].strip()
        if candidate:
            recent_contents.add(candidate)
        if not user_id:
            user_id = _safe_text(entry.get("user_id"))

    if not user_id:
        return ""

    try:
        query_text = entries[0].get("content", "") if entries else ""
        if not isinstance(query_text, str) or not query_text.strip():
            return ""
        embedding = default_embedding_service().embed(query_text)
        hits = get_vector_store().query(user_id=user_id, embedding=embedding, top_k=MAX_RETRIEVED_MEMORIES)
    except Exception as exc:
        LOGGER.warning("Retrieval of memories failed: %s", exc)
        return ""

    filtered: list = []
    for hit in hits:
        if hit.content.strip() in recent_contents:
            continue
        filtered.append(hit)
    if not filtered:
        return ""

    return format_memory_hits(filtered)


def _normalize_chat_history(chat_history: Sequence[ChatMessage]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in list(chat_history)[-MAX_CHAT_MESSAGES:]:
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            normalized.append({"role": cast(str, role), "content": content})
    return normalized


async def run_soul_chat_stream(
    user_input: str,
    history_entries: list[Entry],
    chat_history: list[ChatMessage],
    layered_memory: str | None = None,
    anchor_entry: Entry | None = None,
):
    """
    Async generator — yields text chunks for true SSE streaming.
    Falls back to a non-streaming call if the model is unavailable.
    """
    import asyncio

    validated_input = _require_text(user_input, "user_input")
    if not isinstance(history_entries, list):
        raise TypeError("history_entries must be a list")
    if not isinstance(chat_history, list):
        raise TypeError("chat_history must be a list")

    recent_entries = list(history_entries)[:MAX_RECENT_ENTRIES]
    retrieved_memory = _format_retrieved_memories(recent_entries)
    memory_section = _build_soul_memory_section(
        recent_entries, chat_history, layered_memory, retrieved_memory
    )
    anchor_note = ""
    if anchor_entry:
        anchor_note = (
            f"[{_safe_text(anchor_entry.get('created_at'), '时间未记录')}｜"
            f"{_safe_text(anchor_entry.get('emotion'), '未标注')}] "
            f"{_safe_text(anchor_entry.get('content'), '')[:MAX_ENTRY_CONTENT_CHARS]}"
        )
    system_prompt = _soul_system_prompt(memory_section, anchor_note)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_normalize_chat_history(chat_history))
    messages.append({"role": "user", "content": validated_input})

    client, config = _get_client()
    if client is None:
        # Fall back to mock, stream it word by word
        fallback = _mock_soul_chat(validated_input, recent_entries, retrieved_memory)
        for i in range(0, len(fallback), 4):
            await asyncio.sleep(0.04)
            yield fallback[i : i + 4]
        return

    try:
        request: dict[str, Any] = {
            "model": config.deepseek_model,
            "messages": messages,
            "temperature": 0.8,
            "stream": True,
        }
        stream = client.chat.completions.create(**request)
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token
    except Exception as exc:
        LOGGER.warning("Streaming failed, falling back to mock: %s", exc)
        fallback = _mock_soul_chat(validated_input, recent_entries, retrieved_memory)
        for i in range(0, len(fallback), 4):
            await asyncio.sleep(0.04)
            yield fallback[i : i + 4]


def _mock_soul_chat(user_input: str, history_entries: Sequence[Entry], memories: str) -> str:
    prefix = "我在听。你不需要急着把这一刻整理得很有道理，先让它在这里停一会儿。"
    if not history_entries:
        return (
            f"{prefix}\n\n从你刚刚写下的\"{user_input[:36]}\"里，"
            "我能感觉到这件事正在占据你不少心绪。今晚可以不用马上解决它，"
            "你已经把感受说出来了，这本身就是在照顾自己。"
        )

    latest = history_entries[0]
    past_content = _safe_text(latest.get("content"))[:42]
    past_emotion = _safe_text(latest.get("emotion"), "那份心情")
    memory = (
        f"我也想起你之前记下的\"{past_content}\"。" if past_content else "我也记得你此前留下的那些心绪。"
    )

    memory_section = ""
    if memories:
        memory_section = f"\n\n从更早的随记里，我也看到这样的一些片段：\n{memories}"

    return (
        f"{prefix}\n\n{memory}那时的{past_emotion}，似乎还在和此刻轻轻相连。"
        "你已经走过了一些不容易的时刻，所以现在不必独自硬撑。"
        f"{memory_section}\n\n如果愿意，就再和我说说：此刻最让你放不下的，是哪一个瞬间？"
    )


def run_soul_chat(
    user_input: str,
    history_entries: list[Entry],
    chat_history: list[ChatMessage],
    layered_memory: str | None = None,
    anchor_entry: Entry | None = None,
) -> str:
    """Respond with warm companionship grounded in the user's journal memory."""
    validated_input = _require_text(user_input, "user_input")
    if not isinstance(history_entries, list):
        raise TypeError("history_entries must be a list")
    if not isinstance(chat_history, list):
        raise TypeError("chat_history must be a list")

    recent_entries = list(history_entries)[:MAX_RECENT_ENTRIES]
    retrieved_memory = _format_retrieved_memories(recent_entries)
    memory_section = _build_soul_memory_section(
        recent_entries, chat_history, layered_memory, retrieved_memory
    )
    anchor_note = ""
    if anchor_entry:
        anchor_note = (
            f"[{_safe_text(anchor_entry.get('created_at'), '时间未记录')}｜"
            f"{_safe_text(anchor_entry.get('emotion'), '未标注')}] "
            f"{_safe_text(anchor_entry.get('content'), '')[:MAX_ENTRY_CONTENT_CHARS]}"
        )
    system_prompt = _soul_system_prompt(memory_section, anchor_note)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_normalize_chat_history(chat_history))
    messages.append({"role": "user", "content": validated_input})
    response = _call_deepseek(messages, temperature=0.8)
    return response or _mock_soul_chat(validated_input, recent_entries, retrieved_memory)


def _emotion_distribution(entries: Sequence[Entry]) -> str:
    emotions = [
        emotion
        for entry in entries
        if (emotion := _safe_text(entry.get("emotion")).strip())
    ]
    if not emotions:
        return "60% 平静生长 · 40% 温柔探索"

    counts = Counter(emotions)
    top = counts.most_common(2)
    total = sum(count for _, count in top)
    if len(top) == 1:
        return f"100% {top[0][0]}"
    first_percent = round(top[0][1] / total * 10) * 10
    first_percent = min(90, max(50, first_percent))
    return f"{first_percent}% {top[0][0]} · {100 - first_percent}% {top[1][0]}"


def _mock_poet(user_name: str, entries: Sequence[Entry]) -> PoetResult:
    """Hardcoded poem + book quote for API-timeouts / missing keys."""
    em = "\u2014\u2014"  # —— em-dash pair
    MOCKS: list[PoetResult] = [
        {
            "title": "暗夜里的光",
            "poetry_content": "深夜调试，bug 纠缠\n但你没有放弃\n一盏台灯的光，足够温暖\n那些敲下的代码\n都将成为明天的序章",
            "quote": "在最深的黑暗中，我学会了最真实的光。",
            "quote_author": f"{em} 史铁生《我与地坛》",
            "emotion_dist": _emotion_distribution(entries),
        },
        {
            "title": "缓慢生长的力量",
            "poetry_content": "今天比昨天早起十分钟\n窗外的风，带着一点凉意\n你说你有点累\n但依然在走\n生活不是冲刺\n是每一步的叠加",
            "quote": "我们从不被允许走得太慢，却总被允许停下来。",
            "quote_author": f"{em} 黑塞《德米安》",
            "emotion_dist": _emotion_distribution(entries),
        },
        {
            "title": "周末的轻与重",
            "poetry_content": "周末的午后，一杯咖啡\n和一整页还没写的文档\n你说想躺平\n却又觉得不该\n于是你先躺了一会儿\n然后起来，继续",
            "quote": "重要的不是你现在是谁，而是你愿意成为谁。",
            "quote_author": f"{em} 稻盛和夫《活法》",
            "emotion_dist": _emotion_distribution(entries),
        },
    ]
    idx = len(entries) % len(MOCKS)
    chosen = dict(MOCKS[idx])
    chosen["emotion_dist"] = _emotion_distribution(entries)
    # Offline suggestions use a concrete detail from the demo journal.
    for entry in entries[:MAX_POET_ENTRIES]:
        text = entry.get("content", "")
        if "排练" in text:
            chosen["activity"] = "下次排练前，挑一件身边的小物件。试着用一句开场白，把它介绍给一位想象中的听众。"
            break
        if "公园" in text:
            chosen["activity"] = "下次路过公园时，停下来辨认三种远近不同的声音。哪一种平时最容易错过？"
            break
    return PoetResult(**chosen)


def _validate_poet(data: dict[str, Any] | None) -> PoetResult | None:
    if data is None:
        return None
    required_keys = ("title", "poetry_content", "quote", "quote_author", "emotion_dist")
    if any(not isinstance(data.get(k), str) or not data[k].strip() for k in required_keys):
        return None
    # Normalize poetry_content: collapse any sequence of newlines to a single \n
    poetry_content = data["poetry_content"].strip()
    poetry_content = "\n".join(
        line for line in poetry_content.splitlines() if line.strip()
    )
    return PoetResult(
        title=data["title"].strip(),
        poetry_content=poetry_content,
        quote=data["quote"].strip(),
        quote_author=data["quote_author"].strip(),
        emotion_dist=data["emotion_dist"].strip(),
        activity=(data["activity"].strip()[:240] or None) if isinstance(data.get("activity"), str) else None,
    )


def run_poet_agent(user_name: str, entries: list[Entry]) -> PoetResult:
    """Match a classic literary quote to the user's recent emotional journey."""
    if not isinstance(user_name, str):
        raise TypeError("user_name must be a string")
    if not isinstance(entries, list):
        raise TypeError("entries must be a list")

    entries_payload = [
        {
            "created_at": _safe_text(entry.get("created_at")),
            "content": _safe_text(entry.get("content"))[:MAX_ENTRY_CONTENT_CHARS],
            "emotion": _safe_text(entry.get("emotion")),
            "tags": entry.get("tags", []) if isinstance(entry.get("tags"), list) else [],
        }
        for entry in entries[:MAX_POET_ENTRIES]
    ]
    prompt = (
        f"请为用户 {user_name or '朋友'} 生成近期情绪诗篇，并从书籍中匹配一句金句。"
        "以下随记按新到旧排列，请只依据真实内容创作，并输出 JSON：\n"
        + json.dumps(entries_payload, ensure_ascii=False)
    )
    raw = _call_deepseek(
        [
            {"role": "system", "content": _POET_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        json_mode=True,
        temperature=0.85,
    )
    return _validate_poet(_parse_json_object(raw)) or _mock_poet(user_name, entries)


def index_memory(
    user_id: str,
    entry_id: int,
    content: str,
    metadata: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
) -> None:
    """Persist an entry's semantic memory so it can be retrieved later."""
    try:
        from embeddings import default_embedding_service
        from vector_store import get_vector_store
    except Exception as exc:
        LOGGER.warning("Vector memory components unavailable; skipping indexing: %s", exc)
        return

    if embedding is None:
        embedding = default_embedding_service().embed(content)
    if not embedding:
        return

    payload: dict[str, Any] = {
        "entry_id": entry_id,
        "user_id": user_id,
        "content": content,
        "metadata": dict(metadata or {}),
    }
    get_vector_store().upsert([payload], [embedding])


__all__ = [
    "PatternExtraction",
    "PatternResult",
    "PoetResult",
    "run_pattern_agent",
    "run_soul_chat",
    "run_soul_chat_stream",
    "run_poet_agent",
    "index_memory",
    "serialize_analysis",
]
