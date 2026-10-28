## Newsroom self-review, 2026-10-28

Looked at 35 runs over the last 3 days (59 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove GDELT source to stop frequent 429 errors  
  _Why:_ 20/35 runs failed with rate‑limit errors, causing many drops
- [ ] **remove source** · `gdelt-india`: Remove GDELT‑India source for same reason  
  _Why:_ 24/35 runs failed due to repeated rate‑limiting
- [ ] **fix source** · `arxiv`: Add a retry with increased timeout for arXiv queries  
  _Why:_ 2/35 runs timed out; a simple retry/back‑off can recover these
- [ ] **coverage gap** · `xAI`: Add a dedicated xAI news feed (e.g., blog/rss) to capture lab updates  
  _Why:_ xAI is tracked but produced no stories this week
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower minimum score from 6 to 5  
  _Why:_ Large numbers of drops at score 5; lowering threshold could increase usable stories without major quality loss

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 35,
 "stories_written": 59,
 "source_failures": {
  "arxiv": "2/35 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt": "20/35 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "24/35 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 161,
  "score 2": 94,
  "score 4": 87,
  "could not verify yet": 84,
  "score 3": 77,
  "not AI": 62,
  "could not verify yet after a second try": 25,
  "score 1": 23
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
