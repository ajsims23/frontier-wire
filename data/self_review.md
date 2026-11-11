## Newsroom self-review, 2026-11-11

Looked at 39 runs over the last 3 days (99 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `gdelt`: Reduce the polling frequency or batch size for GDELT and gdelt-india sources to avoid HTTP 429 rate-limiting errors.  
  _Why:_ GDELT and GDELT-india are hitting severe rate-limiting (failing in over half of the runs), indicating query frequency or volume is too high.
- [ ] **fix source** · `aim`: Check the endpoint availability or temporarily disable the aim feed until the server recovers. https://analyticsindiamag.com/feed  
  _Why:_ Analytics India Magazine (aim) is experiencing 503 Service Unavailable errors.
- [ ] **coverage gap** · `Alibaba (Qwen)`: Add a dedicated RSS feed or search query source for Alibaba Qwen announcements to improve lab coverage.  
  _Why:_ Alibaba (Qwen) produced zero stories this week, despite being a tracked lab.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to capture borderline quality stories and increase output volume.  
  _Why:_ A large volume of candidate stories (116 scored 4, and 53 scored 5) are falling just short of the minimum publication threshold of 6.
- [ ] **fix source** · `arxiv`: Implement a longer backoff delay between requests to arXiv to prevent 429 Too Many Requests errors. https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C  
  _Why:_ Arxiv is experiencing HTTP 429 Client errors due to rate limits on export.arxiv.org.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 39,
 "stories_written": 99,
 "source_failures": {
  "gdelt-india": "21/39 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "arxiv": "2/39 runs; last error: failed: HTTPStatusError: Client error '429 Unknown Error' for url 'https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C",
  "gdelt": "17/39 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "aim": "5/39 runs; last error: failed: HTTPStatusError: Server error '503 Service Unavailable' for url 'https://analyticsindiamag.com/feed'\nFor more information check: htt"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 131,
  "score 4": 116,
  "score 5": 53,
  "score 3": 48,
  "could not verify yet": 31,
  "duplicate of b9e9a9b1a38a": 29,
  "duplicate of 88cba1275d52": 29,
  "duplicate of b10abbc74a23": 14
 },
 "tracked_labs_without_stories_this_week": [
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-20b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-20b: HTTP 400: {\"error\":{\"message\":\"Failed to parse tool call arguments as JSON\",\"type\":\"invalid_request_error\",\"code\":\"tool_use_failed\",\"failed_generation\":\"{\\\"name",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia: network error ReadTimeout, retrying",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/qwen/qwen3.8-27b: per-minute limit hit; trying next model"
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
