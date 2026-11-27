## Newsroom self-review, 2026-11-27

Looked at 52 runs over the last 3 days (106 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower min_score_to_publish_1_to_10 from 5 to 4 to increase story output given the high number of near-threshold drops.  
  _Why:_ A high volume of stories are dropping due to scores between 5 and 7 (score 5 alone has 116 drops, and scores 2-4 account to 351 drops), while only 106 stories were written across 52 runs. Lowering the minimum publishing score threshold slightly will help capture more borderline-quality news.
- [ ] **coverage gap** · `sources`: Add dedicated RSS feeds or sources for DeepSeek and Alibaba (Qwen) to ensure these tracked labs are adequately covered.  
  _Why:_ Major AI labs xAI, DeepSeek, and Alibaba (Qwen) had zero stories written about them this week, representing a significant coverage gap.
- [ ] **tune** · `ai_providers_configured`: Deprioritize or adjust rate-limiting pacing for groq models to reduce 429 rate limit errors.  
  _Why:_ Groq providers frequently hit per-minute rate limits and 429 errors (as seen in provider notes), causing fallbacks and delays. Adjusting rate-limiting parameters or prioritizing other free providers like cerebras and gemini can improve stability.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 52,
 "stories_written": 106,
 "source_failures": {},
 "sources_returning_nothing": {},
 "drop_reasons": {
  "not AI": 260,
  "score 4": 200,
  "score 3": 131,
  "score 5": 116,
  "could not verify yet": 58,
  "duplicate of 66cc673a6baa": 53,
  "score 2": 20,
  "variety": 16
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek",
  "Alibaba (Qwen)"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "gemini/gemini-3.5-flash-lite: 503 (server busy); trying next model",
  "gemini: unreachable or too slow (ReadTimeout); resting it for 2 minutes",
  "groq: 429 after retry (rate_limit_exceeded tokens Rate limit reached for model `openai/gpt-oss-120b` in); moving to next provider for this run",
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
