## Newsroom self-review, 2026-11-01

Looked at 35 runs over the last 3 days (63 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `arxiv`: Add a longer read timeout and retry logic for arxiv queries  
  _Why:_ 3 of 35 runs timed out, causing missed papers
- [ ] **remove source** · `gdelt`: Temporarily disable gdelt source and replace with a free alternative like newsapi.org to avoid 429 rate limits _(contains an address suggested by the agent; check it before using)_  
  _Why:_ 14 of 35 runs hit 429 Too Many Requests
- [ ] **remove source** · `gdelt-india`: Disable gdelt-india source and replace with a free alternative (e.g., Reddit AI subreddit) to avoid repeated rate‑limiting pauses  
  _Why:_ 17 of 35 runs paused due to rate‑limiting
- [ ] **add source** · `xAI blog`: Add a simple RSS/HTML scraper for the official xAI blog to capture lab announcements  
  _Why:_ xAI lab had no stories this week despite being tracked
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower the minimum score from 6 to 5  
  _Why:_ 95 stories dropped at score 5; lowering the threshold would increase published content without major quality loss

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 35,
 "stories_written": 63,
 "source_failures": {
  "arxiv": "3/35 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt": "14/35 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "17/35 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 199,
  "score 5": 95,
  "score 4": 74,
  "could not verify yet": 65,
  "could not verify yet after a second try": 21,
  "score 3": 14,
  "variety": 10,
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
