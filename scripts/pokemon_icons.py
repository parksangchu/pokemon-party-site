"""한국어 포켓몬 이름을 PokeAPI 스프라이트 URL로 바꾸고, 파티 문서에 아이콘을 넣는다.

대응표 만들기(처음 한 번): python3 -I pokemon_icons.py build <PokeAPI csv 폴더> <사이트 루트>
  csv: https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv 의 pokemon_species_names.csv, pokemon.csv
파티 문서에 아이콘 넣기:   python3 -I pokemon_icons.py inject <사이트 루트>
"""
import csv
import json
import os
import re
import sys

SPRITE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{}.png"
REGION = {"가라르": "galar", "알로라": "alola", "히스이": "hisui", "팔데아": "paldea"}
ROTOM = {"히트": "heat", "워시": "wash", "프로스트": "frost", "스핀": "fan", "커트": "mow"}
_table = None


def table(root=None):
    global _table
    if _table is None:
        root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "data", "pokemon_ids.json"), encoding="utf-8") as f:
            _table = json.load(f)
    return _table


def pokemon_id(name):
    """'메가리자몽Y ♂', '가라르 야도킹', '한카리아스 (수컷)' 같은 표기를 PokeAPI pokemon id로. 모르면 None."""
    t = table()
    species, ids = t["species"], t["ids"]
    n = re.sub(r"\s*\(.*?\)|[♂♀]", "", name).strip()
    if n in species:
        return ids.get(species[n])
    m = re.match(r"^(가라르|알로라|히스이|팔데아)\s*(.+)$", n)
    if m and m.group(2) in species:
        base = species[m.group(2)]
        return ids.get(f"{base}-{REGION[m.group(1)]}") or ids.get(base)
    m = re.match(r"^(히트|워시|프로스트|스핀|커트)로토무$", n)
    if m:
        return ids.get(f"rotom-{ROTOM[m.group(1)]}")
    m = re.match(r"^메가(.+?)([XYZ])?$", n)
    if m and m.group(1) in species:
        base = species[m.group(1)]
        suffix = f"-mega-{m.group(2).lower()}" if m.group(2) else "-mega"
        return ids.get(base + suffix) or ids.get(base + "-mega") or ids.get(base)
    return None


def icon_url(name):
    i = pokemon_id(name)
    return SPRITE.format(i) if i else ""


def build(csv_dir, root):
    with open(os.path.join(csv_dir, "pokemon_species_names.csv"), encoding="utf-8") as f:
        ko = {r["pokemon_species_id"]: r["name"] for r in csv.DictReader(f) if r["local_language_id"] == "3"}
    with open(os.path.join(csv_dir, "pokemon.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ident = {r["species_id"]: r["identifier"] for r in rows if r["is_default"] == "1"}
    out = {"species": {name: ident[sid] for sid, name in ko.items() if sid in ident},
           "ids": {r["identifier"]: int(r["id"]) for r in rows}}
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    with open(os.path.join(root, "data", "pokemon_ids.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(len(out["species"]), len(out["ids"]))


ICON_CSS = ("<style id=\"pkicon-css\">.pkicon{width:40px;height:40px;image-rendering:pixelated;"
            "vertical-align:middle;margin:-8px 2px -8px -6px}"
            ".mon-head .pkicon{width:56px;height:56px;margin:-12px 4px -12px -8px}</style>")


def inject(root):
    """파티 문서의 '한눈에 보기' 표와 개체 카드 제목에 아이콘을 넣는다. 이미 넣은 문서는 건너뛴다."""
    pdir = os.path.join(root, "parties")
    changed, missing = 0, set()
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".html"):
            continue
        path = os.path.join(pdir, fn)
        with open(path, encoding="utf-8") as f:
            s = f.read()
        if 'id="pkicon-css"' in s:
            continue

        def img(name):
            url = icon_url(name)
            if not url:
                missing.add(name)
                return ""
            return f'<img class="pkicon" src="{url}" alt="" loading="lazy">'

        s = re.sub(r"(<tr><td>\d</td><td>)(<b>)(.*?)(</b>)",
                   lambda m: m.group(1) + img(m.group(3)) + m.group(2) + m.group(3) + m.group(4), s)
        # 개체 카드 제목: <div class="mon-head"> 안의 첫 <h2>/<h3>
        s = re.sub(r'(<div class="mon-head">.*?<h[23][^>]*>)([^<]+)',
                   lambda m: m.group(1) + img(m.group(2).split("@")[0].strip()) + m.group(2), s, flags=re.S)
        s = s.replace("</head>", ICON_CSS + "\n</head>", 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        changed += 1
    print(f"injected {changed}", f"missing {sorted(missing)}" if missing else "")


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3])
    else:
        inject(sys.argv[2])
