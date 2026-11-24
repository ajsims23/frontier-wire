# Frontier Wire

**A live AI news site run by an AI newsroom agent.** It reads around 30 sources every few hours. It then decides
what matters, checks it against its sources, writes it up and publishes it. It also explains what each development
means for DPA's work. People make the final calls. **Everything runs on free services (AI cost: ₹0).**

- Site: https://ajsims23.github.io/frontier-wire/
- How it works, from its own logs (pipeline, accuracy audit, corrections): `/system/`
- For other AI agents: MCP server at `<API address>/mcp` and JSON API at `/api/v1/*.json` (see `/api/`)

Created by Ajay Manuel.

---

## What runs, and when

| Job | When | What it does | Code |
|---|---|---|---|
| **Newsroom agent** | Every 3 hours (:17) | Editor-in-chief plans the run, then gather → judge → verify → research → write → publish (below) | `agent/pipeline.py`, `agent/chief.py` |
| **Breaking news watch** | Every 15 minutes | Checks the labs' own channels; if something is new, runs a quick breaking edition. Most checks use no AI | `.github/workflows/watch.yml` |
| **DPA lens** | Every 3 hours, 90 min after the newsroom | What each story means for DPA, the AI Radar, weekly calls, a daily fact-check audit of published stories, and the fact-check agent that settles its flags | `agent/dpa.py`, `agent/factcheck.py` |
| **DPA task bench** | Sundays | Tests every reachable free model on synthetic DPA-style document tasks, scored against known answers | `agent/bench.py` |
| **Daily recap** | Evenings | A scheduled Claude session writes a one-minute news bulletin of the top 5 stories; **Recap release** renders and publishes it | `agent/recap.py` |
| **API worker** | Always on (Cloudflare) | Ask the Wire, subscriptions and emails, feedback board, MCP server; daily digests at 08:50 IST; re-starts any run GitHub's cron misses | `worker/src/` |
| **Deploy website** | After every change | Builds the static site to GitHub Pages | `agent/build.py` |

A "scheduler" in the worker starts the newsroom, breaking-news and DPA jobs if GitHub's own cron skips them.

### What one newsroom run does

| Step | What happens |
|---|---|
| **Plan** | The editor-in-chief agent looks at the last two days of coverage, open storylines and what came in. It sets priorities, flags thin areas and runs up to three extra news searches. |
| **Gather** | Lab blogs and feeds, Hugging Face, arXiv, GDELT, Hacker News, Bluesky posts from leading people, and news searches. All are free with no keys. |
| **Judge** | Scores each item 1–10, drops noise and non-AI news, and merges coverage of the same event. A variety cap stops one source from flooding the page. Stories about sexual abuse or sexual imagery are never run (the site is read at work and shown in offices); the same rule (`agent/text.py` → `unsuitable`) keeps them out of every page, feed and recap. |
| **Verify** | A story needs an official source (the lab's post, the paper, the person's own post) or two independent outlets. A research agent searches and reads further when it is unsure. |
| **Write** | Headline, summary, "why it matters", an explainer, notes by audience, tags, trackers and storylines. |
| **Check** | Quotes must appear word for word in the source, or they're removed. Unsupported benchmark numbers are removed. Made-up ids from the model are ignored. |
| **Publish** | Home page, story pages, desks, RSS, email alerts and a run report (`data/last_run.md`). |

Every dropped item is logged with a reason, and the `/system/` page shows the counts.

### How flagged claims get settled

Each day a second model audits a sample of published stories claim by claim. It reads only one or two sources per
story, so a flag means "check this", not "this is wrong". The **fact-check agent** then settles each flag on its own:
- It re-reads **all** of the story's sources and rules on every flagged claim: **confirmed**, **reworded** or **removed**.
- **Confirmed** requires words copied exactly from a source.
- A correction may only narrow or remove a claim. It cannot add a number that isn't already in the story or the
  sources, or make the text much longer.
- Every ruling is published with a note (on the story and in the corrections log on `/system/`). Corrections reach
  the site at the next build and `data/stories.json` at the next newsroom run.
- A ruling that fails these checks is retried once. After that the flag stays open for a person.
- The accuracy rate on `/system/` still scores stories as they were first published.

## Where people stay in control

The agent proposes and people decide. There are three places where people decide:

1. **`config/dpa_review.yaml`**: approve **Adopt** on the AI Radar, override a radar ring, and **overrule the
   fact-check agent** on a flagged claim. A person's note shows as an "Editor's note" on the story and wins over the
   agent's ruling. Edit this file on github.com (pencil icon); the site redeploys in a few minutes.
2. **The daily recap email**: the editor gets a preview with an "Approve and send" link first. Nothing goes to
   subscribers until it's approved (a signed link handled by the worker).
3. **Reader suggestions**: the weekly analysis ranks ideas from the public board. The admin dashboard (`/admin/`,
   sign-in by emailed link) has Approve and Reject buttons. Approving only records the decision; it changes nothing on
   the site by itself.

`config/dpa.yaml` holds what the agent knows about DPA: public service lines, capabilities and roles. It holds
**no client names or client data**. Nothing confidential is sent to any AI provider.

## Running it day to day

**Daily check (2 minutes):**
1. Open `/system/` and check that stories are being published and how many accuracy flags are open.
2. Open the **Actions** tab and look for any red ✗ runs.
3. Skim the fact-check agent's rulings in the corrections log, and overrule any you disagree with in `config/dpa_review.yaml`.

**If something breaks:**

| Symptom | What to do |
|---|---|
| Few or no new stories | Run **Check AI keys** (Actions tab). It tests each provider and each model for tool calls. Remove dead models from `providers` in `config/settings.yaml`. |
| A provider's free quota runs out | No action needed. The agent falls back down the provider list automatically and logs it as "fallbacks handled" on `/system/`. |
| Ask the Wire or emails not working | Run **Worker status** (read-only; prints counts, never addresses). Redeploy with **Deploy API**. |
| Recap missing | Check the **Recap release** run for that day. The voice falls back from Gemini TTS to Workers AI to Kokoro; with no voice at all, the video publishes silent. |
| Site not updating | Re-run **Deploy website**. It retries once if GitHub can't find the Pages artifact. |

**Free-tier safety:** caps of 70 AI requests per run, 450 per day and 900k tokens per day (`config/settings.yaml` →
`limits`). A run that hits a cap stops calling AI, and unjudged items carry over to the next run.

**AI providers, in order** (`config/settings.yaml` → `providers`): **Gemini** (main) → **Groq** → **NVIDIA NIM** →
Mistral and OpenRouter (only if keys exist) → Cerebras (its free tier has ended; kept as a last resort).
Busy or retired models are skipped automatically. Only free tiers that need no credit card are used.

## The intelligence layer: Frontier Wire for DPA

| Page | What it is |
|---|---|
| `/dpa/` | The DPA lens: this week's calls, what to act on (each with a move — trial / assess / watch / caution — and a first test), and briefings by role |
| `/radar/` | The AI Radar: the 10 developments that matter most right now, on Adopt / Trial / Assess / Hold, with what they mean for DPA. Only a person can approve Adopt |
| `/bench/` | DPA Task Bench: which free model does DPA-style work best, re-tested weekly |
| `/system/` | Pipeline numbers, drop reasons, verification, the daily accuracy audit and the corrections log |
| `/api/` | The MCP server and JSON API, so any AI agent (Claude, ChatGPT and others) can use Frontier Wire |

## The daily recap

Every evening, a scheduled Claude session picks the day's top five stories and writes a one-minute anchor
bulletin (open, a line per story with context and why it matters, warm close). It pushes the script to
`recap-upload/<date>`. **Recap release** then does the rest:
- adds stock footage (Pixabay or Pexels with keys, otherwise free-licence Wikimedia Commons) and AI illustrations
- records the narration (Gemini TTS; fallbacks Workers AI, then open-source Kokoro)
- renders the video in headless Chrome and checks it
- stores it as the GitHub Release `recap-<date>` and puts it on the site

The site keeps the last 3 days' videos; older ones download from Releases. A vertical 9:16 cut is made for Shorts and Reels.

## Changing things

| To change | Edit |
|---|---|
| Sources (feeds, labs, people) | `config/sources.yaml` |
| Thresholds, caps, AI providers and models | `config/settings.yaml` |
| What the agent knows about DPA; radar limits | `config/dpa.yaml` |
| Human decisions (radar, fact-check flags) | `config/dpa_review.yaml` |
| Prompts | `agent/prompts.py` (newsroom), `agent/chief.py`, `agent/dpa.py`, `agent/factcheck.py` |
| Website look | `site/` (plain HTML, CSS, JavaScript; Jinja templates in `site/templates/`) |
| API, emails, MCP | `worker/src/` (Cloudflare Worker; `worker/schema.sql` for its D1 database) |

You can edit any of these on github.com, and each change redeploys automatically. Run the tests before changing code.

## Accounts and secrets (handover)

Everything lives in this repository plus these free accounts: **GitHub** (code, Actions, Pages, Releases),
**Cloudflare** (API worker, D1 database, Workers AI), **Brevo** (email), **Google AI Studio** (Gemini key),
**Groq**, **NVIDIA Developer Program** and **GoatCounter** (privacy-friendly page counts).

Repository secrets (Settings → Secrets and variables → Actions). Keys are never in the code or on the site.

| Secret | For |
|---|---|
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY` | The AI providers (optional extras: `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`) |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | Deploying the API worker |
| `BREVO_API_KEY` | Sending email |
| `ALERTS_DISPATCH_SECRET` | Lets the newsroom and recap jobs talk to the worker |
| `RECAP_REVIEWER_EMAIL` | Where the recap preview goes for approval |
| `SCHEDULER_TOKEN` | Optional: lets the worker start missed runs |
| `PEXELS_API_KEY`, `PIXABAY_API_KEY` | Optional: stock video for the recap |

Repository variables: `SITE_URL`, `API_URL`, `SENDER_EMAIL`, `GOATCOUNTER_CODE`; `REVIEW_MODE=true` makes the
newsroom open a pull request for review instead of publishing directly.

## Running locally

```bash
pip install -r requirements.txt
python -m pytest -q                      # Python tests (offline, no keys needed)
node --test worker/test/*.test.mjs       # worker tests
python -m agent sources                  # which sources respond (no AI calls)
GEMINI_API_KEY=... python -m agent check-models   # which free models work with your key
GEMINI_API_KEY=... python -m agent run            # one newsroom run
```

## Repository map

```
agent/     the newsroom, DPA lens, fact-checker, bench, recap and site builder (Python)
config/    sources, settings, DPA profile and human decisions (YAML)
data/      everything the agent produces: stories, audits, radar, runs, recaps (written by the bot)
site/      the website's templates, CSS and JavaScript
worker/    the API on Cloudflare Workers: Ask the Wire, email, feedback, MCP
video/     the recap's broadcast renderer
tests/     Python tests (worker tests are in worker/test/)
.github/   the scheduled workflows listed above
```
