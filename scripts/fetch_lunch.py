#!/usr/bin/env python3
"""Fetch this week's Richland Elementary lunch entrées from YumYummi and write lunch.json.

Run weekly by .github/workflows/lunch.yml; the board reads lunch.json from its own origin.
Usage: fetch_lunch.py [YYYY-MM-DD]   (any date in the week wanted; default: today, Pacific;
a Saturday or Sunday rolls forward to the coming week, since that's when the weekly run fires)
"""
import json, re, sys, datetime as dt, urllib.request, urllib.parse
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

SITE = "https://smusd.yumyummi.com"
SCHOOL = {"sid": "16342", "sg": "richland-elementary", "mg": "L", "calendar": "weekly"}
SKIP = re.compile(r"milk|juice|cool tropics", re.I)          # drinks are listed as dishes; kids don't choose lunch by them
CODE = re.compile(r"\s*\(?\b\d{3}E[\w,/]*\)?|\s*\(E\)|\s+\d{3}$")  # kitchen recipe codes: "(216E)", "508E,M,H", "624E/H", "(E)", trailing "517"

def clean(name):
    name = CODE.sub("", re.sub(r"\s+", " ", name)).strip(" -,")
    return name.title() if name.isupper() else name                  # "BOSCO STICK 2" -> "Bosco Stick 2"

class Menu(HTMLParser):
    """Walk the weekly table: td.day columns; entrées are .dish links outside .groupcontainer (the fruit/veg rotation)."""
    def __init__(self):
        super().__init__(); self.days = {}; self.date = None; self.depth = 0; self.group_depth = None
        self.in_dish = None; self.dish_depth = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = a.get("class", ""); self.depth += 1
        if tag == "div" and "daydate" in cls and a.get("data-speech-text"):
            m = re.search(r"(\d{4}-\d{2}-\d{2})", a["data-speech-text"])
            if m and m.group(1) in self.days: self.date = None      # the page repeats the week in a hidden print table that can differ; keep the visible first one
            elif m: self.date = m.group(1); self.days[self.date] = []
        if "groupcontainer" in cls.split() and self.group_depth is None: self.group_depth = self.depth
        if tag == "a" and self.in_dish is None and self.group_depth is None and self.date and a.get("aria-label") and "dish" in (a.get("id") or ""):
            self.in_dish = a["aria-label"].strip(); self.dish_depth = self.depth
    def handle_endtag(self, tag):
        if self.in_dish is not None and self.depth == self.dish_depth:
            name = clean(self.in_dish)
            if name and not SKIP.search(name) and name not in self.days[self.date]: self.days[self.date].append(name)
            self.in_dish = None
        if self.group_depth is not None and self.depth == self.group_depth: self.group_depth = None
        if tag == "td": self.date = None; self.group_depth = None
        self.depth -= 1

def fetch(day):
    year, week, _ = day.isocalendar()
    body = urllib.parse.urlencode({"week": week, "year": year, **SCHOOL}).encode()
    req = urllib.request.Request(f"{SITE}/webapp/ajax-school-menus-weekly/", data=body, headers={
        "User-Agent": "Mozilla/5.0 (contributions-board lunch fetch)", "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{SITE}/webapp/{SCHOOL['sg']}/weekly/lunch"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read().decode("utf-8", "replace")

def main():
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    if day.weekday() >= 5: day += dt.timedelta(days=7 - day.weekday())      # weekend run: fetch the coming week
    html = fetch(day); p = Menu(); p.feed(html)
    monday = day - dt.timedelta(days=day.weekday())
    out = {"school": "Richland Elementary", "source": f"{SITE}/webapp/{SCHOOL['sg']}/weekly/lunch",
           "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "weekStart": monday.isoformat(),
           "days": {d: p.days[d] for d in sorted(p.days)}}
    if not any(out["days"].values()): sys.exit("no entrées parsed; the site markup may have changed")
    json.dump(out, open("lunch.json", "w"), indent=1, ensure_ascii=False); print(json.dumps(out, indent=1, ensure_ascii=False))

if __name__ == "__main__": main()
