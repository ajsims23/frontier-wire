## Newsroom self-review, 2026-11-16

Looked at 31 runs over the last 3 days (83 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt-india`: Add request rate limiting or backoff for gdelt-india source. https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20  
  _Why:_ gdelt-india is failing with HTTP 429 Too Many Requests in 20/31 runs due to frequent rate limiting.
- [ ] **fix source** · `gdelt`: Increase timeout settings for the gdelt source connection.  
  _Why:_ gdelt is encountering SSL handshake timeouts in 12/31 runs.
- [ ] **coverage gap** · `Mistral AI, Alibaba (Qwen)`: Add specific news feeds or query terms for Mistral AI and Alibaba (Qwen) to improve coverage.  
  _Why:_ Mistral AI and Alibaba (Qwen) have tracked labs without any stories produced this week.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to increase published output given strong interest in these scores.  
  _Why:_ A large volume of stories (81 scored 4, 45 scored 3) are dropped just below the publication threshold of 6.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 31,
 "stories_written": 83,
 "source_failures": {
  "gdelt-india": "20/31 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt": "12/31 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "arxiv": "2/31 runs; last error: failed: HTTPStatusError: Client error '429 Unknown Error' for url 'https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 99,
  "score 4": 81,
  "score 3": 45,
  "score 5": 35,
  "could not verify yet": 33,
  "duplicate of a769a94b7f5c": 17,
  "could not verify yet after a second try": 11,
  "duplicate of 72e1fb99c741": 8
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "gemini: 503 after retry; moving to next provider for this run",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: HTTP 400: {\"error\":{\"message\":\"Failed to parse tool call arguments as JSON\",\"type\":\"invalid_request_error\",\"code\":\"tool_use_failed\",\"failed_generation\":\"{\\\"name",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: per-minute limit hit; trying next model",
  "gemini/gemini-flash-latest: answer cut off; retrying with more room"
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
