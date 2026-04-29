import datetime as dt
import os
import sys
import urllib.request
import urllib.parse
import json
from html.parser import HTMLParser

CONFLUENCE_URL = "https://textnow.atlassian.net/wiki/spaces/IPAU/pages/21685043202/Upgrades+Release+Manager"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.in_th = False
        self.current_row = []
        self.rows = []
        self.current_data = ""

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self.current_data = ""
            if tag == "td":
                self.in_td = True
            if tag == "th":
                self.in_th = True
        if tag == "tr":
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "td":
            self.in_td = False
            self.current_row.append(" ".join(self.current_data.split()).strip())
        if tag == "th":
            self.in_th = False
            self.current_row.append(" ".join(self.current_data.split()).strip())
        if tag == "tr" and self.current_row:
            self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_td or self.in_th:
            self.current_data += data


def fetch_confluence_html():
    req = urllib.request.Request(
        CONFLUENCE_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    return html


def fetch_confluence_table():
    html = fetch_confluence_html()

    # Debug: save page for inspection in logs/artifacts if needed
    with open("confluence_debug.html", "w", encoding="utf-8") as f:
        f.write(html)

    parser = TableParser()
    parser.feed(html)
    return parser.rows


def normalize_date(date_str):
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%-d/%Y"):
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def find_topic(rows):
    today = dt.date.today()
    eligible = []

    print(f"Today: {today.isoformat()}")
    print(f"Parsed row count: {len(rows)}")
    print("First 10 parsed rows:")
    for row in rows[:10]:
        print(row)

    for row in rows:
        if len(row) < 5:
            continue

        cutoff = normalize_date(row[1])
        if not cutoff:
            continue

        print(f"Candidate row: cutoff={cutoff}, row={row[:5]}")

        if cutoff <= today:
            eligible.append((cutoff, row))

    if not eligible:
        return None

    eligible.sort(key=lambda x: x[0], reverse=True)
    best_row = eligible[0][1]

    version = best_row[0]
    manager = best_row[2]
    ios = best_row[3] if len(best_row) > 3 else ""
    an = best_row[4] if len(best_row) > 4 else ""

    return (
        f"Release Version: {version} | "
        f"Release Owner: {manager} | "
        f"iOS Automation: {ios} | "
        f"AN Automation: {an}"
    )


def slack_set_topic(token, channel_id, topic):
    data = urllib.parse.urlencode({
        "channel": channel_id,
        "topic": topic
    }).encode()

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
        return json.loads(resp.read().decode())


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL_ID")

    if not token or not channel:
        print("Missing SLACK_BOT_TOKEN or SLACK_CHANNEL_ID")
        sys.exit(1)

    rows = fetch_confluence_table()
    topic = find_topic(rows)

    if not topic:
        print("No matching row found.")
        sys.exit(1)

    print("Topic to send:", topic)
    result = slack_set_topic(token, channel, topic)

    if not result.get("ok"):
        print("Slack API error:", result)
        sys.exit(1)

    print("Updated Slack topic successfully.")


if __name__ == "__main__":
    main()
