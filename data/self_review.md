## Newsroom self-review, 2026-11-26

Looked at 43 runs over the last 3 days (86 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 5 to 4 to increase story volume and reduce dropped stories.  
  _Why:_ A large number of stories (158 scored 4, and 123 scored 5) are being filtered out or failing publication due to the minimum score threshold of 5, while 86 stories have been successfully written. Lowering the minimum score threshold to 4 will allow more borderline-relevant stories through without flooding the site.
- [ ] **coverage gap** · `tracked_labs_without_stories_this_week`: Ensure xAI and DeepSeek sources or feeds are actively monitored and functioning properly to capture missed lab announcements.  
  _Why:_ Both xAI and DeepSeek have tracked labs without stories this week, indicating a lack of coverage or successful ingestion from their respective sources.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 43,
 "stories_written": 86,
 "source_failures": {},
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 212,
  "score 4": 158,
  "score 5": 123,
  "score 3": 99,
  "could not verify yet": 56,
  "duplicate of 66cc673a6baa": 53,
  "variety": 14,
  "score 6": 13
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek"
 ],
 "provider_notes": [
  "gemini/gemini-3.5-flash: 503 (server busy); trying next model",
  "gemini: 503 (server busy) on several tries; resting it for 2 minutes",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq: 429 after retry (rate_limit_exceeded tokens Rate limit reached for model `openai/gpt-oss-120b` in); moving to next provider for this run",
  "gemini/gemini-3.5-flash-lite: 503 (server busy); trying next model",
  "gemini: 429 after retry (429  You exceeded your current quota, please check your plan and billing details); moving to next provider for this run",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room"
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
