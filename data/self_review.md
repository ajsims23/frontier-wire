## Newsroom self-review, 2026-10-25

Looked at 41 runs over the last 3 days (71 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: disable gdelt until rate limit resolves  
  _Why:_ 24/41 runs failing with 429 Too Many Requests, causing many drops
- [ ] **remove source** · `gdelt-india`: disable gdelt-india  
  _Why:_ 28/41 runs failing with runtime error due to repeated rate‑limiting
- [ ] **add source** · `xAI blog`: add source for xAI lab updates  
  _Why:_ tracked lab xAI has no stories this week
- [ ] **add source** · `Alibaba research blog`: add source for Qwen lab updates  
  _Why:_ tracked lab Alibaba (Qwen) has no stories this week
- [ ] **tune** · `min_score_to_publish_1_to_10`: lower to 5  
  _Why:_ many drops due to low scores (1‑5); lowering threshold may increase story count while maintaining quality

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 41,
 "stories_written": 71,
 "source_failures": {
  "gdelt": "24/41 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "arxiv": "4/41 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt-india": "28/41 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 195,
  "score 2": 164,
  "score 4": 103,
  "score 3": 72,
  "could not verify yet": 61,
  "score 1": 35,
  "could not verify yet after a second try": 19,
  "variety": 18
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras: 429 after retry; moving to next provider for this run",
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
