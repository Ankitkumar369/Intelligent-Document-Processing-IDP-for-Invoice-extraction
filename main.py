import sys
import argparse
from src.core.pipeline import IDPPipeline
from src.core.logger import log


def main():
    parser = argparse.ArgumentParser(description="IDP System v2 - Invoice Processing Pipeline")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of files to process (for testing)")
    args = parser.parse_args()

    log.info("Starting IDP System v2")
    if args.limit:
        log.info(f"TEST MODE: Processing only {args.limit} files")
    else:
        log.info("FULL MODE: Processing all files in data/input/")

    pipeline = IDPPipeline()
    result = pipeline.run(limit=args.limit)

    print()
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"  Total Files   : {result.total_files}")
    print(f"  Successful    : {result.success}")
    print(f"  Failed        : {result.failed}")
    print(f"  Skipped       : {result.skipped}")
    print(f"  Time Elapsed  : {result.elapsed_sec}s")
    if result.total_files > 0:
        print(f"  Success Rate  : {(result.success/result.total_files*100):.1f}%")
    print()
    print("Outputs saved to:")
    print("  - data/output/json/      (per-invoice JSON)")
    print("  - data/output/csv/       (consolidated CSV)")
    print("  - data/output/excel/     (Excel report)")
    print("  - data/output/rag/       (RAG-ready chunks)")
    print("  - data/output/logs/      (logs + audit trail)")
    print("=" * 60)

    if result.failed_files:
        print()
        print("Failed files:")
        for f in result.failed_files[:20]:
            print(f"  - {f}")

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
