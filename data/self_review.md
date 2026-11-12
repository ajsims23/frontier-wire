## Newsroom self-review, 2026-11-12

Looked at 47 runs over the last 3 days (117 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt-india`: Investigate network or timeout settings for gdelt-india.  
  _Why:_ Frequent SSL handshake timeouts in nearly half of the runs (20/47).
- [ ] **fix source** · `gdelt`: Investigate network or timeout settings for gdelt.  
  _Why:_ Experiencing frequent SSL handshake timeouts (16/47 runs).
- [ ] **tune** · `Alibaba (Qwen)`: Check tracking keywords or source feeds for Alibaba (Qwen) to ensure coverage.  
  _Why:_ Alibaba (Qwen) had no stories covered this week while India and general GDELT sources have timeout issues.
- [ ] **tune** · `cerebras`: Remove Cerebras from ai_providers_configured since the site runs entirely on free services.  
  _Why:_ Cerebras is failing with 402 payment required (free quota exhausted).

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 47,
 "stories_written": 117,
 "source_failures": {
  "gdelt-india": "20/47 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt": "16/47 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 189,
  "score 4": 180,
  "score 5": 89,
  "score 3": 74,
  "could not verify yet": 45,
  "duplicate of 88cba1275d52": 32,
  "duplicate of b9e9a9b1a38a": 27,
  "variety": 21
 },
 "tracked_labs_without_stories_this_week": [
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "nvidia: unreachable (ReadTimeout); skipping provider",
  "cerebras: payment required (402) \u2014 free quota used up or billing needed; skipping provider",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini: network error ReadTimeout, retrying",
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
