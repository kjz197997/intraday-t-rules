"""每天抓取仓库 Issue 与评论，把有实质内容的反馈追加到 反馈台账.md。

无外部依赖；用 Actions 自带的 GITHUB_TOKEN 调 REST API。
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta

REPO = os.environ.get("REPO", "kjz197997/intraday-t-rules")
TOKEN = os.environ.get("GH_TOKEN", "")
LEDGER = "反馈台账.md"
STRONG_FILE = "反馈台账_强关联.md"
API = "https://api.github.com"

CST = timezone(timedelta(hours=8))
today = datetime.now(CST).strftime("%Y-%m-%d")

NOISE = re.compile(r"^\s*(\+|顶|支持|同意|mark|up|已阅|+1|nice|good job)\s*$", re.I)


def api(path):
    req = urllib.request.Request(API + path, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "feedback-bot",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def clean(t, n=220):
    t = re.sub(r"\s+", " ", (t or "")).strip()
    t = t.replace("|", "｜")
    return t[:n] + ("…" if len(t) > n else "")


def meaningful(text):
    t = (text or "").strip()
    if len(t) < 8:
        return False
    if NOISE.match(t):
        return False
    return True


items = api(f"/repos/{REPO}/issues?state=all&per_page=100&sort=created&direction=desc")
rows = []
for it in items:
    if "pull_request" in it:
        continue
    num, title, url = it["number"], it.get("title", ""), it["html_url"]
    if meaningful(it.get("body")):
        rows.append((num, title, url, clean(it.get("body")),
                     "开源议题", it.get("created_at", "")))
    try:
        comments = api(f"/repos/{REPO}/issues/{num}/comments?per_page=100")
    except Exception:
        comments = []
    for c in comments:
        body = c.get("body", "")
        if meaningful(body):
            rows.append((num, title, c["html_url"], clean(body),
                         "评论", c.get("created_at", "")))

if not rows:
    print("no new meaningful feedback")
    raise SystemExit(0)

try:
    old = open(LEDGER, encoding="utf-8").read()
except FileNotFoundError:
    old = "# 反馈台账（自动回填）\n\n| 抓取日期 | 来源 | 反馈要点 | 我的判断/处理 |\n|---|---|---|---|\n"

add = []
for num, title, url, body, kind, created in rows:
    if url in old:
        continue
    add.append("| %s | [#%s](%s) %s · %s | %s | 待人工判断 |"
               % (today, num, url, kind, clean(title, 40), body))

if not add:
    print("no new feedback to append")
    raise SystemExit(0)

with open(LEDGER, "w", encoding="utf-8") as f:
    f.write(old.rstrip() + "\n" + "\n".join(add) + "\n")
print("appended %d rows" % len(add))
