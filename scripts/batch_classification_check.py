"""Run live batch classification acceptance against a running TicketPilot API."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.config import build_settings

SUITE_PATH = ROOT / "data" / "classification_suite.json"
REPORT_DIR = ROOT / "reports"

BASE_URL = os.getenv("TICKETPILOT_BASE_URL", "http://127.0.0.1:8000")
POLL_TIMEOUT = float(os.getenv("BATCH_POLL_TIMEOUT", "90"))
POLL_INTERVAL = float(os.getenv("BATCH_POLL_INTERVAL", "1.0"))

MIN_CATEGORY_ACCURACY = float(os.getenv("BATCH_MIN_CATEGORY_ACCURACY", "0.80"))
MIN_URGENCY_ACCURACY = float(os.getenv("BATCH_MIN_URGENCY_ACCURACY", "0.80"))
FAIL_ON_SAFETY_VIOLATION = os.getenv(
    "BATCH_FAIL_ON_SAFETY_VIOLATION",
    "true",
).lower() in {"1", "true", "yes"}

PROCESSED_STATUSES = {"AUTO_ROUTED", "MANUAL_REVIEW"}
ERROR_MARKERS = {"AI_UNAVAILABLE", "SYSTEM_ERROR", "PARSE_ERROR"}


async def wait_for_processed(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    ticket_id: int,
) -> dict:
    deadline = asyncio.get_running_loop().time() + POLL_TIMEOUT
    last: dict | None = None

    while asyncio.get_running_loop().time() < deadline:
        response = await client.get(f"/tickets/{ticket_id}", headers=headers)

        if response.status_code != 200:
            raise RuntimeError(
                f"GET /tickets/{ticket_id} failed: "
                f"{response.status_code} {response.text[:500]}"
            )

        last = response.json()

        if last.get("status") in PROCESSED_STATUSES:
            return last

        await asyncio.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Ticket {ticket_id} was not processed within {POLL_TIMEOUT}s. "
        f"Last state: {last}"
    )


async def process_case(
    client: httpx.AsyncClient,
    settings,
    case: dict,
    run_id: str,
) -> dict:
    webhook_headers = {
        "X-Webhook-API-Key": settings.WEBHOOK_API_KEY,
    }
    admin_headers = {
        "X-Admin-API-Key": settings.ADMIN_API_KEY,
    }

    external_id = f"{case['id']}-{run_id}"

    payload = {
        "external_id": external_id,
        "customer_email": case.get("customer_email", "test@example.com"),
        "subject": case["subject"],
        "body": case["body"],
    }

    record = {
        "case_id": case["id"],
        "external_id": external_id,
        "expected_category": case["expected_category"],
        "expected_urgency": case["expected_urgency"],
        "expect_requires_human_review": bool(
            case.get("expect_requires_human_review", False)
        ),
        "error": False,
        "error_type": None,
        "detail": None,
    }

    try:
        response = await client.post(
            "/webhooks/tickets",
            json=payload,
            headers=webhook_headers,
        )
    except Exception as exc:  # noqa: BLE001
        record.update(
            {
                "error": True,
                "error_type": "REQUEST_EXCEPTION",
                "detail": str(exc),
            }
        )
        return record

    if response.status_code != 202:
        record.update(
            {
                "error": True,
                "error_type": "HTTP_ERROR",
                "status_code": response.status_code,
                "detail": response.text[:1000],
            }
        )
        return record

    ticket = response.json()
    record["ticket_id"] = ticket.get("id")
    record["initial_status"] = ticket.get("status")

    try:
        processed = await wait_for_processed(
            client=client,
            headers=admin_headers,
            ticket_id=ticket["id"],
        )
    except TimeoutError as exc:
        record.update(
            {
                "error": True,
                "error_type": "TIMEOUT",
                "detail": str(exc),
                "actual_status": "TIMEOUT",
            }
        )
        return record
    except Exception as exc:  # noqa: BLE001
        record.update(
            {
                "error": True,
                "error_type": "POLL_EXCEPTION",
                "detail": str(exc),
            }
        )
        return record

    actual_status = processed.get("status")
    actual_category = processed.get("ai_category")
    actual_urgency = processed.get("ai_urgency")
    actual_confidence = processed.get("ai_confidence")
    actual_summary = processed.get("ai_summary")
    assigned_to = processed.get("assigned_to")

    llm_available = (
        actual_status in PROCESSED_STATUSES
        and actual_category is not None
        and actual_urgency is not None
        and actual_summary not in ERROR_MARKERS
    )

    pass_category = llm_available and actual_category == case["expected_category"]
    pass_urgency = llm_available and actual_urgency == case["expected_urgency"]

    pass_safety = (
        not record["expect_requires_human_review"] or actual_status == "MANUAL_REVIEW"
    )

    pass_automation = (
        not record["expect_requires_human_review"] and actual_status == "AUTO_ROUTED"
    )

    overall_pass = llm_available and pass_category and pass_urgency and pass_safety

    record.update(
        {
            "error": not llm_available,
            "error_type": None
            if llm_available
            else "LLM_UNAVAILABLE_OR_MISSING_AI_FIELDS",
            "actual_status": actual_status,
            "ai_category": actual_category,
            "ai_urgency": actual_urgency,
            "ai_confidence": actual_confidence,
            "ai_summary": actual_summary,
            "assigned_to": assigned_to,
            "pass_category": pass_category,
            "pass_urgency": pass_urgency,
            "pass_safety": pass_safety,
            "pass_automation": pass_automation,
            "overall_pass": overall_pass,
        }
    )

    return record


def evaluate(records: list[dict]) -> dict:
    total = len(records)
    errors = [record for record in records if record.get("error")]
    successful = [record for record in records if not record.get("error")]

    safety_violations = [
        record
        for record in successful
        if record.get("expect_requires_human_review")
        and record.get("actual_status") == "AUTO_ROUTED"
    ]

    category_accuracy = (
        sum(1 for record in successful if record.get("pass_category")) / len(successful)
        if successful
        else 0.0
    )

    urgency_accuracy = (
        sum(1 for record in successful if record.get("pass_urgency")) / len(successful)
        if successful
        else 0.0
    )

    auto_count = sum(
        1 for record in successful if record.get("actual_status") == "AUTO_ROUTED"
    )

    manual_count = sum(
        1 for record in successful if record.get("actual_status") == "MANUAL_REVIEW"
    )

    automation_rate = auto_count / len(successful) if successful else 0.0
    manual_rate = manual_count / len(successful) if successful else 0.0

    fail = (
        bool(errors)
        or (FAIL_ON_SAFETY_VIOLATION and bool(safety_violations))
        or category_accuracy < MIN_CATEGORY_ACCURACY
        or urgency_accuracy < MIN_URGENCY_ACCURACY
    )

    return {
        "total_cases": total,
        "successful_cases": len(successful),
        "error_cases": len(errors),
        "safety_violations": len(safety_violations),
        "category_accuracy": round(category_accuracy, 4),
        "urgency_accuracy": round(urgency_accuracy, 4),
        "auto_routed_count": auto_count,
        "manual_review_count": manual_count,
        "automation_rate": round(automation_rate, 4),
        "manual_rate": round(manual_rate, 4),
        "thresholds": {
            "min_category_accuracy": MIN_CATEGORY_ACCURACY,
            "min_urgency_accuracy": MIN_URGENCY_ACCURACY,
            "fail_on_safety_violation": FAIL_ON_SAFETY_VIOLATION,
        },
        "exit_code": 1 if fail else 0,
        "error_records": errors,
        "safety_violation_records": safety_violations,
    }


def write_reports(records: list[dict], summary: dict, run_id: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    json_path = REPORT_DIR / f"batch_classification_report_{run_id}_{stamp}.json"
    csv_path = REPORT_DIR / f"batch_classification_report_{run_id}_{stamp}.csv"
    summary_path = REPORT_DIR / f"batch_classification_summary_{run_id}_{stamp}.json"

    latest_json = REPORT_DIR / "batch_classification_report_latest.json"
    latest_csv = REPORT_DIR / "batch_classification_report_latest.csv"
    latest_summary = REPORT_DIR / "batch_classification_summary_latest.json"

    json_text = json.dumps(records, indent=2, ensure_ascii=False)
    summary_text = json.dumps(summary, indent=2, ensure_ascii=False)

    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    summary_path.write_text(summary_text, encoding="utf-8")
    latest_summary.write_text(summary_text, encoding="utf-8")

    fieldnames: list[str] = []
    seen: set[str] = set()

    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    with latest_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"JSON report: {json_path}")
    print(f"CSV report:  {csv_path}")
    print(f"Summary:     {summary_path}")


async def main() -> int:
    if not SUITE_PATH.exists():
        print(f"Suite file not found: {SUITE_PATH}", file=sys.stderr)
        return 2

    settings = build_settings()
    cases = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:8]

    print(f"Base URL: {BASE_URL}")
    print(f"Run ID:   {run_id}")
    print(f"Cases:    {len(cases)}")
    print()

    records: list[dict] = []

    timeout = httpx.Timeout(30.0, connect=5.0)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['id']} - {case['subject']}")

            record = await process_case(
                client=client,
                settings=settings,
                case=case,
                run_id=run_id,
            )

            records.append(record)

            print(
                "    "
                f"status={record.get('actual_status')} "
                f"category={record.get('ai_category')} "
                f"urgency={record.get('ai_urgency')} "
                f"confidence={record.get('ai_confidence')} "
                f"pass={record.get('overall_pass')}"
            )

            if record.get("error"):
                print(f"    ERROR: {record.get('error_type')} {record.get('detail')}")

            print()

    summary = evaluate(records)
    write_reports(records=records, summary=summary, run_id=run_id)

    print("=== SUMMARY ===")
    print(f"Total cases:          {summary['total_cases']}")
    print(f"Successful cases:     {summary['successful_cases']}")
    print(f"Error cases:          {summary['error_cases']}")
    print(f"Safety violations:    {summary['safety_violations']}")
    print(f"Category accuracy:    {summary['category_accuracy']:.2%}")
    print(f"Urgency accuracy:     {summary['urgency_accuracy']:.2%}")
    print(f"Auto-routed count:    {summary['auto_routed_count']}")
    print(f"Manual-review count:  {summary['manual_review_count']}")
    print(f"Automation rate:      {summary['automation_rate']:.2%}")
    print(f"Manual rate:          {summary['manual_rate']:.2%}")
    print(f"Exit code:            {summary['exit_code']}")

    if summary["error_cases"]:
        print("\nErrors:")
        for record in summary["error_records"]:
            print(
                f"- {record.get('case_id')}: "
                f"{record.get('error_type')} "
                f"{record.get('detail')}"
            )

    if summary["safety_violations"]:
        print("\nSafety violations:")
        for record in summary["safety_violation_records"]:
            print(
                f"- {record.get('case_id')} expected human review "
                f"but got {record.get('actual_status')}"
            )

    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
