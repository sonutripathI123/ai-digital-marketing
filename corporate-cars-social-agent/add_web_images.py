import sqlite3
from datetime import datetime

# Website pe jo images hain — filename se public_url
BASE = "https://corporatecarsmelbourne.com.au/wp-content/uploads/2026/08/"
NAMES = [
    "0H5A4921-1-scaled.jpg", "0H5A4924-1-1-scaled.jpg", "0H5A4924-1-scaled.jpg",
    "0H5A4946-scaled.jpg", "0H5A4953-1-scaled.jpg", "0H5A4958-1-scaled.jpg",
    "0H5A4958-2-scaled.jpg", "0H5A4981-1-scaled.jpg", "0H5A4985-1-scaled.jpg",
    "0H5A5003-1-scaled.jpg", "0H5A5007-1-scaled.jpg", "0H5A5040-1-scaled.jpg",
    "0H5A5121-1-scaled.jpg", "0H5A5126-scaled.jpg", "0H5A5157-1-scaled.jpg",
    "0H5A6506-1-scaled.jpg", "0H5A6544-1-scaled.jpg",
]

# General fleet tags — har business keyword (airport, corporate, chauffeur, executive, luxury) pe match
CATEGORY = "sedan"
TAGS = "sedan,suv,corporate,airport,chauffeur,executive,luxury,fleet"

c = sqlite3.connect("social_agent.db")
now = datetime.utcnow().isoformat()
added = 0
updated = 0

for name in NAMES:
    url = BASE + name
    row = c.execute("SELECT id FROM images WHERE filename=?", (name,)).fetchone()
    if row:
        c.execute("UPDATE images SET public_url=?, category=?, tags=? WHERE id=?",
                  (url, CATEGORY, TAGS, row[0]))
        updated += 1
    else:
        c.execute("""INSERT INTO images (filename, filepath, category, tags, use_count, created_at, public_url)
                     VALUES (?,?,?,?,0,?,?)""",
                  (name, "WEB", CATEGORY, TAGS, now, url))
        added += 1

c.commit()
print(f"Added: {added}, Updated: {updated}")
print("--- ab DB mein web images ---")
for r in c.execute("SELECT id, filename, public_url FROM images WHERE public_url IS NOT NULL"):
    print(r)
c.close()