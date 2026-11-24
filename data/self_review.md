## Newsroom self-review, 2026-11-24

Looked at 9 runs over the last 3 days (39 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `gdelt, gdelt-india`: Investigate the GDELT and GDELT-India fetchers (endpoint, query, or rate limit) and repair them; if GDELT is unreliable, consider replacing gdelt-india with a working India news RSS feed.  
  _Why:_ gdelt-india returned nothing in 7/9 runs and gdelt in 4/9 runs. These are the only India/global news sources besides the Indian tech sites, so the pipeline is effectively blind to non-AI-lab news most of the time.
- [ ] **fix source** · `mistral-news`: Check the mistral-news source (URL, parsing, or rate limit) and fix it; if it cannot be made reliable, remove it to avoid wasted fetches.  
  _Why:_ mistral-news returned nothing in 6/9 runs, so Mistral news coverage is nearly absent.
- [ ] **coverage gap** · `xAI, DeepSeek`: Add dedicated xAI and DeepSeek sources (official blogs/announcements) and verify their items are not being dropped by the 'not AI' filter or low scores.  
  _Why:_ xAI and DeepSeek are tracked labs but produced no stories this week, while other labs are well covered. Given the high drop counts, their items are likely being filtered out.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Confirm whether score-5 items should publish; if yes, find why 36 are dropped (likely 'could not verify yet' or max_stories_per_run=10 cap) and adjust the cap or verification step rather than the score threshold.  
  _Why:_ 36 stories were dropped at score 5, which equals the current min_score_to_publish (5). If the intent is to publish score-5 items, these are being dropped by a different rule (e.g., verification or per-run cap), so the threshold itself may be fine but the interaction is unclear.
- [ ] **tune** · `ai_providers_configured`: Reorder ai_providers_configured to put the most reliable free provider first (e.g., gemini or cerebras) and add small backoff between calls to groq to reduce per-minute limit hits.  
  _Why:_ Multiple provider notes show per-minute limits hit and models returning 400/unavailable, causing fallback churn and retries.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 9,
 "stories_written": 39,
 "source_failures": {},
 "sources_returning_nothing": {
  "mistral-news": "6/9 runs",
  "gdelt": "4/9 runs",
  "gdelt-india": "7/9 runs"
 },
 "drop_reasons": {
  "not AI": 90,
  "score 4": 68,
  "score 5": 36,
  "score 3": 33,
  "could not verify yet": 24,
  "score 6": 11,
  "duplicate of f1b7c64ada91": 7,
  "duplicate of 877f48487e8a": 7
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: model unavailable (400); trying next model",
  "groq/qwen/qwen3.8-27b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-20b: model unavailable (400); trying next model",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "groq/qwen/qwen3.8-27b: request over its 7,000-token limit; retrying with a 1,250-token answer",
  "groq/qwen/qwen3.8-27b: request too large for this model; trying next model"
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
