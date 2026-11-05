"""pokedb 트레이너 목록에서 아직 처리하지 않은 구축 글 후보를 뽑는다.

사용: python3 -I fetch_candidates.py <state/done.json> [--max-rank 200] [--seasons 7,8 | --min-season 5]
--seasons를 생략하면 --min-season 이후 모든 시즌을, 둘 다 생략하면 최근 시즌 2개(진행 중 + 직전)를 본다.
본문을 받을 수 없는 링크(X, YouTube, 네이버 카페)는 후보에서 뺀다.
출력: 후보 JSON 배열(stdout). 순위가 높은 글부터.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.request

BASE = "https://champs.pokedb.tokyo"
UA = "Mozilla/5.0 (pokemon-party-site personal translator)"
# 로그인이 필요하거나 영상이라 본문을 받을 수 없는 곳
SKIP_HOSTS = re.compile(r"^https?://([\w.]+\.)?(x\.com|twitter\.com|youtube\.com|youtu\.be|cafe\.naver\.com)/")


def get(url, final=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if final is not None:
            final.append(r.geturl())
        return r.read().decode("utf-8", "replace")


def latest_seasons(n=2, min_season=0):
    s = get(f"{BASE}/trainer/list?rule=0&with_team=1")
    nums = sorted({int(x) for x in re.findall(r"シーズンM-(\d+)", s)}, reverse=True)
    return [x for x in nums if x >= min_season] if min_season else nums[:n]


def text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_cards(page):
    for card in page.split('<article class="trainer-card">')[1:]:
        rank = re.search(r'data-rank="(\d+)"', card)
        art = re.search(
            r'trainer-card-team__article">\s*<a href="([^"]+)"[^>]*>.*?<span>(.*?)</span>\s*</a>',
            card, re.S)
        if not rank or not art:
            continue
        rate = re.search(r'rating-integer">(\d+)</span><span class="rating-decimal">([.\d]*)', card)
        yield {
            "rank": int(rank.group(1)),
            "rate": (rate.group(1) + rate.group(2)) if rate else "",
            "trainer": text(re.search(r'trainer-card-name">(.*?)</div>', card, re.S).group(1)),
            "team": [text(x) for x in re.findall(r'trainer-card-team__pokemon-name">(.*?)</div>', card, re.S)],
            "url": html.unescape(art.group(1)),
            "title": text(art.group(2)),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("done")
    ap.add_argument("--max-rank", type=int, default=200)
    ap.add_argument("--seasons", default="")
    ap.add_argument("--min-season", type=int, default=0)
    a = ap.parse_args()

    try:
        done = json.load(open(a.done, encoding="utf-8"))
    except FileNotFoundError:
        done = {}

    seasons = [int(x) for x in a.seasons.split(",") if x] or latest_seasons(min_season=a.min_season)
    out, seen = [], set()
    for season in seasons:
        page_no = 1
        while True:
            final = []
            page = get(f"{BASE}/trainer/list?season={season}&rule=0&with_team=1&page={page_no}", final)
            # 데이터가 아직 없는 시즌(막 시작한 시즌)은 직전 시즌으로 리다이렉트된다.
            if "fallback=1" in final[0]:
                break
            cards = list(parse_cards(page))
            ranks = [int(r) for r in re.findall(r'data-rank="(\d+)"', page)]
            for c in cards:
                if c["rank"] > a.max_rank or c["url"] in seen or SKIP_HOSTS.match(c["url"]):
                    continue
                seen.add(c["url"])
                entry = done.get(c["url"])
                if entry and (entry.get("status") == "ok" or entry.get("tries", 0) >= 3):
                    continue
                out.append({"season": season, **c})
            # 100명씩 나뉜 페이지. 마지막 순위가 기준을 넘거나 다음 페이지가 없으면 멈춘다.
            if not ranks or max(ranks) > a.max_rank or f"page={page_no + 1}" not in page:
                break
            page_no += 1
            time.sleep(1)
    out.sort(key=lambda c: (-c["season"], c["rank"]))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
