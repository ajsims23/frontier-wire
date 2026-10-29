## Newsroom self-review, 2026-10-29

Looked at 41 runs over the last 3 days (68 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt from sources list  
  _Why:_ Rate-limited 17/41 runs causing frequent failures
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india from sources list  
  _Why:_ Rate-limited 20/41 runs causing frequent failures
- [ ] **add source** · `xAI lab`: Add a dedicated source for xAI lab updates  
  _Why:_ Lab tracked but no stories this week
- [ ] **add source** · `Mistral AI lab`: Add a dedicated source for Mistral AI lab updates  
  _Why:_ Lab tracked but no stories this week
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower to 5  
  _Why:_ Large number of stories dropped at score 5 (183) indicating threshold may be too high

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 41,
 "stories_written": 68,
 "source_failures": {
  "gdelt-india": "20/41 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "gdelt": "17/41 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 183,
  "not AI": 160,
  "score 4": 104,
  "could not verify yet": 95,
  "score 2": 69,
  "score 3": 58,
  "could not verify yet after a second try": 27,
  "score 1": 18
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "Mistral AI"
 ],
 "provider_notes": [
  "cerebras: 429 after retry; moving to next provider for this run",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq: 429 after retry; moving to next provider for this run",
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
