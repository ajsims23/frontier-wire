## Newsroom self-review, 2026-11-08

Looked at 41 runs over the last 3 days (76 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt-india`: Add a request delay or backoff strategy for gdelt-india, or reduce its polling frequency to prevent rate limit errors. https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20  
  _Why:_ gdelt-india is failing with 429 Too Many Requests in nearly half of the runs due to rate limits.
- [ ] **fix source** · `gdelt`: Increase connection timeout thresholds or implement a retry wrapper with exponential backoff for the GDELT source.  
  _Why:_ gdelt is experiencing frequent timeout connection errors during SSL handshakes in nearly 40% of runs.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower the minimum publishing score from 6 to 5 to capture valuable borderline stories and increase output.  
  _Why:_ A high volume of stories (129) are being dropped with a score of 4, just below the publishing threshold of 6.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 41,
 "stories_written": 76,
 "source_failures": {
  "gdelt": "16/41 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "20/41 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 4": 129,
  "not AI": 126,
  "score 5": 100,
  "score 3": 46,
  "could not verify yet": 33,
  "variety": 22,
  "could not verify yet after a second try": 12,
  "duplicate of acdb0c16a39e": 8
 },
 "tracked_labs_without_stories_this_week": [],
 "provider_notes": [
  "gemini/gemini-flash-lite-latest: per-minute limit hit; trying next model",
  "gemini: network error ReadTimeout, retrying",
  "gemini: unreachable (ReadTimeout); skipping provider",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-flash-lite-latest: answer cut off; retrying with more room"
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
