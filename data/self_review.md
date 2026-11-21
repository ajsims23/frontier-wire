## Newsroom self-review, 2026-11-21

Looked at 38 runs over the last 3 days (102 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 5 to 4 to capture viable stories currently being dropped.  
  _Why:_ A large number of stories are being dropped at score 4 (185 items) and score 3 (91 items) while the minimum publishing score is set to 5. Lowering min_score_to_publish_1_to_10 to 4 would safely capture more relevant content without overwhelming output.
- [ ] **fix source** · `gdelt, gdelt-india`: Increase connection timeout limits or add retry logic for GDELT and gdelt-india sources to mitigate SSL handshake timeouts.  
  _Why:_ Both GDELT sources are experiencing connection timeouts in ~13% of runs (5 out of 38 runs), indicating potential instability or network timeout limits that need adjustment.
- [ ] **coverage gap** · `sources`: Add DeepSeek to the monitored sources list to ensure it receives adequate coverage alongside other labs.  
  _Why:_ xAI and DeepSeek have tracked labs without stories this week despite having xAI configured as a source. Adding dedicated RSS or news tracking sources for DeepSeek can help bridge this coverage gap.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 38,
 "stories_written": 102,
 "source_failures": {
  "gdelt": "5/38 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "5/38 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 209,
  "score 4": 185,
  "score 5": 109,
  "score 3": 91,
  "could not verify yet": 53,
  "variety": 23,
  "duplicate of 25c96fa5a216": 23,
  "score 2": 20
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek"
 ],
 "provider_notes": [
  "gemini/gemini-flash-lite-latest: per-minute limit hit; trying next model",
  "gemini: network error ReadTimeout, retrying",
  "gemini: unreachable (ReadTimeout); skipping provider",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini: network error ReadTimeout, retrying",
  "gemini/gemini-flash-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model"
 ],
 "current_settings": {
  "min_score_to_publish_1_to_10": 5,
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
   "mistral-news",
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
