## Newsroom self-review, 2026-11-19

Looked at 36 runs over the last 3 days (115 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `arxiv`: Increase polling interval or add request backoff for the arXiv source to prevent 429 rate limit errors. https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C  
  _Why:_ arXiv is returning HTTP 429 Too Many Requests errors due to rate limiting. We should increase the polling interval or add a backoff delay to comply with arXiv API usage guidelines.
- [ ] **fix source** · `gdelt`: Add a timeout increase or retry mechanism for GDELT and GDELT-India connections to handle transient network and handshake latency.  
  _Why:_ GDELT and GDELT-India sources are experiencing frequent SSL handshake connection timeouts (failing in over a third of runs).
- [ ] **coverage gap** · `Mistral AI`: Check or adjust the retrieval filters for Mistral AI to ensure lab announcements are correctly captured.  
  _Why:_ Mistral AI generated zero stories this week, indicating a potential under-coverage or retrieval issue for their announcements.
- [ ] **tune** · `groq`: Reduce concurrency or add request pacing for Groq to stay within free tier rate limits.  
  _Why:_ Groq is frequently hitting per-minute rate limits, causing fallback retries.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Consider lowering min_score_to_publish_1_to_10 from 6 to 5 if quality permits, given how many stories are narrowly missing the cutoff.  
  _Why:_ A large number of candidate stories (174) are being dropped with a score of 4, just below the publishing threshold of 6.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 36,
 "stories_written": 115,
 "source_failures": {
  "arxiv": "2/36 runs; last error: failed: HTTPStatusError: Client error '429 Unknown Error' for url 'https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C",
  "gdelt": "13/36 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "16/36 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 204,
  "score 4": 174,
  "score 5": 90,
  "score 3": 89,
  "could not verify yet": 57,
  "variety": 24,
  "could not verify yet after a second try": 11,
  "score 2": 11
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI"
 ],
 "provider_notes": [
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
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
