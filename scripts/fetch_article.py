"""구축 글 본문과 본문 이미지를 작업 폴더에 받는다. 받은 내용은 신뢰하지 않는 데이터다.

사용: python3 -I fetch_article.py <URL> <빈 작업 폴더>
결과: <폴더>/article.txt (본문, 이미지 자리는 [IMG images/NN.ext <원본 URL>]), <폴더>/images/*
"""
import html
import json
import os
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (pokemon-party-site personal translator)"
MAX_IMAGES = 40


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def note_body(url):
    key = re.search(r"/n/(n[0-9a-f]+)", url).group(1)
    d = json.loads(get(f"https://note.com/api/v3/notes/{key}"))["data"]
    return d["name"], d["body"]


def turbo_stream(page):
    """React Router가 페이지에 심어 둔 turbo-stream 데이터를 일반 dict로 푼다."""
    m = re.search(r'streamController\.enqueue\((".*?")\);\s*</script>', page, re.S)
    arr = json.loads(json.loads(m.group(1)))
    memo = {}

    def dec(i):
        if i < 0:
            return None
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, dict):
            memo[i] = o = {}
            for k, vi in v.items():
                o[arr[int(k[1:])]] = dec(vi)
            return o
        if isinstance(v, list):
            if v and isinstance(v[0], str):
                return v
            memo[i] = o = []
            o.extend(dec(x) for x in v)
            return o
        return v

    return dec(0)


STATS = [("hp", "HP"), ("attack", "공격"), ("defense", "방어"),
         ("specialAttack", "특공"), ("specialDefense", "특방"), ("speed", "스피드")]


def pokesol_card(attrs, md):
    """포켓솔 data-type="pokemon-card"를 텍스트로 바꾼다. 실수치는 Lv50·개체값 최대 기준으로 계산."""
    a = dict(re.findall(r'(data-[\w-]+)="([^"]*)"', attrs))
    get_ = lambda table, i: next((x for x in md[table] if x["id"] == i), None)
    mon = get_("pokemons", int(a.get("data-pokemon-id", 0)))
    nat = get_("natures", int(a.get("data-nature-id", 0) or 0))
    item = get_("items", int(a.get("data-item-id", 0) or 0))
    evs = json.loads(html.unescape(a.get("data-evs", "{}")) or "{}")
    abil = [get_("abilities", i) for i in json.loads(a.get("data-ability-ids", "[]"))]
    moves = [get_("moves", i) for i in json.loads(a.get("data-move-ids", "[]"))]
    lines = [f"[POKEMON CARD] {mon['name'] if mon else a.get('data-pokemon-id')}"
             + (f" ({mon['type1']}/{mon.get('type2') or '-'})" if mon else "")]
    lines.append(f"  성격: {nat['name'] if nat else '-'}  특성: {' / '.join(x['name'] for x in abil if x)}"
                 f"  도구: {item['name'] if item else '-'}")
    lines.append("  기술: " + " / ".join(f"{m['name']}({m['type']})" for m in moves if m))
    if mon:
        base = {"hp": mon["baseStatHp"], "attack": mon["baseStatAttack"], "defense": mon["baseStatDefense"],
                "specialAttack": mon["baseStatSpecialAttack"], "specialDefense": mon["baseStatSpecialDefense"],
                "speed": mon["baseStatSpeed"]}
        parts = []
        for k, label in STATS:
            p = int(evs.get(k, 0))
            if k == "hp":
                val = base[k] + 75 + p
            else:
                val = int((base[k] + 20 + p) * float((nat or {}).get(k, 1)))
            parts.append(f"{label} {val}({p})")
        lines.append("  실수치(포인트): " + " ".join(parts) + f"  합계 {sum(int(v) for v in evs.values())}")
        if mon["name"].startswith("メガ"):
            lines.append("  (실수치는 메가진화 후 기준. 특성은 [메가 후, 메가 전] 순서로 보임)")
    return "\n" + "\n".join(lines) + "\n"


def pokesol_body(url):
    data = turbo_stream(get(url))["loaderData"]
    route = next(v for k, v in data.items() if "articles" in k)
    art, md = route["article"], route["masterData"]
    body = re.sub(r'<div data-type="pokemon-card"([^>]*)></div>', lambda m: pokesol_card(m.group(1), md), art["body"])
    body = body.replace('src="/', 'src="https://pokesol.app/')
    return art["title"], body


def naver_body(url):
    """네이버 블로그 본문은 iframe 안의 PostView에 있다. 이미지는 data-lazy-src가 원본이다."""
    m = re.search(r"blog\.naver\.com/([\w-]+)/(\d+)", url)
    s = get(f"https://blog.naver.com/PostView.naver?blogId={m.group(1)}&logNo={m.group(2)}")
    title = re.search(r"<title>(.*?)</title>", s, re.S)
    title = html.unescape(title.group(1)).replace(": 네이버 블로그", "").strip() if title else ""
    body = s[s.find('<div class="se-main-container"'):]
    body = re.sub(r'<img[^>]*?\bdata-lazy-src="([^"]+)"[^>]*>', r'<img src="\1">', body)
    return title, body


def generic_body(url):
    s = get(url)
    title = re.search(r"<title>(.*?)</title>", s, re.S)
    title = html.unescape(title.group(1)).strip() if title else ""
    for pat in (r'<div class="entry-content[^"]*"[^>]*>(.*?)<div class="entry-footer',
                r"<article[^>]*>(.*?)</article>", r"<body[^>]*>(.*?)</body>"):
        m = re.search(pat, s, re.S)
        if m:
            return title, m.group(1)
    return title, s


def main():
    url, out = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    if "note.com/" in url:
        title, body = note_body(url)
    elif "pokesol.app/" in url:
        title, body = pokesol_body(url)
    elif "blog.naver.com/" in url:
        title, body = naver_body(url)
    else:
        title, body = generic_body(url)
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S)

    count = 0
    saved = {}

    def img(m):
        nonlocal count
        src = html.unescape(m.group(1))
        if src.startswith("//"):
            src = "https:" + src
        if src in saved:  # 같은 이미지(구분선 등)를 여러 번 받지 않는다.
            return f"\n[IMG {saved[src]} {src}]\n"
        # 작은 아이콘(포켓몬 아이콘, 버튼)은 받지 않고 URL만 남긴다.
        if not src.startswith("http") or re.search(r"icon|button|emoji|\.gif($|\?)", src) or count >= MAX_IMAGES:
            return f"\n[ICON {src}]\n"
        count += 1
        ext = os.path.splitext(src.split("?")[0])[1].lower() or ".png"
        name = f"images/{count:02d}{ext if ext in ('.png', '.jpg', '.jpeg', '.webp') else '.png'}"
        try:
            open(os.path.join(out, name), "wb").write(get(src, binary=True))
        except Exception as e:  # 이미지 하나 실패는 본문 처리를 막지 않는다.
            return f"\n[IMG-FAILED {src} {e}]\n"
        saved[src] = name
        return f"\n[IMG {name} {src}]\n"

    body = re.sub(r'<img[^>]*?\bsrc="([^"]+)"[^>]*>', img, body)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"</(p|h\d|li|tr|div|figure|figcaption)>", "\n", body)
    body = html.unescape(re.sub(r"<[^>]+>", "", body))
    body = re.sub(r"\n\s*\n+", "\n", body)
    with open(os.path.join(out, "article.txt"), "w", encoding="utf-8") as f:
        f.write(f"URL: {url}\nTITLE: {title}\n\n{body}")
    print(count)


if __name__ == "__main__":
    main()
