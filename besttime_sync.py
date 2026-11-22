"""Pull real BestTime.app hourly forecasts (Mon-Sun x 24h) for Chennai & Coimbatore places."""
import os, sys, time, sqlite3, requests
from datetime import datetime

DB = "smart_planner.db"
KEY = os.environ.get("BESTTIME_PRIVATE_KEY")
URL = "https://besttime.app/api/v1/forecasts"

TABLES = """
CREATE TABLE IF NOT EXISTS hourly_forecasts(
  place_id TEXT, day_int INTEGER, hour INTEGER, busyness INTEGER,
  PRIMARY KEY(place_id, day_int, hour));
CREATE TABLE IF NOT EXISTS besttime_venues(
  place_id TEXT PRIMARY KEY, venue_id TEXT, venue_name TEXT, venue_address TEXT, synced_at TEXT);
"""

# place_id: (search name, address). Shorter names match BestTime/Google listings better.
SEARCH = {
 "CHN_01": ("Elliot's Beach", "Besant Nagar, Chennai, Tamil Nadu, India"),
 "CHN_02": ("Semmozhi Poonga", "Teynampet, Chennai, Tamil Nadu, India"),
 "CHN_03": ("VR Chennai", "Anna Nagar West, Chennai, Tamil Nadu, India"),
 "CHN_04": ("Anna Nagar Tower Park", "Anna Nagar, Chennai, Tamil Nadu, India"),
 "CHN_05": ("Government Museum Chennai", "Egmore, Chennai, Tamil Nadu, India"),
 "CHN_06": ("Express Avenue", "17 Pattullos Rd, Thousand Lights, Chennai, Tamil Nadu 600014, India"),
 "CHN_07": ("Marina Beach Lighthouse", "Mylapore, Chennai, Tamil Nadu, India"),
 "CHN_08": ("Sowcarpet Mint Street", "George Town, Chennai, Tamil Nadu, India"),
 "CHN_09": ("Phoenix Marketcity", "Velachery, Chennai, Tamil Nadu, India"),
 "CHN_10": ("Guindy National Park", "Guindy, Chennai, Tamil Nadu, India"),
 "CHN_11": ("DakshinaChitra Museum", "Muttukadu, ECR, Chennai, Tamil Nadu, India"),
 "CHN_12": ("Board Room Cafe", "Mylapore, Chennai, Tamil Nadu, India"),
 "CHN_13": ("Nexus Vijaya Mall", "183 Great Southern Trunk Rd Arcot Rd, Vadapalani, Chennai, Tamil Nadu 600026, India"),
 "CHN_14": ("The Marina Mall Chennai", "13/1A Old Mahabalipuram Road, Egattur, Tamil Nadu 600130, India"),
 "CBE_01": ("Brookefields Mall", "RS Puram, Coimbatore, Tamil Nadu, India"),
 "CBE_02": ("VOC Park and Zoo", "Gopalapuram, Coimbatore, Tamil Nadu, India"),
 "CBE_03": ("Valankulam Lake", "Ukkadam, Coimbatore, Tamil Nadu, India"),
 "CBE_04": ("Prozone Mall", "Sivanandapuram, Coimbatore, Tamil Nadu, India"),
 "CBE_05": ("GD Naidu Museum", "Avinashi Road, Coimbatore, Tamil Nadu, India"),
 "CBE_06": ("Race Course", "Race Course, Coimbatore, Tamil Nadu, India"),
 "CBE_07": ("Marudhamalai Temple", "Vadavalli, Coimbatore, Tamil Nadu, India"),
 "CBE_08": ("TNAU Botanical Garden", "Lawley Road, Coimbatore, Tamil Nadu, India"),
"CHN_08": ("Mint Street Sowcarpet", "Mint St, Sowcarpet, Chennai, Tamil Nadu 600079, India"),
    "CBE_04": ("Prozone Mall", "Sathy Rd, Sivanandapuram, Saravanampatti, Coimbatore, Tamil Nadu 641035, India"),
}

def sync(force=False):
    if not KEY:
        sys.exit("Set BESTTIME_PRIVATE_KEY first (see run commands).")
    c = sqlite3.connect(DB); c.executescript(TABLES)
    done = {r[0] for r in c.execute("SELECT place_id FROM besttime_venues")}
    ok = fail = 0
    for pid, (name, addr) in SEARCH.items():
        if pid in done and not force:
            print(f"skip {pid} (already synced)"); continue
        try:
            r = requests.post(URL, params={"api_key_private": KEY, "venue_name": name,
                                           "venue_address": addr}, timeout=90).json()
        except Exception as e:
            print(f"✗ {pid} {name}: {e}"); fail += 1; continue
        if r.get("status") != "OK" or not r.get("analysis"):
            print(f"✗ {pid} {name}: {r.get('message', 'no forecast available')}"); fail += 1; continue
        vi = r.get("venue_info", {})
        c.execute("INSERT OR REPLACE INTO besttime_venues VALUES (?,?,?,?,?)",
                  (pid, vi.get("venue_id"), vi.get("venue_name"), vi.get("venue_address"),
                   datetime.now().strftime("%Y-%m-%d %H:%M")))
        for day in r["analysis"]:
            d = day["day_info"]["day_int"]               # 0 = Monday ... 6 = Sunday
            for i, v in enumerate(day["day_raw"]):       # index 0 = 6 AM
                c.execute("INSERT OR REPLACE INTO hourly_forecasts VALUES (?,?,?,?)",
                          (pid, d, (6 + i) % 24, int(v)))
        c.commit(); ok += 1
        print(f"✓ {pid} matched → {vi.get('venue_name')} | {vi.get('venue_address')}")
        time.sleep(1)
    print(f"\nDone. {ok} synced, {fail} failed (failed ones use the static fallback).")

if __name__ == "__main__":
    sync(force="--force" in sys.argv)