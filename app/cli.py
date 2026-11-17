"""Command-line interface.

One company:
    python -m app.cli https://example.com

A list of companies (one URL per line) with a CSV summary:
    python -m app.cli --batch companies.txt

Add --loop to use the LangGraph agent, which keeps reading pages
until it has enough information:
    python -m app.cli https://example.com --loop -v
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

from app.agent import research_company
from app.llm import OpenAICompatibleLLM
from app.report import save_report


def run_one(url: str, llm, out_dir: str, loop: bool = False):
    if loop:
        from app.graph_agent import research_company_loop

        result = research_company_loop(url, llm)
        for step in result.agent_trace:
            logging.info(step)
    else:
        result = research_company(url, llm)
    md_path, _ = save_report(result, out_dir)
    print(f"✓ {result.profile.name or url} -> {md_path}")
    return result


def run_batch(path: str, llm, out_dir: str, loop: bool = False) -> None:
    urls = [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    summary_path = Path(out_dir) / "summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "company", "what_they_do", "top_need", "connection_note", "status"])
        for url in urls:
            try:
                r = run_one(url, llm, out_dir, loop)
                top_need = r.brief.likely_needs[0] if r.brief.likely_needs else ""
                writer.writerow([r.url, r.profile.name, r.profile.what_they_do, top_need,
                                 r.brief.connection_note, "ok"])
            except Exception as exc:
                print(f"✗ {url}: {exc}", file=sys.stderr)
                writer.writerow([url, "", "", "", "", f"error: {exc}"])
    print(f"\nSummary written to {summary_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Research a company and write a sales brief.")
    parser.add_argument("url", nargs="?", help="Company website URL")
    parser.add_argument("--batch", help="Text file with one URL per line")
    parser.add_argument("--out", default="reports", help="Output folder (default: reports)")
    parser.add_argument("--loop", action="store_true",
                        help="Use the LangGraph loop agent (reads until it has enough)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show agent decisions")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")

    if not args.url and not args.batch:
        parser.error("give a URL or --batch FILE")

    llm = OpenAICompatibleLLM()
    if args.batch:
        run_batch(args.batch, llm, args.out, args.loop)
    else:
        run_one(args.url, llm, args.out, args.loop)


if __name__ == "__main__":
    main()
