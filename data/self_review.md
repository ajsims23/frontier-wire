## Newsroom self-review, 2026-11-15

Looked at 38 runs over the last 3 days (104 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt-india`: Remove gdelt‑india from the source list.  
  _Why:_ gdelt‑india fails in 23 of 38 runs (≈60% failure) and blocks story generation.
- [ ] **fix source** · `gdelt`: Add exponential back‑off and increase the connection timeout for gdelt.  
  _Why:_ gdelt times out in 13 of 38 runs; a simple retry/back‑off or longer timeout could recover many runs.
- [ ] **coverage gap** · `Mistral AI, Alibaba (Qwen)`: Add dedicated RSS or blog sources for Mistral AI and Alibaba Qwen to capture their announcements.  
  _Why:_ Mistral AI and Alibaba (Qwen) labs have no stories this week despite being tracked.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 6 to 5 to increase usable story yield.  
  _Why:_ Large numbers of drops are due to scores 4, 5 and 3 (total 241) while the publish threshold is 6.
- [ ] **remove source** · `sam-altman`: Remove sam‑altman from the source list.  
  _Why:_ sam‑altman fails intermittently (2/38) and provides little value; removing reduces error handling overhead.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 38,
 "stories_written": 104,
 "source_failures": {
  "gdelt": "13/38 runs; last error: failed: ConnectTimeout: _ssl.c:994: The handshake operation timed out",
  "gdelt-india": "23/38 runs; last error: failed: RuntimeError: GDELT paused for this run after repeated rate-limiting",
  "sam-altman": "2/38 runs; last error: failed: ReadTimeout: The read operation timed out"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 150,
  "score 4": 113,
  "score 5": 67,
  "score 3": 61,
  "could not verify yet": 50,
  "duplicate of efdd0bfa6110": 16,
  "duplicate of a769a94b7f5c": 16,
  "variety": 14
 },
 "tracked_labs_without_stories_this_week": [
  "Mistral AI",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/qwen/qwen3.8-27b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: request over its 8,000-token limit; retrying with a 2,149-token answer",
  "groq/openai/gpt-oss-120b: request too large for this model; trying next model",
  "groq/qwen/qwen3.8-27b: request too large for this model; trying next model",
  "groq/openai/gpt-oss-20b: request over its 8,000-token limit; retrying with a 2,056-token answer",
  "groq/openai/gpt-oss-20b: request over its 8,000-token limit; retrying with a 1,056-token answer",
  "groq/openai/gpt-oss-20b: request too large for this model; trying next model"
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
