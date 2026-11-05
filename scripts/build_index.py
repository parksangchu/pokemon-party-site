"""parties/*.html을 읽어 index.html(목록 페이지)을 만든다.

사용: python3 -I build_index.py <사이트 루트>
"""
import html
import os
import re
import sys


def first(pattern, s, default=""):
    m = re.search(pattern, s, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else default


def chip(label, s):
    return first(rf'<div class="chip">{label}<b>(.*?)</b>', s)


def parse(path):
    s = open(path, encoding="utf-8").read()
    rank = chip("최종 순위", s)
    season = first(r'<div class="chip">시즌[^<]*<b>(M-\d+)', s)
    team = re.findall(r"<tr><td>\d</td><td><b>(.*?)</b>", s)
    return {
        "file": "parties/" + os.path.basename(path),
        "title": first(r"<h1>(.*?)</h1>", s, os.path.basename(path)),
        "rank": rank,
        "rank_num": int(re.sub(r"\D", "", rank) or 9999),
        "rate": chip("최종 레이트", s),
        "season": season,
        "season_num": int(re.sub(r"\D", "", season) or 0),
        "team": team,
        "source": first(r'<footer>원문: <a href="([^"]+)"', s) or "",
        "mtime": os.path.getmtime(path),
    }


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>포켓몬 챔피언스 상위 파티 한국어 정리</title>
<style>
:root{--bg:#f3f2f7;--surface:#fff;--ink:#1d1b29;--muted:#625e78;--line:#dddbe7;--accent:#5b3fd0;--accent-soft:#ece7ff}
@media (prefers-color-scheme: dark){:root{--bg:#14131b;--surface:#1d1b27;--ink:#ecebf4;--muted:#a29fb8;--line:#33303f;--accent:#a996ff;--accent-soft:#2a2442;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;padding:0 16px}
.wrap{max-width:980px;margin:0 auto;padding:40px 0 80px}
h1{font-size:clamp(24px,4vw,32px);margin:0 0 6px}
.lede{color:var(--muted);margin:0 0 20px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.filters input,.filters select{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
.filters input{flex:1;min-width:200px}
h2{font-size:20px;margin:32px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--ink)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;color:inherit;text-decoration:none}
.card:hover{border-color:var(--accent)}
.top{display:flex;gap:8px;align-items:baseline;margin-bottom:6px}
.rank{font-weight:800;font-size:20px;color:var(--accent)}
.rate{color:var(--muted);font-size:13px}
.title{font-weight:600;margin-bottom:8px}
.team{display:flex;flex-wrap:wrap;gap:4px}
.team span{background:var(--accent-soft);border-radius:6px;padding:2px 7px;font-size:12px}
.src{display:block;margin-top:8px;font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
footer{margin-top:40px;color:var(--muted);font-size:13px}
</style>
</head>
<body>
<div class="wrap">
<h1>포켓몬 챔피언스 상위 파티 한국어 정리</h1>
<p class="lede">일본 상위 플레이어의 구축 글을 한국어판 용어로 정리했습니다. 각 문서에 원문 링크가 있습니다. 총 __COUNT__개.</p>
<div class="filters">
  <input id="q" type="search" placeholder="포켓몬·작성자 검색 (예: 메가팬텀)">
  <select id="season"><option value="">모든 시즌</option>__SEASON_OPTIONS__</select>
</div>
__SECTIONS__
<footer>마지막 갱신: __UPDATED__ · 순위 데이터 출처 <a href="https://champs.pokedb.tokyo/">バトルデータベース チャンピオンズ</a></footer>
</div>
<script>
const q=document.getElementById('q'),se=document.getElementById('season');
function f(){const t=q.value.trim().toLowerCase(),s=se.value;
 document.querySelectorAll('section').forEach(sec=>{let n=0;
  sec.querySelectorAll('.card').forEach(c=>{const ok=(!s||c.dataset.season===s)&&(!t||c.dataset.text.includes(t));c.hidden=!ok;n+=ok});
  sec.hidden=!n;});}
q.addEventListener('input',f);se.addEventListener('change',f);
</script>
</body>
</html>
"""


def main():
    root = sys.argv[1]
    pdir = os.path.join(root, "parties")
    items = [parse(os.path.join(pdir, n)) for n in os.listdir(pdir) if n.endswith(".html")]
    items.sort(key=lambda x: (-x["season_num"], x["rank_num"]))
    seasons = sorted({x["season"] for x in items if x["season"]}, key=lambda s: -int(s[2:]))
    e = html.escape
    sections = []
    for season in seasons + ([""] if any(not x["season"] for x in items) else []):
        cards = []
        for x in (i for i in items if i["season"] == season):
            text = " ".join([x["title"], *x["team"]]).lower()
            cards.append(
                f'<a class="card" href="{e(x["file"])}" data-season="{e(season)}" data-text="{e(text)}">'
                f'<div class="top"><span class="rank">{e(x["rank"] or "-")}</span><span class="rate">{e(x["rate"])}</span></div>'
                f'<div class="title">{e(x["title"])}</div>'
                f'<div class="team">{"".join(f"<span>{e(t)}</span>" for t in x["team"])}</div>'
                f'<span class="src">{e(x["source"])}</span></a>')
        sections.append(f'<section><h2>시즌 {e(season or "기타")}</h2><div class="grid">{"".join(cards)}</div></section>')
    import datetime
    page = (PAGE.replace("__COUNT__", str(len(items)))
            .replace("__SEASON_OPTIONS__", "".join(f'<option value="{e(s)}">{e(s)}</option>' for s in seasons))
            .replace("__SECTIONS__", "\n".join(sections))
            .replace("__UPDATED__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(page)
    print(len(items))


if __name__ == "__main__":
    main()
