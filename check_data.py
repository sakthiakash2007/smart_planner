import sqlite3
c = sqlite3.connect("smart_planner.db")
pid = "CHN_13"   # Nexus Vijaya Mall; try CHN_06, CHN_09, CBE_01
for d, name in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
    vals = [r[0] for r in c.execute(
        "SELECT busyness FROM hourly_forecasts WHERE place_id=? AND day_int=? ORDER BY hour", (pid, d))]
    print(name, vals)