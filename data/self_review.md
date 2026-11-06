## Newsroom self-review, 2026-11-06

Looked at 41 runs over the last 3 days (60 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove the gdelt source and replace it with an alternative free news API.  
  _Why:_ gdelt fails in 15/41 runs with HTTP 429, throttling the pipeline.
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india; consider adding a different regional source if needed.  
  _Why:_ gdelt-india fails in 16/41 runs with ConnectTimeout, causing frequent gaps.
- [ ] **coverage gap** · `Meta`: Add a dedicated Meta AI news source (e.g., a Meta AI blog feed).  
  _Why:_ Meta lab produced no stories this week despite having a source.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to increase usable output.  
  _Why:_ 194 stories dropped due to score 5 and 148 due to score 4; current min_score is 6.
- [ ] **remove source** · `cerebras`: Remove cerebras from ai_providers_configured to avoid quota failures.  
  _Why:_ Cerebras providers repeatedly return payment-required errors, wasting runs.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 41,
 "stories_written": 60,
 "source_failures": {
  "gdelt": "15/41 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20",
  "gdelt-india": "16/41 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 194,
  "not AI": 182,
  "score 4": 148,
  "could not verify yet": 89,
  "could not verify yet after a second try": 32,
  "score 3": 21,
  "score 0": 18,
  "duplicate of e420e884477a": 18
 },
 "tracked_labs_without_stories_this_week": [
  "Meta"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-20b: HTTP 413: {\"error\":{\"message\":\"Request too large for model `openai/gpt-oss-20b` in organization `org_01m5f76hpme70svswvfnz1wxpn` service tier `on_demand` on tok",
  "groq/allam-2-7b: HTTP 400: {\"error\":{\"message\":\"`max_tokens` must be less than or equal to `4096`, the maximum value for `max_tokens` is less than the `context_window` for this ",
  "cerebras/gpt-oss-120b: HTTP 402: {\"message\":\"Payment required to access this resource. Visit your billing tab.\",\"type\":\"payment_required_error\",\"param\":\"quota\",\"code\":\"payment_require",
  "cerebras/gpt-oss-120b: HTTP 402: {\"message\":\"Payment required to access this resource. Visit your billing tab.\",\"type\":\"payment_required_error\",\"param\":\"quota\",\"code\":\"payment_require",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq: 429 after retry; moving to next provider for this run",
  "cerebras/gpt-oss-120b: HTTP 402: {\"message\":\"Payment required to access this resource. Visit your billing tab.\",\"type\":\"payment_required_error\",\"param\":\"quota\",\"code\":\"payment_require",
  "cerebras/gpt-oss-120b: HTTP 402: {\"message\":\"Payment required to access this resource. Visit your billing tab.\",\"type\":\"payment_required_error\",\"param\":\"quota\",\"code\":\"payment_require"
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
