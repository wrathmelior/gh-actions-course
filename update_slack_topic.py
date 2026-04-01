import csv
import datetime as dt
import os
import sys
import urllib.parse
import urllib.request
import json


CSV_PATH = "release_schedule.csv"


def load_rows(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_topic(rows, today_str: str) -> str | None:
    # Exact date match
    for row in rows:
        if row["code_cutoff"].strip() == today_str:
            return row["topic_text"]
    return None


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
