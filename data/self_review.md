## Newsroom self-review, 2026-11-10

Looked at 32 runs over the last 3 days (82 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt-india`: Remove gdelt-india from the source list.  
  _Why:_ gdelt-india fails in 21 out of 32 runs (handshake timeout), causing frequent gaps.
- [ ] **remove source** · `gdelt`: Remove gdelt from the source list.  
  _Why:_ gdelt fails in 13 out of 32 runs with the same timeout issue, wasting run time.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Set min_score_to_publish_1_to_10 from 6 to 5.  
  _Why:_ Many stories are dropped for scores 4‑5 (68+28 drops). Lowering the threshold can increase usable content without sacrificing much quality.
- [ ] **add source** · `arxiv`: Add an alternative arXiv source (e.g., OAI‑PMH endpoint).  
  _Why:_ arXiv occasionally hits rate‑limit (429). Adding a secondary arXiv feed reduces reliance on a single endpoint.
- [ ] **fix source** · `aim`: Add retry logic with exponential backoff or switch to a cached RSS feed for aim.  
  _Why:_ aim (Analytics India Magazine) returned 503 errors 5 times, indicating intermittent availability.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 32,
 "stories_written": 82,
 "source_failures": {
  "gdelt-india": "21/32 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt": "13/32 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "arxiv": "2/32 runs; last error: failed: HTTPStatusError: Client error '429 Unknown Error' for url 'https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C",
  "aim": "5/32 runs; last error: failed: HTTPStatusError: Server error '503 Service Unavailable' for url 'https://analyticsindiamag.com/feed'\nFor more information check: htt"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 89,
  "score 4": 68,
  "score 3": 39,
  "score 5": 28,
  "could not verify yet": 21,
  "duplicate of b9e9a9b1a38a": 21,
  "duplicate of b10abbc74a23": 13,
  "duplicate of 4756aa2fa657": 10
 },
 "tracked_labs_without_stories_this_week": [],
 "provider_notes": [
  "groq/qwen/qwen3.8-27b: couldn't force a tool call; retrying without forcing",
  "groq/qwen/qwen3.8-27b: HTTP 400: {\"error\":{\"message\":\"Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details.\",\"type\":\"invalid_request_error\",\"",
  "groq/openai/gpt-oss-20b: model unavailable (400); trying next model",
  "nvidia: network error ReadTimeout, retrying",
  "nvidia: unreachable (ReadTimeout); skipping provider",
  "cerebras: payment required (402) \u2014 free quota used up or billing needed; skipping provider",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model"
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
