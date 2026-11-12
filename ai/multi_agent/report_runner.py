"""CLI entry point: generate a financial health report for the signed-in user.

  python ai/multi_agent/report_runner.py --email you@example.com --password '...' [--month 6 --year 2026] [--output report.md]
  (or set API_JWT_TOKEN in the environment instead of --email/--password)

Month/year default to the current month. Gemini adds short narratives when GOOGLE_API_KEY is set; otherwise the report is
produced from the calculated figures only.
"""
import argparse
import datetime
import getpass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from common.api_client import FinanceApiClient  # noqa: E402
from multi_agent.graph import generate_financial_report  # noqa: E402


def main(argv=None) -> int:
    today = datetime.date.today()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--month", type=int, default=today.month)
    p.add_argument("--year", type=int, default=today.year)
    p.add_argument("--email")
    p.add_argument("--password", help="omit to be prompted")
    p.add_argument("--no-llm", action="store_true", help="skip Gemini narratives (calculated report only)")
    p.add_argument("--output", help="also write the report to this Markdown file")
    args = p.parse_args(argv)

    token = os.getenv("API_JWT_TOKEN") or None
    if args.email:
        res = FinanceApiClient().login(args.email, args.password or getpass.getpass("Password: "))
        if not res.ok:
            print(f"Sign-in failed: {res.error}", file=sys.stderr)
            return 2
        token = res.data["access_token"]
    if not token:
        print("Provide --email/--password or set API_JWT_TOKEN.", file=sys.stderr)
        return 2

    print(f"Generating Financial Health Report for {args.month:02d}/{args.year}")
    print("=" * 60)
    result = generate_financial_report(None, args.month, args.year, token=token, use_llm=not args.no_llm)
    print("\nAgent Execution Log:")
    for msg in result["messages"]:
        print(f"  ✓ {msg}")
    if result["errors"]:
        print("\nErrors encountered:")
        for err in result["errors"]:
            print(f"  ✗ {err}")
    print("\n" + "=" * 60 + "\nFINANCIAL HEALTH REPORT\n" + "=" * 60)
    print(result["final_report"])
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(result["final_report"])
        print(f"\nSaved to {args.output}")
    return 0 if result["report_status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
