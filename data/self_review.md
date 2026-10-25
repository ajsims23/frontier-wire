## Newsroom self-review, 2026-10-25

Looked at 40 runs over the last 3 days (69 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `arxiv`: Add a retry with increased read timeout (e.g., 30 s) and back‑off for arxiv queries  
  _Why:_ Arxiv fails 4/40 runs due to read timeout, causing missed stories
- [ ] **remove source** · `gdelt`: Temporarily disable the gdelt source  
  _Why:_ gdelt fails 22/40 runs with connect timeouts, heavily reducing reliability
- [ ] **remove source** · `gdelt-india`: Temporarily disable the gdelt‑india source  
  _Why:_ gdelt‑india fails 28/40 runs with HTTP 429, indicating rate‑limit issues
- [ ] **add source** · `Alibaba (Qwen)`: Add a free news source covering Alibaba’s Qwen lab (e.g., monitor Alibaba press releases or relevant RSS feeds)  
  _Why:_ Lab xAI and Alibaba (Qwen) have no stories this week, indicating coverage gap
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower the minimum score from 6 to 5  
  _Why:_ Most drops are due to low scores (score 5‑1); lowering the threshold will increase usable story count without sacrificing quality

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 40,
 "stories_written": 69,
 "source_failures": {
  "arxiv": "4/40 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt": "22/40 runs; last error: failed: ConnectTimeout: _ssl.c:993: The handshake operation timed out",
  "gdelt-india": "28/40 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 167,
  "score 2": 164,
  "score 4": 108,
  "score 3": 70,
  "could not verify yet": 62,
  "score 1": 35,
  "could not verify yet after a second try": 18,
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
