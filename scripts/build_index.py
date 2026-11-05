"""parties/*.html을 읽어 index.html(목록 페이지)을 만든다.

사용: python3 -I build_index.py <사이트 루트>
"""
import datetime
import html
import json
import os
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pokemon_icons import icon_url  # noqa: E402


def first(pattern, s, default=""):
    m = re.search(pattern, s, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else default


def chip(label, s):
    return first(rf'<div class="chip">{label}<b>(.*?)</b>', s)


def split_title(title):
    """'삭쿠의 시즌 M-7 최종 1위 파티 "루카가브zzz"' -> ('삭쿠', '루카가브zzz')"""
    m = re.match(r"^(.*?)의 시즌 .*?파티\s*[—·:：-]?\s*(.*)$", title)
    if not m:
        return title, ""
    return m.group(1).strip(), m.group(2).strip().strip('"「」『』“”')


def parse(path):
    s = open(path, encoding="utf-8").read()
    rank = chip("최종 순위", s)
    season = first(r'<div class="chip">시즌[^<]*<b>(M-\d+)', s)
    team = re.findall(r"<tr><td>\d</td><td>(?:<img[^>]*>)?<b>(.*?)</b>", s)
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
:root{--bg:#f3f2f7;--surface:#fff;--ink:#1d1b29;--muted:#625e78;--line:#e4e2ec;--accent:#5b3fd0;--accent-soft:#ece7ff;--hover:#f7f5ff}
@media (prefers-color-scheme: dark){:root{--bg:#14131b;--surface:#1d1b27;--ink:#ecebf4;--muted:#a29fb8;--line:#2e2b3a;--accent:#a996ff;--accent-soft:#2a2442;--hover:#24212f;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;padding:0 12px}
.wrap{max-width:1100px;margin:0 auto;padding:28px 0 60px}
h1{font-size:clamp(20px,3vw,26px);margin:0 0 4px}
.lede{color:var(--muted);margin:0 0 16px;font-size:13px}
.bar{position:sticky;top:0;z-index:2;background:var(--bg);padding:8px 0;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.tabs{display:flex;gap:4px;flex-wrap:wrap}
.tabs button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:4px 12px;cursor:pointer}
.tabs button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.tabs small{opacity:.7;margin-left:3px}
.bar input,.bar select{font:inherit;font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
.bar input{flex:1;min-width:180px}
.active-mon{display:none;font-size:13px}
.active-mon.show{display:inline-flex;gap:6px;align-items:center}
.active-mon b{background:var(--accent-soft);border-radius:6px;padding:2px 8px}
.active-mon button{font:inherit;border:0;background:none;color:var(--muted);cursor:pointer}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th{white-space:nowrap;font-size:12px;font-weight:600;color:var(--muted);text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:0}
tbody tr{cursor:pointer}
tbody tr:hover{background:var(--hover)}
.rank{font-weight:800;color:var(--accent);white-space:nowrap}
.rate{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.season{color:var(--muted);font-size:12px;white-space:nowrap}
.who a{color:inherit;text-decoration:none;font-weight:600}
.who span{display:block;color:var(--muted);font-size:12px}
.team{display:flex;flex-wrap:wrap;gap:3px}
.team button{font:inherit;font-size:12px;border:0;background:var(--accent-soft);color:var(--ink);border-radius:5px;padding:1px 6px 1px 2px;cursor:pointer;display:inline-flex;align-items:center;gap:1px}
.team img{width:30px;height:30px;margin:-6px -2px -6px -4px;image-rendering:pixelated}
.team button:hover{outline:1px solid var(--accent)}
.src{color:var(--muted);font-size:12px;white-space:nowrap}
.new{font-size:11px;color:#fff;background:#e0567a;border-radius:4px;padding:0 5px;margin-left:4px;font-weight:600}
.empty{padding:30px;text-align:center;color:var(--muted)}
footer{margin-top:24px;color:var(--muted);font-size:12px}
footer a{color:inherit}
@media (max-width:720px){
 thead{display:none}
 table,tbody,tr,td{display:block}
 .bar input{flex-basis:100%;min-width:0}
 table{table-layout:fixed}
 tr{display:grid!important;grid-template-columns:auto auto 1fr;gap:2px 8px;padding:8px 10px;border-bottom:1px solid var(--line)}
 td{border:0;padding:0;min-width:0}
 td.who{grid-column:1/-1}
 td.team-cell{grid-column:1/-1}
 td.src{display:none}
}
</style>
</head>
<body>
<div class="wrap">
<h1>포켓몬 챔피언스 상위 파티 한국어 정리</h1>
<p class="lede">일본 상위 플레이어의 구축 글을 한국어판 용어로 정리했습니다. 총 __COUNT__개 · 행을 누르면 문서, 포켓몬을 누르면 그 포켓몬이 든 파티만 봅니다.</p>
<div class="bar">
  <div class="tabs" id="tabs">__TABS__</div>
  <input id="q" type="search" placeholder="포켓몬·작성자 검색">
  <select id="sort"><option value="rank">순위순</option><option value="new">최근 추가순</option><option value="rate">레이트순</option></select>
  <span class="active-mon" id="mon"><b></b><button type="button" title="해제">✕</button></span>
</div>
<table>
<thead><tr><th>순위</th><th>레이트</th><th>시즌</th><th>작성자 · 파티 이름</th><th>파티</th><th>원문</th></tr></thead>
<tbody id="rows">__ROWS__</tbody>
</table>
<div class="empty" id="empty" hidden>조건에 맞는 파티가 없습니다.</div>
<footer>마지막 갱신: __UPDATED__ · 순위 데이터 출처 <a href="https://champs.pokedb.tokyo/">バトルデータベース チャンピオンズ</a></footer>
</div>
<script>
const rows=[...document.querySelectorAll('#rows tr')],tbody=document.getElementById('rows');
const q=document.getElementById('q'),sort=document.getElementById('sort'),mon=document.getElementById('mon');
let season=document.querySelector('#tabs .on')?.dataset.season||'',pick='';
function apply(){
 const t=q.value.trim().toLowerCase();let n=0;
 const key={rank:r=>[-+r.dataset.season.replace(/\\D/g,''),+r.dataset.rank],new:r=>[-+r.dataset.added],rate:r=>[-+r.dataset.rate]}[sort.value];
 rows.sort((a,b)=>{const x=key(a),y=key(b);for(let i=0;i<x.length;i++)if(x[i]!==y[i])return x[i]-y[i];return 0}).forEach(r=>tbody.appendChild(r));
 rows.forEach(r=>{const ok=(!season||r.dataset.season===season)&&(!t||r.dataset.text.includes(t))&&(!pick||r.dataset.team.split('|').includes(pick));r.hidden=!ok;n+=ok});
 document.getElementById('empty').hidden=!!n;
 mon.classList.toggle('show',!!pick);mon.querySelector('b').textContent=pick;
}
document.getElementById('tabs').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
 document.querySelectorAll('#tabs button').forEach(x=>x.classList.toggle('on',x===b));season=b.dataset.season;apply()});
tbody.addEventListener('click',e=>{const b=e.target.closest('.team button');
 if(b){e.stopPropagation();pick=b.dataset.mon;apply();return}
 if(e.target.closest('a'))return;const r=e.target.closest('tr');if(r)location.href=r.dataset.href});
mon.querySelector('button').addEventListener('click',()=>{pick='';apply()});
q.addEventListener('input',apply);sort.addEventListener('change',apply);apply();
</script>
</body>
</html>
"""


def mon_chip(name):
    url = icon_url(name)
    img = f'<img src="{html.escape(url)}" alt="" loading="lazy">' if url else ""
    return f'<button type="button" data-mon="{html.escape(name)}">{img}{html.escape(name)}</button>'


def added_times(root):
    """state/done.json에 기록된 처리 시각(없으면 파일 수정 시각)."""
    try:
        done = json.load(open(os.path.join(root, "state", "done.json"), encoding="utf-8"))
    except FileNotFoundError:
        return {}
    out = {}
    for v in done.values():
        if v.get("file") and v.get("at"):
            out[v["file"]] = datetime.datetime.fromisoformat(v["at"]).timestamp()
    return out


def main():
    root = sys.argv[1]
    pdir = os.path.join(root, "parties")
    items = [parse(os.path.join(pdir, n)) for n in os.listdir(pdir) if n.endswith(".html")]
    added = added_times(root)
    for x in items:
        x["added"] = added.get(x["file"], x["mtime"])
    items.sort(key=lambda x: (-x["season_num"], x["rank_num"]))
    seasons = sorted({x["season"] for x in items if x["season"]}, key=lambda s: -int(s[2:]))
    e = html.escape
    now = datetime.datetime.now()
    tabs = [f'<button type="button" data-season="" class="{"" if seasons else "on"}">전체<small>{len(items)}</small></button>']
    for i, sn in enumerate(seasons):
        cnt = sum(1 for x in items if x["season"] == sn)
        tabs.append(f'<button type="button" data-season="{e(sn)}" class="{"on" if i == 0 else ""}">{e(sn)}<small>{cnt}</small></button>')
    rows = []
    for x in items:
        who, sub = split_title(x["title"])
        text = " ".join([x["title"], *x["team"]]).lower()
        is_new = (now.timestamp() - x["added"]) < 2 * 86400
        host = urlparse(x["source"]).netloc.replace("www.", "") if x["source"] else ""
        rate = re.sub(r"[^\d.]", "", x["rate"]) or "0"
        rows.append(
            f'<tr data-href="{e(x["file"])}" data-season="{e(x["season"])}" data-rank="{x["rank_num"]}" '
            f'data-rate="{e(rate)}" data-added="{int(x["added"])}" data-text="{e(text)}" data-team="{e("|".join(x["team"]))}">'
            f'<td class="rank">{e(x["rank"] or "-")}</td><td class="rate">{e(x["rate"])}</td>'
            f'<td class="season">{e(x["season"])}</td>'
            f'<td class="who"><a href="{e(x["file"])}">{e(who)}</a>{"<em class=new>NEW</em>" if is_new else ""}'
            f'{f"<span>{e(sub)}</span>" if sub else ""}</td>'
            f'<td class="team-cell"><div class="team">{"".join(mon_chip(t) for t in x["team"])}</div></td>'
            f'<td class="src">{e(host)}</td></tr>')
    page = (PAGE.replace("__COUNT__", str(len(items)))
            .replace("__TABS__", "".join(tabs))
            .replace("__ROWS__", "\n".join(rows))
            .replace("__UPDATED__", now.strftime("%Y-%m-%d %H:%M")))
    open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(page)
    print(len(items))


if __name__ == "__main__":
    main()
