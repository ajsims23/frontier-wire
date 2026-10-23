## Newsroom self-review, 2026-10-23

Looked at 27 runs over the last 3 days (54 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt due to frequent 429 errors; replace with an alternative free news source.  
  _Why:_ 14/27 runs failed with HTTP 429 Too Many Requests.
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india because it also hits rate limits.  
  _Why:_ 12/27 runs failed with HTTP 429 Too Many Requests.
- [ ] **fix source** · `arxiv`: Increase read timeout or add retry logic for arxiv queries to avoid occasional timeouts.  
  _Why:_ 2/27 runs timed out, missing potential papers.
- [ ] **coverage gap** · `xAI`: Add a dedicated free source for xAI lab updates (e.g., xAI blog) to capture stories.  
  _Why:_ Lab is tracked but produced no stories this week.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower the minimum score to 5 to reduce drops at score 5 and increase story output.  
  _Why:_ 151 stories dropped at score 5; threshold may be too high.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 27,
 "stories_written": 54,
 "source_failures": {
  "gdelt": "14/27 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "arxiv": "2/27 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt-india": "12/27 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 151,
  "score 2": 102,
  "score 4": 65,
  "score 3": 56,
  "score 1": 41,
  "could not verify yet": 30,
  "could not verify with enough independent": 13,
  "could not verify yet after a second try": 12
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
