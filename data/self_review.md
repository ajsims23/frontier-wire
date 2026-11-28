## Newsroom self-review, 2026-11-28

Looked at 49 runs over the last 3 days (87 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `mistral-news`: Remove mistral-news from the sources list as it is consistently failing to return content.  
  _Why:_ mistral-news has returned nothing in 25 out of 49 runs.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 5 to 4.  
  _Why:_ A high volume of stories (155 stories) are falling just short of publication at score 4, while only 45 stories achieved score 5. Lowering the publication threshold to 4 would help capture more relevant developments without overwhelming the output.
- [ ] **coverage gap** · `xAI, DeepSeek, Alibaba (Qwen)`: Check if the feeds or search terms covering xAI, DeepSeek, and Alibaba (Qwen) are active and correctly configured to capture their recent releases.  
  _Why:_ xAI, DeepSeek, and Alibaba (Qwen) have not produced any stories this week despite being major AI labs.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 49,
 "stories_written": 87,
 "source_failures": {},
 "sources_returning_nothing": {
  "mistral-news": "25/49 runs"
 },
 "drop_reasons": {
  "not AI": 244,
  "score 4": 155,
  "score 3": 105,
  "score 5": 45,
  "could not verify yet": 39,
  "score 2": 16,
  "duplicate of 9794db2730fe": 16,
  "duplicate of 5d94a8a52956": 15
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "gemini: unreachable or too slow (ReadTimeout); resting it for 2 minutes",
  "groq: 429 after retry (rate_limit_exceeded tokens Rate limit reached for model `openai/gpt-oss-120b` in); moving to next provider for this run",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "gemini/gemini-3.5-flash-lite: per-minute limit hit; trying next model",
  "gemini/gemini-3.5-flash-lite: 503 (server busy); trying next model",
  "gemini/gemini-3.6-flash: answer cut off; retrying with more room",
  "gemini/gemini-3.6-flash: answer cut off; retrying with more room",
  "gemini/gemini-3.5-flash-lite: per-minute limit hit; trying next model"
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
