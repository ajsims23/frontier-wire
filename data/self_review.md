## Newsroom self-review, 2026-10-21

Looked at 9 runs over the last 3 days (19 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt`: Implement exponential backoff and cache recent queries to stay under rate limits  
  _Why:_ gdelt failed 5/9 runs with HTTP 429, causing loss of source data
- [ ] **add source** · `AI Lab Press Releases`: Add a generic RSS/press‑release source (e.g., https://pressrelease.ai/) to capture announcements from DeepMind, xAI, DeepSeek, Alibaba Qwen, Microsoft  
  _Why:_ Five tracked labs produced no stories this week, indicating a coverage gap
- [ ] **coverage gap** · `Google DeepMind`: Prioritize DeepMind publications by querying arXiv and DeepMind blog daily  
  _Why:_ DeepMind is a tracked lab with zero coverage
- [ ] **tune** · `score_thresholds`: Raise the minimum acceptable relevance score from 1 to 2 and lower the maximum acceptable score from 5 to 4  
  _Why:_ High drop counts at scores 1 and 5 suggest thresholds are too permissive or too strict
- [ ] **remove source** · `cerebras/gpt-oss-120b`: Replace this model with a stable alternative (e.g., openai/gpt-4o) since it repeatedly returns unusable answers  
  _Why:_ Provider notes show repeated unusable answers and 404 errors for cerebras models

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 9,
 "stories_written": 19,
 "source_failures": {
  "gdelt": "5/9 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 43,
  "score 1": 25,
  "score 4": 23,
  "score 2": 23,
  "score 3": 21,
  "could not verify with enough independent": 13,
  "duplicate of c3c47473c56f": 2,
  "duplicate of 820bd24a41c4": 1
 },
 "tracked_labs_without_stories_this_week": [
  "Google DeepMind",
  "xAI",
  "DeepSeek",
  "Alibaba (Qwen)",
  "Microsoft"
 ],
 "provider_notes": [
  "cerebras/gpt-oss-120b: unusable answer; trying next model",
  "cerebras/llama3.3-70b: model unavailable (404); trying next model",
  "cerebras/qwen-3-235b-a22b-instruct-2507: model unavailable (404); trying next model",
  "cerebras/gpt-oss-120b: unusable answer; trying next model",
  "cerebras/llama3.3-70b: model unavailable (404); trying next model",
  "cerebras/qwen-3-235b-a22b-instruct-2507: model unavailable (404); trying next model",
  "cerebras/gpt-oss-120b: unusable answer"
 ]
}
```

</details>
