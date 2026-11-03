## Newsroom self-review, 2026-11-03

Looked at 28 runs over the last 3 days (46 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt-india`: Remove source to stop repeated failures  
  _Why:_ Failed 17/28 runs due to rate limiting
- [ ] **remove source** · `gdelt`: Remove source to stop repeated 429 errors  
  _Why:_ Failed 13/28 runs due to rate limiting
- [ ] **tune** · `min_score_to_publish_1_to_10`: lower to 5  
  _Why:_ Many stories dropped for scores 5-4; lowering will increase publishable content
- [ ] **coverage gap** · `Meta`: Add dedicated Meta AI news source  
  _Why:_ Meta lab tracked but no stories this week
- [ ] **add source** · `ai.googleblog`: Add source for Google's AI blog  
  _Why:_ Broaden AI news coverage; url left empty as placeholder.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 28,
 "stories_written": 46,
 "source_failures": {
  "gdelt-india": "17/28 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "gdelt": "13/28 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 131,
  "could not verify yet": 43,
  "score 5": 42,
  "score 4": 36,
  "could not verify yet after a second try": 23,
  "duplicate of c10fef6ec816": 20,
  "score 3": 10,
  "duplicate of b329cc4aaa4c": 10
 },
 "tracked_labs_without_stories_this_week": [
  "Meta"
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
