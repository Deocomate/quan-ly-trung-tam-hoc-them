from __future__ import annotations

import sys

from app.seeder.seed import UnsafeSeedError, format_summary, seed_sample_data


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        summary = seed_sample_data()
    except UnsafeSeedError as exc:
        print(f"Không thể seed dữ liệu mẫu: {exc}", file=sys.stderr)
        return 1
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

