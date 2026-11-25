## Newsroom self-review, 2026-11-25

Looked at 17 runs over the last 3 days (63 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `mistral-news`: Remove mistral-news source as it is frequently unproductive.  
  _Why:_ mistral-news has returned nothing in 10 out of 17 runs.
- [ ] **remove source** · `gdelt-india`: Remove gdelt-india source due to persistent lack of returns.  
  _Why:_ gdelt-india has returned nothing in 10 out of 17 runs.
- [ ] **coverage gap** · `xAI`: Add dedicated sources or increase monitoring for xAI and DeepSeek to cover tracked labs effectively.  
  _Why:_ xAI and DeepSeek have been tracked without generating any stories this week.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 5 to 4 to reduce valuable story drops.  
  _Why:_ A high volume of stories are scored 5 (105 drops) and 4 (110 drops), while the current minimum score to publish is 5. Lowering min_score_to_publish to 4 or adjusting the scoring threshold could capture more viable content.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 17,
 "stories_written": 63,
 "source_failures": {},
 "sources_returning_nothing": {
  "mistral-news": "10/17 runs",
  "gdelt-india": "10/17 runs"
 },
 "drop_reasons": {
  "not AI": 132,
  "score 4": 110,
  "score 5": 105,
  "score 3": 48,
  "could not verify yet": 41,
  "duplicate of 66cc673a6baa": 40,
  "score 6": 13,
  "could not verify yet after a second try": 10
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek"
 ],
 "provider_notes": [
  "groq: 429 after retry (rate_limit_exceeded tokens Rate limit reached for model `openai/gpt-oss-120b` in); moving to next provider for this run",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
  "nvidia/nvidia/nemotron-3-ultra-550b-a55b: answer cut off; retrying with more room",
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
