## Newsroom self-review, 2026-11-17

Looked at 29 runs over the last 3 days (81 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `gdelt`: Consider temporarily disabling or removing gdelt and gdelt-india until their connectivity stabilizes, or check timeout settings if configurable.  
  _Why:_ GDELT and GDELT-india are experiencing frequent connection timeouts (failing in roughly half of all runs), indicating network or stability issues.
- [ ] **tune** · `arxiv`: Add a polite delay or reduce request frequency for the arxiv source to avoid rate-limit errors.  
  _Why:_ Arxiv is encountering 429 Too Many Requests errors, which points to rate-limiting issues on the free endpoint.
- [ ] **coverage gap** · `Mistral AI`: Check the configuration or RSS feed associated with Mistral AI to ensure it is actively fetching new content.  
  _Why:_ Mistral AI produced no stories over the tracked period despite being in the source/lab list.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Consider lowering min_score_to_publish_1_to_10 from 6 to 5 to increase story volume, given the high drop count.  
  _Why:_ A large number of candidate stories (67 scored 4 and 39 scored 5) are being dropped just below the minimum publication threshold of 6.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 29,
 "stories_written": 81,
 "source_failures": {
  "arxiv": "3/29 runs; last error: failed: HTTPStatusError: Client error '429 Unknown Error' for url 'https://export.arxiv.org/api/query?search_query=cat%3Acs.AI+OR+cat%3Acs.C",
  "gdelt": "14/29 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "16/29 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 105,
  "score 4": 67,
  "score 5": 39,
  "could not verify yet": 32,
  "score 3": 16,
  "could not verify yet after a second try": 9,
  "variety": 8,
  "duplicate of 369f1ffcda11": 8
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-20b: request over its 8,000-token limit; retrying with a 1,310-token answer",
  "groq/openai/gpt-oss-20b: request too large for this model; trying next model",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-latest: 503 (server busy); trying next model",
  "gemini: 503 after retry; moving to next provider for this run",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing"
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
