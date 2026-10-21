"""Command line.

  python -m agent run           full newsroom run (writes to data/)
  python -m agent sources       fetch every source and report what came back (no AI calls)
  python -m agent check-models  send one tiny request to each configured provider/model
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
    sub.add_parser("sources")
    sub.add_parser("check-models")
    args = ap.parse_args(argv)

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

    report = Newsroom(cfg, llm, fetcher, Store(cfg.data_dir), now).run()
    md = summary_markdown(report)
    print(md)
    (cfg.data_dir / "last_run.md").write_text(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(md)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"stories_written={len(report['written'])}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
