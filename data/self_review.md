## Newsroom self-review, 2026-11-14

Looked at 47 runs over the last 3 days (120 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt-india`: Add request rate limiting or backoff for GDELT API calls to avoid 429 Too Many Requests errors.  
  _Why:_ GDELT API is returning 429 Too Many Requests errors frequently (23/47 runs for gdelt-india, 11/47 for gdelt). Request rate or query frequency should be reduced.
- [ ] **coverage gap** · `Mistral AI`: Check source configurations or queries for Mistral AI and Alibaba (Qwen) to ensure their recent developments are being captured.  
  _Why:_ Mistral AI and Alibaba (Qwen) have tracked labs with zero stories this week, indicating an under-coverage gap.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to allow more borderline quality stories to be published.  
  _Why:_ A high volume of stories (182) are being dropped with a score of 4, just below the publishing threshold of 6.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 47,
 "stories_written": 120,
 "source_failures": {
  "gdelt-india": "23/47 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt": "11/47 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "sam-altman": "2/47 runs; last error: failed: ReadTimeout: The read operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 210,
  "score 4": 182,
  "score 3": 95,
  "score 5": 95,
  "could not verify yet": 61,
  "variety": 20,
  "could not verify yet after a second try": 18,
  "duplicate of efdd0bfa6110": 16
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "gemini/gemini-flash-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini: unreachable (ReadTimeout); skipping provider",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/qwen/qwen3.8-27b: couldn't force a tool call; retrying without forcing",
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
