## Newsroom self-review, 2026-11-24

Looked at 9 runs over the last 3 days (41 stories written).
Tick the suggestions you want applied; nothing changes until a person approves it.

- [ ] **fix source** · `mistral-news`: Investigate and fix the mistral-news source (check its endpoint/auth/parse logic); if it can't be repaired, remove it from the sources list.  
  _Why:_ mistral-news returned nothing in 7 of 9 runs, the worst of any source. It's effectively dead weight and likely failing silently.
- [ ] **fix source** · `gdelt, gdelt-india`: Fix the GDELT sources (verify the GDELT DOC API query/params and rate limits); if they keep failing, drop them rather than leaving them returning nothing.  
  _Why:_ gdelt (4/9) and gdelt-india (6/9) return nothing more than half the time, so India coverage is unreliable.
- [ ] **tune** · `ai_providers_configured (groq models)`: Remove or deprioritize the failing Groq models (gpt-oss-120b, gpt-oss-20b, qwen3.8-27b) from the rotation, or add a short backoff between requests to stay under the per-minute limit; keep the working free providers (gemini, cerebras, nvidia).  
  _Why:_ Provider notes show repeated per-minute limit hits and 'model unavailable (400)' on groq/openai/gpt-oss-120b and gpt-oss-20b, plus qwen3.8-27b hitting its 7,000-token request limit. These models are failing often enough to waste runs.
- [ ] **coverage gap** · `tracked labs: xAI, DeepSeek`: Add dedicated sources for xAI and DeepSeek (e.g., their official blogs/announcements and X/Bluesky accounts) so they aren't missed when news is sparse.  
  _Why:_ xAI and DeepSeek are tracked but produced no stories this week, even though they are active AI labs.
- [ ] **tune** · `min_score_to_publish_1_to_10`: Consider lowering min_score_to_publish to 4 to capture more stories, or verify the scoring prompt isn't being overly strict; review a sample of the dropped score-4 items first.  
  _Why:_ min_score_to_publish is 5, so 64 stories scored 4 and 23 scored 3 were dropped. Combined with 87 'not AI' drops, the pipeline is discarding a lot of potentially useful material.

<details><summary>Statistics the agent reviewed</summary>

```json
{
 "runs": 9,
 "stories_written": 41,
 "source_failures": {},
 "sources_returning_nothing": {
  "mistral-news": "7/9 runs",
  "gdelt": "4/9 runs",
  "gdelt-india": "6/9 runs"
 },
 "drop_reasons": {
  "not AI": 87,
  "score 4": 64,
  "score 5": 51,
  "score 3": 23,
  "could not verify yet": 23,
  "duplicate of f1b7c64ada91": 7,
  "variety": 7,
  "score 6": 7
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
