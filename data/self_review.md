## Newsroom self-review, 2026-11-23

Looked at 12 runs over the last 3 days (53 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt-india`: Remove the gdelt-india source as it is unreliable.  
  _Why:_ gdelt-india has failed to return content in 9 out of 12 runs.
- [ ] **remove source** · `mistral-news`: Remove the mistral-news source due to high failure rate.  
  _Why:_ mistral-news has returned nothing in 6 out of 12 runs.
- [ ] **coverage gap** · `xAI, DeepSeek`: Add dedicated RSS or news feeds for xAI and DeepSeek to improve coverage of these key labs.  
  _Why:_ Tracked labs xAI and DeepSeek have produced no stories this week, despite xAI being in the sources list.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower the minimum score to publish from 5 to 4 to capture more borderline relevant stories and reduce drop volume.  
  _Why:_ A large number of candidate stories (68) scored a 4, falling just below the publish threshold of 5 while still generating significant processing overhead.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 12,
 "stories_written": 53,
 "source_failures": {},
 "sources_returning_nothing": {
  "gdelt-india": "9/12 runs",
  "mistral-news": "6/12 runs"
 },
 "drop_reasons": {
  "not AI": 111,
  "score 4": 68,
  "score 3": 29,
  "score 5": 29,
  "could not verify yet": 23,
  "duplicate of f1b7c64ada91": 17,
  "duplicate of 4aacf31011a3": 12,
  "duplicate of 8099b1cf49a8": 7
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
  "groq/openai/gpt-oss-120b: HTTP 400: {\"error\":{\"message\":\"Failed to parse tool call arguments as JSON\",\"type\":\"invalid_request_error\",\"code\":\"tool_use_failed\",\"failed_generation\":\"{\\\"name",
  "gemini/gemini-flash-lite-latest: 503 (server busy); trying next model",
  "gemini/gemini-flash-latest: 503 (server busy); trying next model"
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
