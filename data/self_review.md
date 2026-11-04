## Newsroom self-review, 2026-11-04

Looked at 33 runs over the last 3 days (65 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt source  
  _Why:_ Fails 16/33 runs with 429 rate‑limit errors, causing many missed stories.
- [ ] **remove source** · `gdelt-india`: Remove gdelt‑india source  
  _Why:_ Fails 19/33 runs due to GDELT pausing, heavily impacting coverage.
- [ ] **add source** · `meta-lab-news`: Add a dedicated source for Meta AI lab announcements  
  _Why:_ Meta lab has no stories this week despite being tracked.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower threshold to 5  
  _Why:_ Large numbers of drops at scores 5 and 4 (93 + 64), reducing missed potentially valuable stories.
- [ ] **tune** · `cerebras/gpt-oss-120b`: Reduce max output tokens or add a fallback model to avoid cut‑off answers  
  _Why:_ Provider notes show repeated answer cut‑offs, leading to unusable content.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 33,
 "stories_written": 65,
 "source_failures": {
  "gdelt-india": "19/33 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "gdelt": "16/33 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 179,
  "score 5": 93,
  "could not verify yet": 75,
  "score 4": 64,
  "could not verify yet after a second try": 35,
  "score 0": 18,
  "score 3": 17,
  "duplicate of c10fef6ec816": 14
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
  "cerebras/gpt-oss-120b: unusable answer"
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
