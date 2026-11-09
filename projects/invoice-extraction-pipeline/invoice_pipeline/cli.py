from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .export import export_csv, export_excel, export_google_sheet, export_json
from .extractor import AnthropicExtractor, Extractor, OpenAIExtractor
from .pipeline import process_folder


def make_extractor(provider: str) -> Extractor:
    load_dotenv()
    if provider == "anthropic":
        return AnthropicExtractor(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    return OpenAIExtractor(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="invoice-extract", description="Extract structured data from invoice PDFs and scans")
    parser.add_argument("folder", type=Path, help="folder with PDF / PNG / JPG invoices")
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--provider", choices=["openai", "anthropic"], default=os.getenv("LLM_PROVIDER", "openai"))
    parser.add_argument("--sheet-id", help="also append results to this Google Sheet")
    parser.add_argument("--credentials", default="service_account.json", help="Google service account JSON")
    args = parser.parse_args()

    results = process_folder(args.folder, make_extractor(args.provider))
    written = [*export_csv(results, args.out), export_json(results, args.out), export_excel(results, args.out)]
    if args.sheet_id:
        export_google_sheet(results, args.sheet_id, args.credentials)

    ok = sum(r.status == "ok" for r in results)
    print(f"\n{len(results)} invoices: {ok} ok, {len(results) - ok} need review or failed")
    for r in results:
        if r.status != "ok":
            print(f"  - {r.file} [{r.status}]: {'; '.join(r.issues)}")
    print("Written:", ", ".join(str(p) for p in written))


if __name__ == "__main__":
    main()
