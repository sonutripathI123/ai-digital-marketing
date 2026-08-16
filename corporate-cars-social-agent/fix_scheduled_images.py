import sqlite3
import re

c = sqlite3.connect("social_agent.db")

# Saari web images (public_url wali) — base code se map
web = {}
for iid, fn in c.execute("SELECT id, filename FROM images WHERE public_url IS NOT NULL"):
    m = re.match(r"(0H5A\d+)", fn)
    if m:
        web.setdefault(m.group(1), []).append((iid, fn))

# Scheduled (unpublished) posts jinki image local/problem hai
rows = c.execute("""
    SELECT p.id, p.platform, i.filename, p.image_id
    FROM posts p
    JOIN schedule s ON s.post_id = p.id
    JOIN images i ON i.id = p.image_id
    WHERE s.published = 0 AND i.public_url IS NULL
""").fetchall()

fixed = 0
skipped = []
for pid, platform, fn, img_id in rows:
    m = re.match(r"(0H5A\d+)", fn or "")
    if not m:
        # ye clean image hai (wedding-cars, people-mover) — chhod do, ye theek hai
        continue
    base = m.group(1)
    if base in web:
        new_img_id, new_fn = web[base][0]
        c.execute("UPDATE posts SET image_id=? WHERE id=?", (new_img_id, pid))
        print(f"  FIXED post #{pid} ({platform}): {fn}  ->  {new_fn}")
        fixed += 1
    else:
        skipped.append((pid, platform, fn))

c.commit()
print(f"\nTotal fixed: {fixed}")
if skipped:
    print("Web image nahi mili inke liye (skip):")
    for s in skipped:
        print("  ", s)
c.close()