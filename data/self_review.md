## Newsroom self-review, 2026-11-22

Looked at 26 runs over the last 3 days (76 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt-india`: Remove the gdelt-india source to clean up execution runs and prevent empty fetches.  
  _Why:_ The gdelt-india source has failed to return anything in 15 out of 26 runs, indicating it is likely broken or empty.
- [ ] **fix source** · `xai`: Check and update the xAI source configuration to ensure it is actively capturing posts or news.  
  _Why:_ Tracked labs xAI and DeepSeek had no stories this week, and xAI's source may need verification or additional query broadening.
- [ ] **coverage gap** · `DeepSeek`: Add additional free RSS feeds or query parameters for DeepSeek news coverage to bridge the gap.  
  _Why:_ DeepSeek had no stories this week despite being a major AI lab, indicating a potential coverage gap.
- [ ] **tune** · `groq/openai/gpt-oss-120b`: Lower request frequency or adjust fallback priority away from groq/openai/gpt-oss-120b when rate limits are repeatedly hit.  
  _Why:_ Groq/openai/gpt-oss-120b is frequently hitting per-minute rate limits and failing tool calls, leading to fallback retries.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 26,
 "stories_written": 76,
 "source_failures": {},
 "sources_returning_nothing": {
  "gdelt-india": "15/26 runs"
 },
 "drop_reasons": {
  "not AI": 167,
  "score 4": 129,
  "score 5": 65,
  "score 3": 62,
  "could not verify yet": 36,
  "duplicate of f1b7c64ada91": 17,
  "duplicate of 4aacf31011a3": 14,
  "variety": 14
 },
 "tracked_labs_without_stories_this_week": [
  "xAI",
  "DeepSeek"
 ],
 "provider_notes": [
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: per-minute limit hit; trying next model",
  "groq/openai/gpt-oss-120b: couldn't force a tool call; retrying without forcing",
  "groq/openai/gpt-oss-120b: HTTP 400: {\"error\":{\"message\":\"Failed to parse tool call arguments as JSON\",\"type\":\"invalid_request_error\",\"code\":\"tool_use_failed\",\"failed_generation\":\"{\\\"name"
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
