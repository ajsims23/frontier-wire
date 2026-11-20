## Newsroom self-review, 2026-11-20

Looked at 43 runs over the last 3 days (110 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 5 to 4 to increase the volume of published stories.  
  _Why:_ A significant number of stories (202) are being dropped with a score of 4, just below the publishing threshold of 5. Lowering the threshold to 4 will allow more high-quality stories to be published without compromising standards.
- [ ] **coverage gap** · `gdelt`: Investigate network timeouts for GDELT and GDELT-India sources to ensure news regarding labs like xAI and DeepSeek is not being missed.  
  _Why:_ xAI and DeepSeek have tracked labs without stories this week, while the GDELT sources are experiencing high connection timeout failure rates (up to 30% of runs).
- [ ] **fix source** · `gdelt-india`: Check the connection timeout settings or endpoint stability for the gdelt-india source.  
  _Why:_ gdelt-india is failing nearly 30% of the time (13/43 runs) due to SSL handshake timeouts.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 43,
 "stories_written": 110,
 "source_failures": {
  "gdelt": "10/43 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "13/43 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 217,
  "score 4": 202,
  "score 5": 119,
  "score 3": 109,
  "could not verify yet": 68,
  "variety": 23,
  "duplicate of 25c96fa5a216": 23,
  "score 2": 18
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek"
 ],
 "provider_notes": [
  "groq/qwen/qwen3.8-27b: couldn't force a tool call; retrying without forcing",
  "groq/qwen/qwen3.8-27b: HTTP 400: {\"error\":{\"message\":\"Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details.\",\"type\":\"invalid_request_error\",\"",
  "groq/openai/gpt-oss-20b: model unavailable (400); trying next model",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "groq/qwen/qwen3.8-27b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini: network error ReadTimeout, retrying",
  "gemini: unreachable (ReadTimeout); skipping provider"
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
