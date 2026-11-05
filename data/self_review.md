## Newsroom self-review, 2026-11-05

Looked at 36 runs over the last 3 days (70 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt from sources list  
  _Why:_ Failed in 17 of 36 runs due to SSL timeout, causing unreliable data ingestion
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india from sources list  
  _Why:_ Failed in 18 of 36 runs with the same SSL timeout, wasting run time
- [ ] **add source** · `meta-ai-blog`: Add a dedicated Meta AI news source  
  _Why:_ Meta lab had no stories this week despite being tracked, indicating coverage gap
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower threshold from 6 to 5  
  _Why:_ Large numbers of stories are dropped at score 5 (186) and 4 (125); lowering may capture more relevant content without sacrificing quality
- [ ] **tune** · `cerebras/gpt-oss-120b`: Increase max token limit or shorten prompts for this model  
  _Why:_ Repeated 'answer cut off' notes indicate token limit is being hit, reducing output quality

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 36,
 "stories_written": 70,
 "source_failures": {
  "gdelt": "17/36 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "18/36 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 217,
  "score 5": 186,
  "score 4": 125,
  "could not verify yet": 105,
  "could not verify yet after a second try": 42,
  "score 3": 21,
  "score 0": 18,
  "duplicate of e420e884477a": 18
 },
 "tracked_labs_without_stories_this_week": [
  "Meta"
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
