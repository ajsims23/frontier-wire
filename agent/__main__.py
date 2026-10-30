"""Command line.

  python -m agent run           full newsroom run (writes to data/)
  python -m agent watch         quick check of the labs' own channels; runs a breaking-news edition if there's news
  python -m agent sources       fetch every source and report what came back (no AI calls)
  python -m agent check-models  send one tiny request to each configured provider/model
  python -m agent preview-desks plan a run and write the Builders and Top Voices desks now (set DATA_DIR to a copy of
                                data/ to try changes without touching the live site)
  python -m agent recap draft   pick today's top five and write data/recaps/<date>.json for the editor to fill
  python -m agent recap render --out DIR   check the filled script and render the 30s recap.mp4, poster.jpg, teaser.gif
  python -m agent recap check --out DIR    re-check a rendered video (length, size, codec, decodes cleanly)
"""
from __future__ import annotations

import argparse
import os
import sys

from .config import load_config
from .llm import LLM, Limits
from .pipeline import Newsroom, summary_markdown
from .sources import Gdelt, HttpFetcher, gather
from .store import Store, utcnow


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent", description="Frontier Wire newsroom agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("watch")
    sub.add_parser("sources")
    sub.add_parser("check-models")
    sub.add_parser("preview-desks")
    rc = sub.add_parser("recap")
    rc.add_argument("action", choices=["draft", "render", "check"])
    rc.add_argument("--date", default="", help="YYYY-MM-DD in IST (default: today)")
    rc.add_argument("--out", default="", help="folder for the rendered files")
    rc.add_argument("--force", action="store_true", help="draft: replace a script the editor already filled")
    args = ap.parse_args(argv)
    if args.cmd == "recap":
        return _recap(args)

    cfg = load_config()
    fetcher = HttpFetcher()
    now = utcnow()

    if args.cmd == "sources":
        items, status = gather(cfg.sources, fetcher, now=now, lookback_hours=cfg.run["lookback_hours"],
                               gdelt=Gdelt(fetcher), gdelt_settings=cfg.gdelt, lab_domains=cfg.lab_domains)
        for sid, st in status.items():
            print(f"{sid:16} {st}")
        print(f"\n{len(items)} items total")
        return 0

    limits = Limits(cfg.limits, cfg.data_dir / "usage.json")

    if args.cmd == "check-models":
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
        any_ok = False
        for p in cfg.providers:
            if not os.environ.get(p["key_env"]):
                print(f"{p['name']:11} skipped ({p['key_env']} not set)")
                continue
            for model in p["models"]:
                llm = LLM([dict(p, models=[model])], limits)
                try:
                    llm.ask(system="Reply by calling the tool.", prompt="Say ok.", schema_name="submit", schema=schema, max_tokens=50)
                    print(f"{p['name']:11} {model:45} OK")
                    any_ok = True
                except Exception as e:  # noqa: BLE001
                    print(f"{p['name']:11} {model:45} FAILED  {(llm.log or [str(e)])[-1][:100]}")
        return 0 if any_ok else 1

    llm = LLM(cfg.providers, limits)
    if not llm.configured:
        print("No AI provider key is set. Add CEREBRAS_API_KEY or GROQ_API_KEY (see README).", file=sys.stderr)
        return 2

    store = Store(cfg.data_dir)
    if args.cmd == "preview-desks":
        import json as _json
        from . import builders, top_voices
        room = Newsroom(cfg, llm, fetcher, store, now)
        fresh = room.collect()
        extra = room.make_plan(fresh)
        builders.update_builders(room, force=True)
        top_voices.update_top_voices(room, force=True)
        store.save(now, room.build_site(), room.report)
        lines = ["## Desk preview", "", f"Fresh items: {len(fresh)} · editor's searches found {len(extra)}",
                 "", "```json", _json.dumps({k: room.report.get(k) for k in (
                     "plan", "builders", "builders_sources", "top_voices", "top_voices_sources", "notes")}, indent=2), "```"]
        print("\n".join(lines))
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
                fh.write("\n".join(lines) + "\n")
        return 0
    mode = "full"
    if args.cmd == "watch":
        from .pipeline import breaking_sources
        items, _ = gather(breaking_sources(cfg.sources), fetcher, now=now, lookback_hours=12,
                          gdelt=Gdelt(fetcher), gdelt_settings=cfg.gdelt, lab_domains=cfg.lab_domains)
        from datetime import timedelta
        from .pipeline import _parse_time
        cutoff = now - timedelta(hours=12)
        # same test the breaking run uses: not seen before, and published in the last 12 hours (or undated)
        new = [it for it in items if not store.is_seen(it.url) and not ((_parse_time(it.published) or now) < cutoff)]
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
                fh.write(f"new_items={len(new)}\n")
        if not new:
            print("No new announcements from the labs.")
            return 0
        print(f"{len(new)} new item(s) from the labs: " + "; ".join(it.title[:60] for it in new[:5]))
        mode = "breaking"
    report = Newsroom(cfg, llm, fetcher, store, now, mode=mode).run()
    md = summary_markdown(report)
    print(md)
    (cfg.data_dir / "last_run.md").write_text(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"stories_written={len(report['written'])}\n")
            fh.write(f"self_review={'1' if report.get('self_review') else '0'}\n")
    return 0


def _recap(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from . import recap

    cfg = load_config()
    now = utcnow()
    date = args.date or recap.today(now)
    path = cfg.data_dir / "recaps" / f"{date}.json"
    if args.action == "draft":
        if path.exists() and json.loads(path.read_text()).get("hook") and not args.force:
            print(f"{path} is already filled; use --force to start again", file=sys.stderr)
            return 4
        stories = json.loads((cfg.data_dir / "stories.json").read_text())
        script = recap.draft(stories, now)
        print(json.dumps(script, indent=2, ensure_ascii=False))
        if len(script["stories"]) < 3:
            print(f"only {len(script['stories'])} stories in the last 24 hours; skipping today's recap", file=sys.stderr)
            return 3
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {path}", file=sys.stderr)
        return 0
    out = Path(args.out or f"_recap/{date}")
    if args.action == "render":
        script = json.loads(path.read_text())
        try:
            info = recap.render(script, out)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    else:
        info = recap.check(out)
    print(json.dumps(info, indent=2))
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
