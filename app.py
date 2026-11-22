"""Smart Planner - AI Crowd-Aware Outing & Budget Planner (Flask + SQLite)
Crowd data priority: Live CCTV (last 15 min) > BestTime hourly forecast > static estimate
"""
import itertools, json, math, sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, g

DB = "smart_planner.db"
app = Flask(__name__)

FARES = {"Chennai": {"base": 25, "km": 15}, "Coimbatore": {"base": 20, "km": 18}}
SLOTS = ["weekday_morning", "weekday_evening", "weekend_morning", "weekend_evening"]
MAX_HOP_KM = 8.0
LIVE_TTL_MIN = 15                                   # CCTV readings older than this are ignored
SLOT_HOURS = {"morning": range(9, 13), "evening": range(17, 21)}   # 9am-12pm, 5pm-8pm

# (id, city, name, area, category, tags, entry, food, hrs, capacity, lat, lng, transit, [wd_m, wd_e, we_m, we_e])
# The last list is the STATIC FALLBACK, used only when BestTime has no data for the venue.
SEED = [
 ("CHN_01","Chennai","Elliot's Beach (Bessy) & Street Food","Besant Nagar","Beach & Street Food","Friends,Couples,Family,Solo",0,220,2.5,500,13.0002,80.2668,"Thiruvanmiyur MRTS / Besant Nagar Bus Terminus",[20,60,45,92]),
 ("CHN_02","Chennai","Semmozhi Poonga Botanical Garden","Teynampet","Nature & Park","Couples,Family,Solo",20,100,1.5,200,13.0519,80.2518,"AG-DMS Metro Station (500m)",[25,45,55,75]),
 ("CHN_03","Chennai","VR Chennai Mall & Food Box","Anna Nagar West","Mall & Dining","Friends,Couples,Family",0,450,3.0,800,13.0811,80.1972,"Thirumangalam Metro Station (600m)",[20,58,40,90]),
 ("CHN_04","Chennai","Anna Nagar Tower Park","Anna Nagar","Park & Chill","Friends,Family,Solo",10,150,1.5,250,13.0853,80.2101,"Anna Nagar Tower Metro Station (200m)",[30,55,50,80]),
 ("CHN_05","Chennai","Government Museum & Connemara Complex","Egmore","Heritage & Museum","Solo,Friends,Family",20,120,2.5,300,13.0715,80.2569,"Egmore Metro / Railway Station (800m)",[20,30,45,50]),
 ("CHN_06","Chennai","Express Avenue (EA) Mall & Escape Cinemas","Royapettah","Mall, Movie & Gaming","Friends,Couples,Family",0,550,3.5,900,13.0587,80.2641,"LIC Metro Station (700m)",[25,65,45,94]),
 ("CHN_07","Chennai","Marina Beach Lighthouse & Sundal Walk","Mylapore","Beach & Landmark","Friends,Family,Solo",20,130,2.0,600,13.0398,80.2794,"Light House MRTS Station (300m)",[25,65,50,95]),
 ("CHN_08","Chennai","Sowcarpet Mint Street Food Walk","George Town","Street Food Trail","Friends,Solo",0,250,2.0,350,13.0954,80.2785,"High Court / Mannadi Metro Station",[35,78,40,95]),
 ("CHN_09","Chennai","Phoenix Marketcity & Palladium","Velachery","Mall & Entertainment","Friends,Couples,Family",0,650,3.5,1000,12.9915,80.2165,"Velachery MRTS / Guindy Metro + Feeder",[22,62,48,96]),
 ("CHN_10","Chennai","Guindy National Park & Children's Park","Guindy","Nature & Wildlife","Family,Couples,Solo",30,100,2.0,250,13.0067,80.2376,"Guindy Metro / MRTS (1.2 km)",[20,35,60,65]),
 ("CHN_11","Chennai","DakshinaChitra Heritage Museum","Muttukadu (ECR)","Culture & Art","Family,Couples,Friends",175,250,3.0,300,12.8235,80.2427,"ECR Bus 588 / 109 from Thiruvanmiyur",[18,25,55,60]),
 ("CHN_12","Chennai","Board Room Cafe & Gaming Lounge","Mylapore","Indoor Games & Cafe","Friends,Couples",150,300,2.5,80,13.0368,80.2676,"Mylapore MRTS / Thousand Lights Metro",[15,50,35,78]),
 ("CHN_13","Chennai","Nexus Vijaya Mall","Vadapalani","Mall & Dining","Friends,Couples,Family",0,480,3.0,800,13.0498937,80.2095018,"Vadapalani Metro Station (400m)",[18,55,32,95]),
 ("CHN_14","Chennai","The Marina Mall (OMR)","Egattur, OMR","Mall & Entertainment","Friends,Couples,Family",0,420,3.0,600,12.8357358,80.2289203,"OMR Bus Routes (Egattur Stop)",[15,50,25,88]),
 ("CBE_01","Coimbatore","Brookefields Mall & Food Court","RS Puram","Mall & Dining","Friends,Couples,Family",0,450,3.0,700,11.0087,76.9600,"RS Puram / Gandhipuram Town Bus",[20,60,45,92]),
 ("CBE_02","Coimbatore","VOC Park & Zoo","Gopalapuram","Park & Family Spot","Family,Solo,Friends",20,120,2.0,350,11.0045,76.9698,"Gandhipuram Central Bus Stand (1.5 km)",[25,50,60,82]),
 ("CBE_03","Coimbatore","Ukkadam Valankulam Lakefront Walk","Ukkadam","Lakefront & Street Snacks","Friends,Couples,Family,Solo",0,150,2.0,400,10.9896,76.9628,"Ukkadam Bus Terminus (400m)",[20,58,40,88]),
 ("CBE_04","Coimbatore","Prozone Mall & Entertainment Zone","Sivanandapuram","Mall & Gaming","Friends,Couples,Family",0,500,3.5,850,11.0558,76.9942,"Saravanampatti / Ganapathy Bus Route",[18,55,42,90]),
 ("CBE_05","Coimbatore","GD Naidu Car & Science Museum","Avinashi Road","Museum & Tech","Friends,Family,Solo",75,150,2.0,200,11.0116,76.9815,"Lakshmi Mills Bus Stop (300m)",[15,30,45,55]),
 ("CBE_06","Coimbatore","Race Course Walking Trail & Cafes","Race Course","Chill Walk & Cafe","Couples,Friends,Solo",0,280,2.0,300,11.0018,76.9765,"Coimbatore Junction Railway Station (1.2 km)",[40,60,55,78]),
 ("CBE_07","Coimbatore","Marudhamalai Temple Foothills & Viewpoint","Vadavalli","Hill & Heritage","Family,Solo,Friends",0,140,3.0,450,11.0466,76.8524,"Bus 70 from Gandhipuram",[35,30,85,60]),
 ("CBE_08","Coimbatore","TNAU Botanical Garden","Lawley Road","Nature & Garden","Couples,Family,Solo",20,100,1.5,200,11.0124,76.9355,"Lawley Road / Vadavalli Bus Stop",[15,35,45,55]),
]

# ---------- DB ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS places(
      place_id TEXT PRIMARY KEY, city TEXT, name TEXT, area TEXT, category TEXT, vibe_tags TEXT,
      entry_fee INTEGER, avg_food_activity_cost INTEGER, avg_duration_hrs REAL, max_capacity INTEGER,
      lat REAL, lng REAL, nearest_transit TEXT, crowd_scores TEXT);
    CREATE TABLE IF NOT EXISTS live_cctv_logs(
      log_id INTEGER PRIMARY KEY AUTOINCREMENT, place_id TEXT, detected_count INTEGER,
      crowd_percentage INTEGER, updated_at TEXT);
    CREATE TABLE IF NOT EXISTS saved_plans(
      plan_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, city TEXT, vibe TEXT, slot TEXT,
      total_budget INTEGER, people INTEGER, plan_json TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS hourly_forecasts(
      place_id TEXT, day_int INTEGER, hour INTEGER, busyness INTEGER,
      PRIMARY KEY(place_id, day_int, hour));
    CREATE TABLE IF NOT EXISTS besttime_venues(
      place_id TEXT PRIMARY KEY, venue_id TEXT, venue_name TEXT, venue_address TEXT, synced_at TEXT);
    """)
    for s in SEED:
        c.execute("INSERT OR IGNORE INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (*s[:5], json.dumps(s[5].split(",")), *s[6:13], json.dumps(dict(zip(SLOTS, s[13])))))
    c.commit(); c.close()

def place_row(r):
    d = dict(r)
    d["vibe_tags"] = json.loads(d["vibe_tags"]); d["crowd_scores"] = json.loads(d["crowd_scores"])
    return d

def latest_live():
    """Latest CCTV reading per place, ignoring readings older than LIVE_TTL_MIN."""
    cutoff = (datetime.now() - timedelta(minutes=LIVE_TTL_MIN)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db().execute("""SELECT l.* FROM live_cctv_logs l JOIN
        (SELECT place_id, MAX(log_id) m FROM live_cctv_logs GROUP BY place_id) x ON l.log_id = x.m
        WHERE l.updated_at >= ?""", (cutoff,)).fetchall()
    return {r["place_id"]: dict(r) for r in rows}

# ---------- Logic ----------
def haversine(a, b):
    R = 6371.0
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lng"] - a["lng"])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(h))

def badge(p):
    return "green" if p < 55 else ("yellow" if p < 80 else "red")

def forecast_score(place_id, slot):
    """Real BestTime hourly data -> (score, source). source: besttime | closed | static
    BestTime day_int: 0=Monday ... 6=Sunday. Weekday = Mon-Fri, weekend = Sat-Sun."""
    days = (5, 6) if slot.startswith("weekend") else (0, 1, 2, 3, 4)
    hrs = list(SLOT_HOURS[slot.split("_")[1]])
    q = (f"SELECT busyness FROM hourly_forecasts WHERE place_id=? "
         f"AND day_int IN ({','.join('?' * len(days))}) AND hour IN ({','.join('?' * len(hrs))})")
    vals = [r[0] for r in db().execute(q, (place_id, *days, *hrs))]
    if not vals:
        return None, "static"                 # venue not synced yet
    nonzero = [v for v in vals if v > 0]
    if not nonzero:
        return None, "closed"                 # BestTime reports 0 = closed in this window
    return round(sum(nonzero) / len(nonzero)), "besttime"

def build_plans(d):
    city, vibe, slot = d["city"], d["vibe"], d["slot"]
    people = max(1, int(d["people"])); total = float(d["budget"])
    per_head = total / people; avoid = bool(d.get("avoid_crowds"))
    fare = FARES[city]; live = latest_live()

    cands = []
    for r in db().execute("SELECT * FROM places WHERE city=?", (city,)):
        p = place_row(r)
        if vibe not in p["vibe_tags"]: continue
        pid = p["place_id"]
        if pid in live:
            p["crowd"], p["source"] = live[pid]["crowd_percentage"], "live"
        else:
            sc, src = forecast_score(pid, slot)
            if src == "closed": continue                       # closed in this window
            if sc is None: sc, src = p["crowd_scores"][slot], "static"
            p["crowd"], p["source"] = sc, src
        p["is_live"] = p["source"] == "live"
        if avoid and p["crowd"] > 75: continue
        cands.append(p)

    best = {}
    for n in (3, 2):
        for combo in itertools.combinations(cands, n):
            for perm in itertools.permutations(combo):
                hops = [haversine(perm[i], perm[i+1]) for i in range(n-1)]
                if any(h > MAX_HOP_KM for h in hops): continue
                transit = fare["base"] + sum(h * fare["km"] for h in hops)
                spend = sum(p["entry_fee"] + p["avg_food_activity_cost"] for p in perm) + transit
                hrs = sum(p["avg_duration_hrs"] for p in perm)
                if spend >= per_head or hrs > 9: continue      # strictly inside budget
                avg_crowd = sum(p["crowd"] for p in perm) / n
                score = avg_crowd - 8*n - 15*(spend/per_head) + 2*sum(hops)
                key = frozenset(p["place_id"] for p in perm)
                if key not in best or score < best[key][0]:
                    best[key] = (score, perm, hops, spend, avg_crowd)
    ranked = sorted(best.values(), key=lambda x: x[0])[:3]

    plans = []
    for score, perm, hops, spend, avg_crowd in ranked:
        t = datetime(2026, 1, 1, 9, 0) if "morning" in slot else datetime(2026, 1, 1, 16, 30)
        stops = []
        for i, p in enumerate(perm):
            tin = fare["base"] if i == 0 else round(hops[i-1] * fare["km"])
            travel_min = 0 if i == 0 else round(hops[i-1] / 22 * 60 + 5)
            t += timedelta(minutes=travel_min)
            arrive = t; t += timedelta(hours=p["avg_duration_hrs"])
            head = p["entry_fee"] + p["avg_food_activity_cost"] + tin
            stops.append({
                "place_id": p["place_id"], "name": p["name"], "area": p["area"], "category": p["category"],
                "arrive": arrive.strftime("%I:%M %p"), "leave": t.strftime("%I:%M %p"),
                "hours": p["avg_duration_hrs"], "entry_fee": p["entry_fee"],
                "food_activity": p["avg_food_activity_cost"], "transit_cost": tin,
                "per_head": head, "group_cost": head * people,
                "nearest_transit": p["nearest_transit"], "crowd": p["crowd"],
                "badge": badge(p["crowd"]), "is_live": p["is_live"], "source": p["source"],
                "hop_km": 0 if i == 0 else round(hops[i-1], 1)})
            t += timedelta(minutes=10)
        per_head_total = round(sum(s["per_head"] for s in stops))
        plans.append({"stops": stops, "per_head_total": per_head_total,
                      "group_total": per_head_total * people,
                      "buffer": round(total - per_head_total * people),
                      "buffer_per_head": round(per_head - per_head_total),
                      "avg_crowd": round(avg_crowd), "badge": badge(avg_crowd)})
    return {"per_head_budget": round(per_head, 1), "candidates": len(cands), "plans": plans}

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/places")
def api_places():
    city = request.args.get("city"); live = latest_live()
    rows = db().execute("SELECT * FROM places WHERE (? IS NULL OR city=?) ORDER BY place_id", (city, city))
    out = []
    for r in rows:
        p = place_row(r); p["live"] = live.get(p["place_id"]); out.append(p)
    return jsonify(out)

@app.route("/api/plan", methods=["POST"])
def api_plan():
    d = request.get_json(force=True)
    if d.get("city") not in FARES or d.get("slot") not in SLOTS:
        return jsonify(error="Invalid city or time slot"), 400
    if float(d.get("budget", 0)) <= 0 or int(d.get("people", 0)) < 1:
        return jsonify(error="Budget and people must be positive"), 400
    return jsonify(build_plans(d))

@app.route("/api/cctv", methods=["POST"])
def api_cctv():
    d = request.get_json(force=True)
    r = db().execute("SELECT max_capacity FROM places WHERE place_id=?", (d.get("place_id"),)).fetchone()
    if not r: return jsonify(error="Unknown place"), 404
    count = max(0, int(d.get("detected_count", 0)))
    pct = min(100, round(count / r["max_capacity"] * 100))
    db().execute("INSERT INTO live_cctv_logs(place_id,detected_count,crowd_percentage,updated_at) VALUES(?,?,?,?)",
                 (d["place_id"], count, pct, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db().commit()
    return jsonify(place_id=d["place_id"], detected_count=count, crowd_percentage=pct, badge=badge(pct))

@app.route("/api/cctv/logs")
def api_logs():
    rows = db().execute("""SELECT l.*, p.name FROM live_cctv_logs l JOIN places p USING(place_id)
                           ORDER BY log_id DESC LIMIT 8""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/cctv/reset", methods=["POST"])
def api_reset():
    pid = (request.get_json(silent=True) or {}).get("place_id")
    if pid: db().execute("DELETE FROM live_cctv_logs WHERE place_id=?", (pid,))
    else: db().execute("DELETE FROM live_cctv_logs")
    db().commit(); return jsonify(ok=True)

@app.route("/api/forecast/status")
def api_forecast_status():
    """Shows which places have real BestTime data (handy for checking the sync worked)."""
    rows = db().execute("""SELECT p.place_id, p.name, b.venue_name AS matched_name, b.venue_address, b.synced_at
                           FROM places p LEFT JOIN besttime_venues b USING(place_id) ORDER BY p.place_id""")
    return jsonify([dict(r) for r in rows])

@app.route("/api/plans", methods=["GET", "POST"])
def api_saved():
    if request.method == "POST":
        d = request.get_json(force=True)
        db().execute("""INSERT INTO saved_plans(title,city,vibe,slot,total_budget,people,plan_json,created_at)
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (d["title"], d["city"], d["vibe"], d["slot"], d["budget"], d["people"],
                      json.dumps(d["plan"]), datetime.now().strftime("%Y-%m-%d %H:%M")))
        db().commit(); return jsonify(ok=True)
    rows = db().execute("SELECT * FROM saved_plans ORDER BY plan_id DESC LIMIT 10").fetchall()
    return jsonify([{**dict(r), "plan_json": json.loads(r["plan_json"])} for r in rows])

@app.route("/api/plans/<int:pid>", methods=["DELETE"])
def api_del(pid):
    db().execute("DELETE FROM saved_plans WHERE plan_id=?", (pid,)); db().commit()
    return jsonify(ok=True)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)