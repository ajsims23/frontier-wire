## Newsroom self-review, 2026-11-09

Looked at 33 runs over the last 3 days (72 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt from the source list.  
  _Why:_ gdelt hits HTTP 429 on most runs (18/33) causing frequent data loss.
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india and replace with a more reliable Indian AI news source.  
  _Why:_ gdelt-india is rate‑limited on 23/33 runs, leaving Indian AI coverage sparse.
- [ ] **fix source** · `aim`: Add retry with exponential back‑off or switch to an alternative feed like analyticsindiamag.com RSS.  
  _Why:_ aim fails with 503 errors (5/33 runs), reducing story pool.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to increase usable content.  
  _Why:_ Many stories are dropped for low scores (score 5: 59 drops, score 4: 88 drops) while the threshold is 6.
- [ ] **add source** · `indian-ai-news`: Add a dedicated Indian AI news source.  
  _Why:_ After removing gdelt‑india, Indian AI coverage will be thin.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 33,
 "stories_written": 72,
 "source_failures": {
  "gdelt": "18/33 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "23/33 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "aim": "5/33 runs; last error: failed: HTTPStatusError: Server error '503 Service Unavailable' for url 'https://analyticsindiamag.com/feed'\nFor more information check: htt"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 114,
  "score 4": 88,
  "score 5": 59,
  "score 3": 40,
  "could not verify yet": 28,
  "variety": 19,
  "could not verify yet after a second try": 9,
  "duplicate of acdb0c16a39e": 8
 },
 "tracked_labs_without_stories_this_week": [],
 "provider_notes": [
  "gemini: network error ReadTimeout, retrying",
  "gemini: unreachable (ReadTimeout); skipping provider",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: answer cut off; retrying with more room",
  "gemini/gemini-flash-lite-latest: per-minute limit hit; trying next model"
 ],
 "current_settings": {
  "min_score_to_publish_1_to_10": 6,
  "max_stories_per_run": 10,
  "ai_providers_configured": [
   "gemini",
   "groq",
   "nvidia",
   "cerebras"
  ],
  "sources": [
   "openai",
   "deepmind",
   "google-ai",
   "huggingface",
   "nvidia",
   "anthropic",
   "meta-ai",
   "xai",
   "microsoft-ai",
   "mistral",
   "hf-models",
   "arxiv",
   "hf-papers",
   "gdelt",
   "hn",
   "techcrunch-ai",
   "verge-ai",
   "mit-tr-ai",
   "ars-ai",
   "aim",
   "inc42",
   "medianama",
   "mint-tech",
   "et-tech",
   "yourstory",
   "gdelt-india",
   "crunchbase-news",
   "import-ai",
   "simon-willison",
   "sam-altman",
   "bluesky"
  ]
 }
}
```

</details>
