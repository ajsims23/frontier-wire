"""Which quotes are worth showing.

Two levels:
  - `is_real_quote`: is this actually a named person's own words? Used when a story is written, so a reporter's
    paraphrase ("Huang said on Sunday that…"), a company press line or a scrap like "has got to go" never gets
    stored as a quote at all.
  - `pick_voices`: the homepage strip. From all the real quotes on the front page, pick the few that say
    something about AI (an argument, a prediction, a worry, a result), one per person and one per story thread,
    so a single scandal or a single CEO can't fill the strip.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# speakers that are organisations, documents or unnamed groups, not people
_NOT_A_PERSON_ROLE = re.compile(
    r"\b(company|companies|spokes(?:person|man|woman)|report|analysts|lawyers|attorneys|counsel|plaintiff|"
    r"announcement|blog|press release|statement|researchers|firm|outlet|filing)\b", re.I)
_NOT_A_PERSON_NAME = re.compile(
    r"\b(spokes(?:person|man|woman)|person familiar|people familiar|report|analysts|researchers|attorneys|lawyers|"
    r"official|officials|source|sources|times|journal|research|inc|ltd|corp|llc)\b|/| and ", re.I)
_KNOWN_ORGS = {"openai", "anthropic", "google", "google deepmind", "deepmind", "meta", "apple", "microsoft", "nvidia",
               "amazon", "aws", "xai", "mistral", "sarvam ai", "the new york times", "jefferies report"}

# a reporter describing the speech rather than the speaker's words
_REPORTED = re.compile(r"\b(said|says|told|according to|tweeted|wrote)\b|[”\"],?\s+[A-Z][a-z]+ (said|told|says)", re.I)

# personal life and scandal: newsworthy, but not "what AI's leading people think"
_PERSONAL = re.compile(
    r"\b(unfaithful|affair|my wife|my husband|divorce|my family|our children|my children|apolog(?:y|ise|ize)|"
    r"girlfriend|boyfriend|subpoena\w*|indict\w*|arrest\w*|investigation|cooperate fully|fine person|"
    r"talking to me directly)\b", re.I)

# press-release filler
_PR = re.compile(
    r"\b(we are (?:very )?(?:excited|pleased|proud|thrilled|delighted)|excited to|pleased to|proud to|thrilled to|"
    r"delighted to|joining forces|brings together|positioned to lead|our clients|our customers|second quarter|"
    r"we respectfully|best-in-class|world-class|seamless(?:ly)?)\b", re.I)

# signs of an actual view: a claim, a prediction, a worry, a judgement
_OPINION = re.compile(
    r"\b(i think|i believe|i don.t think|we think|we believe|will|won.t|should|need to|needs to|must|worry|risk|"
    r"future|never|nobody|no one|every|most|hard to|can.t|cannot|existential|threshold|bubble|peaked|"
    r"transform\w*|replace|jobs?|safety|crosses|gap)\b", re.I)


def tidy(text: str) -> str:
    """Trim quote marks, a spoken "You know," opener and a dangling comma left by cutting mid-sentence."""
    t = (text or "").strip().strip('"“”').strip()
    t = re.sub(r"^(?:you know|so|well|look),\s+", "", t, flags=re.I)
    t = re.sub(r"[,;:]+$", "", t).strip()
    return t[:1].upper() + t[1:] if t else t


def _words(text: str) -> int:
    return len(re.findall(r"[\w’']+", text))


def is_person(speaker: str, role: str = "") -> bool:
    s = (speaker or "").strip()
    if not s or len(s.split()) > 5 or s.lower() in _KNOWN_ORGS:
        return False
    if _NOT_A_PERSON_NAME.search(s) or _NOT_A_PERSON_ROLE.search(role or ""):
        return False
    return any(c.isupper() for c in s[:1])


def is_real_quote(text: str, speaker: str, role: str = "") -> bool:
    """The speaker's own words, a full thought, attributed to a named person."""
    t = (text or "").strip().strip('"“”')
    if not t or not is_person(speaker, role):
        return False
    if (t.count("“") != t.count("”")) or t.count('"') % 2:
        return False  # cut mid-quote, e.g. a “steep road.
    if _words(t) < 6 or not (t[0].isupper() or t[0].isdigit() or t[0] in "‘'"):
        return False  # a scrap or mid-sentence fragment ("has got to go", "about a 50-50")
    surname = speaker.split()[-1]
    if len(surname) > 2 and re.search(rf"\b{re.escape(surname)}\b", t):
        return False  # "Huang said…" is the reporter talking about the speaker
    return not _REPORTED.search(t)


def score(q: dict[str, Any], story: dict[str, Any], now: datetime) -> float:
    t = q["text"]
    s = float(story.get("score") or 5)
    if story.get("ai_relevance") == "adjacent":
        s -= 4
    if story.get("category") in ("voices", "research", "safety", "models"):
        s += 1
    if _OPINION.search(t):
        s += 2
    if _PR.search(t):
        s -= 4
    n = _words(t)
    if n < 10:
        s -= 1
    elif n <= 35:
        s += 1
    try:
        age_days = (now - datetime.fromisoformat(story["published_at"])).total_seconds() / 86400
    except (KeyError, ValueError, TypeError):
        age_days = 7
    return s - max(0.0, age_days) * 0.6  # a strong quote from a few days ago can beat a weak one from today


def pick_voices(stories: list[dict[str, Any]], now: datetime, limit: int = 6) -> list[dict[str, Any]]:
    """The homepage's quotes: the best real quotes, one per person and one per story thread."""
    ranked = []
    for s in stories:
        for q in s.get("quotes") or []:
            raw = (q.get("text") or "").strip().strip('"“”').strip()
            text = tidy(raw)
            if not is_real_quote(re.sub(r"^(?:you know|so|well|look),\s+", "", raw, flags=re.I),
                                 q.get("speaker", ""), q.get("speaker_role", "")):
                continue
            if _PERSONAL.search(text) or _words(text) > 45:
                continue
            ranked.append((score(q, s, now), q, s))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out, speakers, threads = [], set(), set()
    for _, q, s in ranked:
        who = q["speaker"].strip().lower()
        thread = s.get("thread") or s["id"]
        if who in speakers or thread in threads:
            continue
        speakers.add(who)
        threads.add(thread)
        out.append({**q, "text": tidy(q["text"]), "story_id": s["id"], "headline": s["headline"],
                    "published_at": s["published_at"]})
        if len(out) >= limit:
            break
    return out
