"""pokedb 트레이너 목록에서 아직 처리하지 않은 구축 글 후보를 뽑는다.

사용: python3 -I fetch_candidates.py <state/done.json> [--max-rank 200] [--seasons 7,8 | --min-season 5] [--current-min-rate 2000]
--current-min-rate를 주면 가장 최근 시즌(진행 중)은 순위 대신 레이트 기준으로 고르고,
pokedb에 아직 없는 글을 pokesol·note 최신 글에서도 찾는다(제목의 시즌·레이트·순위로 판단).
--seasons를 생략하면 --min-season 이후 모든 시즌을, 둘 다 생략하면 최근 시즌 2개(진행 중 + 직전)를 본다.
본문을 받을 수 없는 링크(X, YouTube, 네이버 카페)는 후보에서 뺀다.
출력: 후보 JSON 배열(stdout). 순위가 높은 글부터.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_article import turbo_stream  # noqa: E402

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


def parse_cards(page, with_article=True):
    for card in page.split('<article class="trainer-card">')[1:]:
        rank = re.search(r'data-rank="(\d+)"', card)
        art = re.search(
            r'trainer-card-team__article">\s*<a href="([^"]+)"[^>]*>.*?<span>(.*?)</span>\s*</a>',
            card, re.S)
        if not rank or (with_article and not art):
            continue
        rate = re.search(r'rating-integer">(\d+)</span><span class="rating-decimal">([.\d]*)', card)
        yield {
            "rank": int(rank.group(1)),
            "rate": (rate.group(1) + rate.group(2)) if rate else "",
            "trainer": text(re.search(r'trainer-card-name">(.*?)</div>', card, re.S).group(1)),
            "team": [text(x) for x in re.findall(r'trainer-card-team__pokemon-name">(.*?)</div>', card, re.S)],
            "url": html.unescape(art.group(1)) if art else "",
            "title": text(art.group(2)) if art else "",
        }


def title_score(title):
    """제목에 적힌 레이트(최고·현재·달성 등)와 순위를 읽는다. 없으면 None."""
    rates = [int(x) for x in re.findall(r"(?:R|レート|レーティング|最高|瞬間|現在)\s*:?\s*(\d{4})", title)
             + re.findall(r"(\d{4})\s*(?:達成|到達|帯)", title) if 1000 <= int(x) <= 3000]
    ranks = [int(x.replace(",", "")) for x in re.findall(r"(\d[\d,]*)\s*位", title)]
    return (max(rates) if rates else None), (min(ranks) if ranks else None)


def other_sources(season, min_rate, max_rank=1000):
    """진행 중인 시즌의 싱글 구축 글을 pokesol·note 최신 글에서 찾는다.
    시즌 중이므로 '最終'이 붙은 글(지난 시즌 결과)은 빼고, 제목의 레이트나 순위가 기준을 넘는 글만 남긴다."""
    found = []

    def add(source, url, title, trainer, season_ok):
        t = unicodedata.normalize("NFKC", title)
        if not season_ok(t) or "最終" in t or "ダブル" in t:
            return
        rate, rank = title_score(t)
        if (rate or 0) >= min_rate or (rank or max_rank + 1) <= max_rank:
            found.append({"season": season, "rank": rank or 9999, "rate": str(rate or ""), "trainer": trainer,
                          "team": [], "url": url, "title": title, "source": source})

    in_title = re.compile(rf"M\s*[-ー]?\s*{season}(?!\d)")
    for page_no in range(1, 6):
        d = turbo_stream(get(f"https://pokesol.app/?tab=latest&category=team&page={page_no}"))
        for x in d["loaderData"]["routes/_index"]["articles"]:
            if x.get("battleFormat") == "single":
                add("pokesol", f"https://pokesol.app/u/{x['author']['username']}/articles/{x['id']}", x["title"],
                    x["author"].get("displayName") or x["author"]["username"],
                    lambda t, x=x: x.get("season") == f"m-{season}" or bool(in_title.search(t)))
        time.sleep(1)
    q = urllib.parse.quote("ポケモンチャンピオンズ")
    for start in range(0, 100, 20):
        d = json.loads(get(f"https://note.com/api/v3/searches?context=note&q={q}&size=20&start={start}&sort=new"))
        for x in d["data"]["notes"]["contents"]:
            add("note", f"https://note.com/{x['user']['urlname']}/n/{x['key']}", x["name"],
                x["user"].get("nickname") or x["user"]["urlname"], lambda t: bool(in_title.search(t)))
        time.sleep(1)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("done")
    ap.add_argument("--max-rank", type=int, default=200)
    ap.add_argument("--seasons", default="")
    ap.add_argument("--min-season", type=int, default=0)
    ap.add_argument("--current-min-rate", type=float, default=0)
    a = ap.parse_args()

    try:
        done = json.load(open(a.done, encoding="utf-8"))
    except FileNotFoundError:
        done = {}

    seasons = [int(x) for x in a.seasons.split(",") if x] or latest_seasons(min_season=a.min_season)
    out, seen = [], set()
    current = max(seasons) if a.current_min_rate else None
    for season in seasons:
        # 진행 중인 시즌은 순위가 계속 바뀌므로 레이트가 기준 이상인 사람의 글을 본다.
        ok = (lambda c: float(c["rate"] or 0) >= a.current_min_rate) if season == current else \
             (lambda c: c["rank"] <= a.max_rank)
        page_no = 1
        while True:
            final = []
            page = get(f"{BASE}/trainer/list?season={season}&rule=0&with_team=1&page={page_no}", final)
            # 데이터가 아직 없는 시즌(막 시작한 시즌)은 직전 시즌으로 리다이렉트된다.
            if "fallback=1" in final[0]:
                break
            cards = list(parse_cards(page))
            for c in cards:
                if not ok(c) or c["url"] in seen or SKIP_HOSTS.match(c["url"]):
                    continue
                seen.add(c["url"])
                entry = done.get(c["url"])
                if entry and (entry.get("status") == "ok" or entry.get("tries", 0) >= 3):
                    continue
                out.append({"season": season, **c})
            # 100명씩 순위순으로 나뉜 페이지. 마지막 사람이 기준 밖이거나 다음 페이지가 없으면 멈춘다.
            last = list(parse_cards(page, with_article=False))[-1:]
            if not last or not ok(last[0]) or f"page={page_no + 1}" not in page:
                break
            page_no += 1
            time.sleep(1)
    if current:
        for c in other_sources(current, a.current_min_rate):
            entry = done.get(c["url"])
            if c["url"] in seen or (entry and (entry.get("status") == "ok" or entry.get("tries", 0) >= 3)):
                continue
            seen.add(c["url"])
            out.append(c)
    out.sort(key=lambda c: (-c["season"], c["rank"]))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
