## Newsroom self-review, 2026-11-07

Looked at 45 runs over the last 3 days (65 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt`: Check network/timeout configuration for the GDELT source.  
  _Why:_ GDELT is experiencing frequent connection timeouts (19/45 runs failing).
- [ ] **fix source** · `gdelt-india`: Increase request intervals or reduce polling frequency for gdelt-india to avoid rate limits.  
  _Why:_ GDELT-India is frequently hitting rate-limiting errors (20/45 runs failing).
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to capture these borderline stories given free resource constraints.  
  _Why:_ A large volume of stories (187 scored 5, 169 scored 4) are being dropped just below the current publish threshold of 6.
- [ ] **tune** · `ai_providers_configured`: Stagger requests or add a small delay between calls to free AI providers to prevent rate-limit hits.  
  _Why:_ Frequent per-minute rate limits are hitting Groq and Gemini models, causing fallbacks and retries.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 45,
 "stories_written": 65,
 "source_failures": {
  "gdelt": "19/45 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "20/45 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 187,
  "score 4": 169,
  "not AI": 167,
  "could not verify yet": 68,
  "score 3": 36,
  "could not verify yet after a second try": 26,
  "variety": 24,
  "duplicate of e420e884477a": 18
 },
 "tracked_labs_without_stories_this_week": [],
 "provider_notes": [
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: per-minute limit hit; trying next model",
  "gemini: network error ReadTimeout, retrying",
  "gemini: unreachable (ReadTimeout); skipping provider",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
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
