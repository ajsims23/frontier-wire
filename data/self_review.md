## Newsroom self-review, 2026-10-22

Looked at 11 runs over the last 3 days (22 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **remove source** · `gdelt`: Remove GDELT as a source  
  _Why:_ 6 of 11 runs hit HTTP 429 errors, causing frequent failures
- [ ] **add source** · `deepmind-blog`: Add DeepMind blog as a source  
  _Why:_ Google DeepMind lab has no stories this week
- [ ] **add source** · `xai-blog`: Add xAI blog as a source  
  _Why:_ xAI lab is unrepresented in recent stories
- [ ] **add source** · `microsoft-research-ai`: Add Microsoft Research AI news source  
  _Why:_ Microsoft lab lacks coverage
- [ ] **tune** · `min_score_to_publish_1_to_10`: Lower to 5  
  _Why:_ 84 stories dropped at score 5; lowering will increase usable output without major quality loss

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 11,
 "stories_written": 22,
 "source_failures": {
  "gdelt": "6/11 runs; last error: failed: HTTPStatusError: Client error '429 Too Many Requests' for url 'https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22artificial%20"
 },
 "sources_returning_nothing": {},
 "drop_reasons": {
  "score 5": 84,
  "score 3": 27,
  "score 4": 26,
  "score 2": 25,
  "score 1": 25,
  "could not verify with enough independent": 13,
  "could not verify yet": 6,
  "duplicate of c3c47473c56f": 2
 },
 "tracked_labs_without_stories_this_week": [
  "Google DeepMind",
  "xAI",
  "DeepSeek",
  "Alibaba (Qwen)",
  "Microsoft"
 ],
 "provider_notes": [
  "cerebras/gpt-oss-120b: unusable answer; trying next model",
  "cerebras/llama3.3-70b: model unavailable (404); trying next model",
  "cerebras/qwen-3-235b-a22b-instruct-2507: model unavailable (404); trying next model",
  "cerebras/gpt-oss-120b: unusable answer",
  "cerebras/gpt-oss-120b: unusable answer",
  "cerebras/gpt-oss-120b: unusable answer",
  "cerebras: listed models retired; trying qwen-3.8-27b (update settings.yaml when convenient)",
  "cerebras/qwen-3.8-27b: HTTP 400: {\"message\":\"Failed to generate tool_calls. Exception: Failed to generate tool call but tool_choice = 'required'.\",\"type\":\"generation_error\",\"param\":\"t"
 ],
 "current_settings": {
  "min_score_to_publish_1_to_10": 6,
  "max_stories_per_run": 8,
  "ai_providers_configured": [
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
   "import-ai",
   "simon-willison",
   "sam-altman",
   "bluesky"
  ]
 }
}
```

</details>
