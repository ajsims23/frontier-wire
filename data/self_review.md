## Newsroom self-review, 2026-11-18

Looked at 32 runs over the last 3 days (101 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `gdelt`: Increase request intervals or backoff periods for GDELT and gdelt-india to reduce rate-limiting errors.  
  _Why:_ GDELT sources are frequently hitting 429 Too Many Requests errors across almost half of the runs.
- [ ] **coverage gap** · `Mistral AI`: Add or verify dedicated RSS or news sources for Mistral AI to improve lab coverage.  
  _Why:_ Mistral AI had no stories written this week, indicating a potential gap in tracking their releases.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to increase story throughput without relying on paid models.  
  _Why:_ A large volume of stories (176 total across scores 3-5) are being dropped just below the publishing threshold.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 32,
 "stories_written": 101,
 "source_failures": {
  "gdelt": "12/32 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "15/32 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "arxiv": "3/32 runs; last error: failed: HTTPStatusError: Client error '429 Unknown Error' for url 'https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 149,
  "score 4": 119,
  "score 5": 57,
  "could not verify yet": 50,
  "score 3": 47,
  "variety": 20,
  "could not verify yet after a second try": 10,
  "duplicate of 369f1ffcda11": 10
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI"
 ],
 "provider_notes": [
  "groq/qwen/qwen3.8-27b: HTTP 400: {\"error\":{\"message\":\"Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details.\",\"type\":\"invalid_request_error\",\"",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/qwen/qwen3.8-27b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-latest: 503 (server busy); trying next model"
 ],
 "current_settings": {
  "min_score_to_publish_1_to_10": 6,
  "max_stories_per_run": 10,
  "ai_providers_configured": [
   "gemini",
   "groq",
   "nvidia",
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
