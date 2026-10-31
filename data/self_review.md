## Newsroom self-review, 2026-10-31

Looked at 41 runs over the last 3 days (79 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt source due to frequent 429 errors  
  _Why:_ 16/41 runs failed, causing delays
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india source  
  _Why:_ 17/41 runs failed, rate limiting
- [ ] **add source** · `xAI`: Add a dedicated XAI news source to capture lab updates  
  _Why:_ xAI lab has no stories this week
- [ ] **tune** · `min_score_to_publish_1_to_10`: Increase to 7  
  _Why:_ Many drops due to low scores (5,4,3) reducing content quality
- [ ] **tune** · `max_stories_per_run`: Reduce to 8  
  _Why:_ Current max 10 may strain processing and cause provider cut-offs

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 41,
 "stories_written": 79,
 "source_failures": {
  "gdelt": "16/41 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "17/41 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "arxiv": "3/41 runs; last error: failed: ReadTimeout: The read operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 259,
  "score 5": 134,
  "score 4": 123,
  "could not verify yet": 83,
  "could not verify yet after a second try": 24,
  "score 3": 21,
  "variety": 14,
  "duplicate of 007a2afe4a6c": 11
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
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
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
