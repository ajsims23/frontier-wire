## Newsroom self-review, 2026-10-26

Looked at 34 runs over the last 3 days (58 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove gdelt due to frequent ConnectTimeout errors (22/34 runs)  
  _Why:_ High failure rate prevents timely news gathering
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india because it fails in most runs (26/34)  
  _Why:_ Consistently timing out, wasting resources
- [ ] **add source** · `xAI lab updates`: Add a source tracking xAI research announcements  
  _Why:_ xAI is a tracked lab with no stories this week
- [ ] **add source** · `Alibaba Qwen lab updates`: Add a source for Alibaba (Qwen) research releases  
  _Why:_ Alibaba (Qwen) is a tracked lab lacking coverage
- [ ] **tune** · `max_stories_per_run`: Reduce max_stories_per_run from 10 to 5  
  _Why:_ Fewer stories per run can improve overall quality and reduce overload

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 34,
 "stories_written": 58,
 "source_failures": {
  "arxiv": "4/34 runs; last error: failed: ReadTimeout: The read operation timed out",
  "gdelt-india": "26/34 runs; last error: failed: ConnectTimeout: _ssl.c:993: The handshake operation timed out",
  "gdelt": "22/34 runs; last error: failed: ConnectTimeout: _ssl.c:993: The handshake operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 130,
  "score 2": 113,
  "score 4": 111,
  "score 3": 69,
  "could not verify yet": 58,
  "score 1": 26,
  "duplicate of 3f492a65e9c2": 17,
  "variety": 12
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: answer cut off; retrying with more room",
  "cerebras/gpt-oss-120b: unusable answer",
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
