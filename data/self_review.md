## Newsroom self-review, 2026-10-27

Looked at 33 runs over the last 3 days (50 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt from sources list  
  _Why:_ Rate‑limited on 21/33 runs, causing frequent 429 errors and no content
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india from sources list  
  _Why:_ Paused after repeated rate‑limiting on 25/33 runs, blocking news intake
- [ ] **add source** · `xAI`: Add a dedicated XAI news source (e.g., XAI blog / press releases)  
  _Why:_ Tracked lab xAI has no stories this week
- [ ] **add source** · `Alibaba (Qwen)`: Add a source for Alibaba Qwen research updates (e.g., Alibaba research blog)  
  _Why:_ Tracked lab Alibaba (Qwen) has no stories this week
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower threshold from 6 to 5  
  _Why:_ Large number of drops due to score 5 (131) – lowering could increase publishable stories without sacrificing quality

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 33,
 "stories_written": 50,
 "source_failures": {
  "gdelt": "21/33 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "25/33 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "arxiv": "2/33 runs; last error: failed: ReadTimeout: The read operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 131,
  "score 4": 95,
  "score 2": 90,
  "could not verify yet": 66,
  "score 3": 65,
  "score 1": 28,
  "could not verify yet after a second try": 17,
  "duplicate of 3f492a65e9c2": 17
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "Alibaba (Qwen)"
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
