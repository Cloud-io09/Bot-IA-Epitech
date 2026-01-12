import argparse
from pathlib import Path

from .crawler import crawl_site
from .rag import build_index, save_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a RAG index from epitech.eu")
    parser.add_argument("--base-url", default="https://www.epitech.eu")
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--output", default="rag_index.jsonl")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--max-chunks-per-page", type=int, default=8)
    parser.add_argument("--no-sitemap", action="store_true", help="Disable sitemap-based seeding.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pages = crawl_site(
        args.base_url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        rate_limit_s=args.rate_limit,
        use_sitemap=not args.no_sitemap,
    )
    if not pages:
        raise SystemExit("No pages collected. Check base URL or crawl limits.")

    chunks = build_index(
        pages,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        max_chunks_per_page=args.max_chunks_per_page,
    )
    if not chunks:
        raise SystemExit("No index chunks created. Check embedding model availability.")

    output_path = Path(args.output)
    save_index(chunks, output_path)
    print(f"Index saved to {output_path} ({len(chunks)} chunks).")


if __name__ == "__main__":
    main()
