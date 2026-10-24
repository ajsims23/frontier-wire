## Newsroom self-review, 2026-10-24

Looked at 43 runs over the last 3 days (81 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt source due to 53% failure rate  
  _Why:_ Frequent ConnectTimeout and 429 errors causing many runs to miss data.
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india source  
  _Why:_ 21/43 failures with 429 Too Many Requests, high unreliability.
- [ ] **add source** · `xAI lab blog`: Add a dedicated XAI lab source to capture their announcements  
  _Why:_ Tracked lab xAI produced no stories this week.
- [ ] **coverage gap** · `Alibaba (Qwen)`: Add a source for Alibaba Qwen lab updates  
  _Why:_ Lab tracked but no stories; under-covered.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower to 5  
  _Why:_ Score 5 drops are the largest category (208); lowering will increase publishable stories without major quality loss.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 43,
 "stories_written": 81,
 "source_failures": {
  "gdelt": "23/43 runs; last error: failed: ConnectTimeout: _ssl.c:993: The handshake operation timed out",
  "arxiv": "3/43 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt-india": "21/43 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 208,
  "score 2": 164,
  "score 4": 109,
  "score 3": 82,
  "score 1": 56,
  "could not verify yet": 49,
  "could not verify yet after a second try": 16,
  "variety": 16
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras: 429 after retry; moving to next provider for this run",
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
