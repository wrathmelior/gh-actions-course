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
        self.current_row = []
        self.rows = []
        self.current_data = ""

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.in_td = True
            self.current_data = ""
        if tag == "tr":
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "td":
            self.in_td = False
            self.current_row.append(self.current_data.strip())
        if tag == "tr" and self.current_row:
            self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_td:
            self.current_data += data


def fetch_confluence_table():
    req = urllib.request.Request(CONFLUENCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")

    parser = TableParser()
    parser.feed(html)

    return parser.rows


def normalize_date(date_str):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(date_str.strip(), fmt).date()
        except:
            continue
    return None


def find_topic(rows):
    today = dt.date.today()
    best_row = None

    for row in rows:
        if len(row) < 3:
            continue

        cutoff = normalize_date(row[1])
        if not cutoff:
            continue

        if cutoff <= today:
            best_row = row

    if not best_row:
        return None

    version = best_row[0]
    manager = best_row[2]
    ios = best_row[3] if len(best_row) > 3 else ""
    an = best_row[4] if len(best_row) > 4 else ""

    return f"Release Version: {version} | Release Owner: {manager} | iOS: {ios} | AN: {an}"


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

    rows = fetch_confluence_table()
    topic = find_topic(rows)

    if not topic:
        print("No matching row found.")
        return

    result = slack_set_topic(token, channel, topic)

    if not result.get("ok"):
        print("Slack API error:", result)
        sys.exit(1)

    print("Updated Slack topic:", topic)


if __name__ == "__main__":
    main()
