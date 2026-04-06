import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request


CSV_PATH = "release_schedule.csv"


def load_rows(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize_date(date_str: str) -> str | None:
    date_str = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%-d/%Y"):
        try:
            return dt.datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def find_topic(rows, today_str: str) -> str | None:
    today = dt.date.fromisoformat(today_str)
    eligible = []

    for row in rows:
        cutoff = normalize_date(row["Code Cutoff"])
        if cutoff:
            cutoff_date = dt.date.fromisoformat(cutoff)
            if cutoff_date <= today:
                eligible.append((cutoff_date, row["Topic text"]))

    if not eligible:
        return None

    # pick most recent past cutoff
    eligible.sort(key=lambda x: x[0], reverse=True)
    return eligible[0][1]


def slack_set_topic(token: str, channel_id: str, topic: str) -> dict:
    data = urllib.parse.urlencode({
        "channel": channel_id,
        "topic": topic,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://slack.com/api/conversations.setTopic",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")

    if not token or not channel_id:
        print("Missing SLACK_BOT_TOKEN or SLACK_CHANNEL_ID.", file=sys.stderr)
        sys.exit(1)

    today = dt.date.today().isoformat()
    rows = load_rows(CSV_PATH)
    topic = find_topic(rows, today)

    if not topic:
        print(f"No matching row found for {today}. Exiting without changes.")
        return

    result = slack_set_topic(token, channel_id, topic)

    if not result.get("ok"):
        print(f"Slack API error: {result}", file=sys.stderr)
        sys.exit(1)

    print(f"Updated Slack topic for {today}.")


if __name__ == "__main__":
    main()
