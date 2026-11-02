## Newsroom self-review, 2026-11-02

Looked at 29 runs over the last 3 days (52 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt source due to repeated 429 errors  
  _Why:_ 14/29 runs failed with rate‑limit, causing frequent interruptions
- [ ] **remove source** · `gdelt-india`: Remove gdelt‑india source due to rate‑limiting pauses  
  _Why:_ 17/29 runs failed, blocking data collection
- [ ] **add source** · `xai`: Add a dedicated xAI news source to capture lab updates  
  _Why:_ xAI lab has no stories this week, indicating a coverage gap
- [ ] **tune** · `source_query_filter`: Add AI‑specific keyword filter (e.g., "AI", "artificial intelligence") to source queries  
  _Why:_ 135 drops labelled "not AI" show the current queries pull many irrelevant items
- [ ] **tune** · `min_score_to_publish_1_to_10`: Raise minimum score to 7  
  _Why:_ Many stories are dropped at scores 5‑6; a higher threshold will improve overall story quality

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 29,
 "stories_written": 52,
 "source_failures": {
  "gdelt": "14/29 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "17/29 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 135,
  "score 5": 64,
  "score 4": 48,
  "could not verify yet": 41,
  "duplicate of c10fef6ec816": 20,
  "could not verify yet after a second try": 19,
  "score 3": 11,
  "duplicate of b329cc4aaa4c": 10
 },
 "tracked_labs_without_stories_this_week": [
  "xAI"
 ],
 "provider_notes": [
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: unusable answer",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room"
 ],
 "current_settings": {
  "min_score_to_publish_1_to_10": 6,
  "max_stories_per_run": 10,
  "ai_providers_configured": [
   "cerebras",
   "groq"
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
