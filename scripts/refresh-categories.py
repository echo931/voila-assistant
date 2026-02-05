#!/usr/bin/env python3
"""
Refresh Voilà category cache.

Standalone script for cron or manual refresh.
Crawls full category tree and saves to ~/.voila-categories.json

Usage:
    python refresh-categories.py          # Default depth 3
    python refresh-categories.py --depth 2
    python refresh-categories.py --quiet  # No output (for cron)
"""

import sys
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from category_cache import CategoryCache


def main():
    parser = argparse.ArgumentParser(description="Refresh Voilà category cache")
    parser.add_argument("--depth", type=int, default=3, 
                        help="Max crawl depth (default: 3)")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Quiet mode (for cron)")
    parser.add_argument("--timeout", type=int, default=30000,
                        help="Page load timeout in ms (default: 30000)")
    args = parser.parse_args()
    
    cache = CategoryCache()
    
    def on_progress(msg):
        if not args.quiet:
            print(msg, file=sys.stderr)
    
    if not args.quiet:
        print("📂 Refreshing Voilà category cache...", file=sys.stderr)
    
    try:
        count = cache.refresh(
            headless=True,
            timeout=args.timeout,
            max_depth=args.depth,
            on_progress=on_progress
        )
        
        if not args.quiet:
            print(f"✅ {count} categories indexed", file=sys.stderr)
            print(f"📁 Saved to {cache.cache_file}", file=sys.stderr)
        
        return 0
        
    except Exception as e:
        if not args.quiet:
            print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
