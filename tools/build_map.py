"""Build offline map from Natural Earth (public domain) and countries (ODbL)."""

import argparse, hashlib, json, math
from pathlib import Path
from shapely.geometry import shape, mapping

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--geometry", type=Path, required=True)
parser.add_argument("--countries", type=Path, required=True)
args = parser.parse_args()
expected = {
    "geometry": "239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255",
    "countries": "913e5d716f9dc6b59881ee23488d47f5fda52070d1a34cac5fa327c9e61d8f7c",
}
for key, digest in expected.items():
    if hashlib.sha256(getattr(args, key).read_bytes()).hexdigest() != digest:
        raise SystemExit(
            f"{key}: checksum differs from documented source snapshot; audit the new data before updating provenance."
        )
features = json.loads(args.geometry.read_text())["features"]
countries = json.loads(args.countries.read_text())
by_iso = {f["properties"]["ADM0_A3"]: f for f in features}
by_iso.update({f["properties"]["ISO_A3"]: f for f in features})
MENA = set(
    "MAR DZA TUN LBY EGY SDN ISR PSE JOR LBN SYR IRQ IRN SAU YEM OMN ARE QAT BHR KWT".split()
)
CENTRAL = set("KAZ UZB TKM KGZ TJK AFG".split())
rows = []
originals = {}
for c in countries:
    iso = c["cca3"]
    if not (c["unMember"] or iso in ("VAT", "PSE")):
        continue
    region = (
        "Oriente Médio e Norte da África"
        if iso in MENA
        else "Ásia Central"
        if iso in CENTRAL
        else "América do Norte"
        if iso in ("USA", "CAN")
        else "América Latina e Caribe"
        if c["region"] == "Americas"
        else "Europa"
        if c["region"] == "Europe"
        else "África Subsaariana"
        if c["region"] == "Africa"
        else "Ásia-Pacífico"
    )
    f = by_iso.get(iso)
    geom = shape(f["geometry"]) if f else None
    lat, lon = c["latlng"]
    if geom:
        originals[iso] = geom
        p = geom.representative_point()
        lon, lat = p.x, p.y
        geom = geom.simplify(0.025, preserve_topology=True)
    rows.append(
        dict(
            id=iso,
            name=c.get("translations", {}).get("por", c["name"])["common"],
            region=region,
            center=[lon, lat],
            area=geom.area if geom else 0,
            geometry=mapping(geom) if geom else None,
            neighbors=[],
        )
    )
shapes = originals
edges = []


def connect(a, b, kind):
    if a == b or a not in ids or b not in ids:
        return
    pair = sorted((a, b))
    if any(e["countries"] == pair for e in edges):
        return
    edges.append({"countries": pair, "kind": kind})
    ids[a]["neighbors"].append(b)
    ids[b]["neighbors"].append(a)


ids = {r["id"]: r for r in rows}
for i, a in enumerate(rows):
    for b in rows[i + 1 :]:
        if (
            a["id"] in shapes
            and b["id"] in shapes
            and shapes[a["id"]].distance(shapes[b["id"]]) < 0.00001
        ):
            connect(a["id"], b["id"], "land-simplified")
# Small states missing from this map scale, and selected strategic sea routes.
for pair in "VAT-ITA SMR-ITA MCO-FRA AND-ESP AND-FRA LIE-CHE LIE-AUT SGP-MYS BHR-SAU PSE-ISR PSE-JOR".split():
    connect(*pair.split("-"), "land-or-causeway")
for pair in "USA-RUS USA-JPN CAN-GBR GBR-FRA ESP-MAR ITA-TUN GRC-TUR EGY-SAU AUS-IDN AUS-NZL IDN-PNG PHL-IDN JPN-KOR IND-LKA MOZ-MDG BRA-CPV USA-CUB".split():
    connect(*pair.split("-"), "sea-gameplay")


# Attach isolated islands to the closest country: explicitly fictional game links.
def distance(a, b):
    lon1, lat1 = map(math.radians, a["center"])
    lon2, lat2 = map(math.radians, b["center"])
    return (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )


for a in rows:
    if not a["neighbors"]:
        b = min((b for b in rows if b != a), key=lambda b: distance(a, b))
        connect(a["id"], b["id"], "sea-gameplay")


# Ensure one connected playable graph using shortest inter-component sea link.
def component(start):
    seen = {start}
    todo = [start]
    while todo:
        for n in ids[todo.pop()]["neighbors"]:
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return seen


while len(component(rows[0]["id"])) < len(rows):
    seen = component(rows[0]["id"])
    a, b = min(
        ((a, b) for a in rows if a["id"] in seen for b in rows if b["id"] not in seen),
        key=lambda ab: distance(*ab),
    )
    connect(a["id"], b["id"], "sea-gameplay")
(ROOT / "src/war_lan/assets/world.json").write_text(
    json.dumps(
        {"countries": rows, "edges": edges, "provenance": expected}, ensure_ascii=False
    ),
    encoding="utf8",
)
print(len(rows), "countries,", len(edges), "edges")
