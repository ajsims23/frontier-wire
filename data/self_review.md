## Newsroom self-review, 2026-11-13

Looked at 47 runs over the last 3 days (118 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `ai_providers_configured`: Remove cerebras from ai_providers_configured since its free quota is used up.  
  _Why:_ The Cerebras provider hit a 402 Payment Required error, indicating its free quota is exhausted.
- [ ] **fix source** · `gdelt-india`: Lower the polling frequency or remove the gdelt-india source to prevent rate limiting.  
  _Why:_ gdelt-india is failing almost half the time (21/47 runs) with 429 Too Many Requests errors due to heavy query frequency.
- [ ] **fix source** · `gdelt`: Increase timeout thresholds or remove the gdelt source if timeouts persist.  
  _Why:_ gdelt is failing frequently (14/47 runs) with SSL handshake timeouts.
- [ ] **coverage gap** · `tracked_labs_without_stories_this_week`: Add targeted queries or RSS/blog sources for Mistral AI and Alibaba (Qwen) to improve coverage.  
  _Why:_ Mistral AI and Alibaba (Qwen) have not produced any stories this week.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 47,
 "stories_written": 118,
 "source_failures": {
  "gdelt": "14/47 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "21/47 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 215,
  "score 4": 187,
  "score 5": 106,
  "score 3": 73,
  "could not verify yet": 61,
  "variety": 29,
  "duplicate of 88cba1275d52": 24,
  "score 7": 17
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq: 429 after retry; moving to next provider for this run",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia: network error ReadTimeout, retrying",
  "nvidia: unreachable (ReadTimeout); skipping provider",
  "cerebras: payment required (402) \u2014 free quota used up or billing needed; skipping provider"
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
