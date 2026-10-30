## Newsroom self-review, 2026-10-30

Looked at 41 runs over the last 3 days (71 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove GDELT source due to frequent 429 rate‑limit errors (15/41 runs)  
  _Why:_ High failure rate limits story collection
- [ ] **remove source** · `gdelt-india`: Remove GDELT‑India source because it hits runtime rate‑limit errors in 18/41 runs  
  _Why:_ Frequent pauses prevent timely data
- [ ] **add source** · `xAI_blog`: Add a dedicated xAI blog source to capture updates from the tracked lab  
  _Why:_ xAI has no stories this week despite being tracked
- [ ] **add source** · `ai_googleblog`: Add Google AI Blog (ai.googleblog.com) as a free source for AI research news _(contains an address suggested by the agent; check it before using)_  
  _Why:_ Broadens coverage with a reliable free source
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower minimum score to 5  
  _Why:_ Many potential stories are dropped at score 5; lowering threshold could increase useful output without sacrificing quality

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 41,
 "stories_written": 71,
 "source_failures": {
  "arxiv": "3/41 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt-india": "18/41 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "gdelt": "15/41 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 252,
  "score 5": 161,
  "score 4": 104,
  "could not verify yet": 101,
  "score 3": 39,
  "score 2": 30,
  "could not verify yet after a second try": 28,
  "variety": 18
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
