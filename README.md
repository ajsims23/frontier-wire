# Frontier Wire

A live AI news website, run by an AI newsroom agent. Every 3 hours it reads lab announcements,
papers, news and posts from leading people, then picks what matters, checks it and writes it up.
The site updates itself. **Everything runs on free services.**

---

## Launch it (about 20 minutes, one time)

### 1. Get a free AI key (2 min)
- Go to **https://cloud.cerebras.ai**, sign up, open **API Keys** and create a key. Copy it.
- Recommended: also get a free backup key from **https://console.groq.com/keys**.
  If one provider is busy, the agent automatically uses the other.

### 2. Put the project on GitHub (5 min, no command line)
1. Install **GitHub Desktop** (https://desktop.github.com) and sign in with your GitHub account.
2. Unzip `frontier-wire.zip` somewhere easy, such as Documents.
3. In GitHub Desktop, choose **File → Add local repository**, pick the `frontier-wire` folder, and
   click **Add repository**. If it asks to "create a repository", say yes.
4. Click **Publish repository**. **Untick "Keep this code private"** (free website hosting needs a
   public repository), then click **Publish**.

### 3. Add your key to the repository (2 min)
On github.com, open your repository and go to **Settings → Secrets and variables → Actions → New repository secret**:
- Name `CEREBRAS_API_KEY`, value: your Cerebras key.
- Also, if you have it: `GROQ_API_KEY`.

Keys stored here are encrypted. They're never visible in the code or on the site.

### 4. Switch on the website and the robot (2 min)
In the repository's **Settings**:
- **Pages** → *Build and deployment* → Source: **GitHub Actions**.
- **Actions → General** → *Workflow permissions*: choose **Read and write permissions** and tick
  **Allow GitHub Actions to create and approve pull requests**. Click **Save**.
- **General** → tick **Automatically delete head branches**.

### 5. First run (5 min)
1. Open the **Actions** tab. If asked, click **"I understand my workflows, go ahead and enable them"**.
2. Click **Newsroom agent → Run workflow → Run workflow**. Wait 3–5 minutes.
3. Review mode is on, so a **pull request** appears under **Pull requests**. Open it to read the
   stories, then click **Merge pull request** to publish them.
4. **Deploy website** runs automatically. Your site is live at
   **`https://<your-username>.github.io/frontier-wire/`**. The exact link is shown under Settings → Pages.

From then on it runs every 3 hours. New stories collect in the same pull request, so you can merge
once or twice a day.

**To publish automatically, without reviewing:** go to Settings → Secrets and variables → Actions →
**Variables** tab and add `REVIEW_MODE` = `false`.

### Optional: your own domain
Buy a domain (about ₹800–1,500 a year from Namecheap, GoDaddy, Hostinger and similar), then follow
Settings → Pages → *Custom domain*. GitHub provides HTTPS for free.

---

## What one run does

| Step | What happens |
|---|---|
| **Gather** | Lab blogs and RSS feeds, new Hugging Face models from 12 labs, arXiv and Hugging Face trending papers, GDELT global news search, Hacker News top AI stories, and Bluesky posts from leading people. All free, no keys. |
| **Judge** | The AI scores each item 1–10, drops noise (minor fine-tunes, listicles, marketing) and merges coverage of the same event. |
| **Verify** | A story needs an official source (the lab's post, the paper, or the person's own post) or 2 independent outlets. Missing outlets are searched for on GDELT. |
| **Write** | Headline, two-line summary, "why it matters", lab and model. |
| **Check** | Quotes must appear word for word in the source, or they're removed. |
| **Publish** | Front page, frontier lab tracker, RSS feed (`data/feed.xml`) and a run report. |

## Free-tier safety
- Caps of 40 AI requests per run, 300 per day and 700k tokens per day keep you well inside free limits (`config/settings.yaml` → `limits`).
- Provider fallback: Cerebras → Groq → OpenRouter → Gemini. Rate-limited or retired models are skipped automatically.
- Stories the agent keeps but can't write this run carry over to the next run.

## Changing things
- **Sources** (feeds, labs, Bluesky accounts): `config/sources.yaml`
- **Thresholds, caps, providers**: `config/settings.yaml`
- **Website look**: `site/` (plain HTML, CSS and JavaScript)

You can edit these files on github.com with the pencil icon. Each change redeploys automatically.

## If something isn't working
- **Each run's report:** Actions → Newsroom agent → the latest run → *Summary*. It lists failed sources, dropped stories and provider issues.
- **"No AI provider key is set"**: step 3 wasn't done, or the secret name is misspelt.
- **A model was retired**: the agent tries the next model in the list. Update `providers` in `settings.yaml` when convenient.

## Running locally (optional)
```bash
pip install -r requirements.txt
python -m pytest -q             # offline tests
python -m agent sources         # which sources respond (no AI calls)
CEREBRAS_API_KEY=... python -m agent check-models   # which free models work with your key
CEREBRAS_API_KEY=... python -m agent run
```
