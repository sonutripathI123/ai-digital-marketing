import sqlite3
import re
from collections import defaultdict
from pathlib import Path

db_path = Path(__file__).parent / "social_agent.db"
c = sqlite3.connect(str(db_path))

# 1. Fetch all valid images with public_url, sorted deterministically
images = c.execute("""
    SELECT id, filename, public_url, category 
    FROM images 
    WHERE public_url IS NOT NULL AND public_url != ''
    ORDER BY id ASC
""").fetchall()

if not images:
    images = c.execute("SELECT id, filename, public_url, category FROM images ORDER BY id ASC").fetchall()

total_images = len(images)
print(f"=== Total Available Images Pool: {total_images} Photos ===")
for idx, (iid, fn, url, cat) in enumerate(images, 1):
    print(f"  Photo #{idx:02d} [ID {iid}]: {fn} ({cat or 'general'})")

# 2. Get all unpublished scheduled posts ordered chronologically by publish_at
scheduled_rows = c.execute("""
    SELECT p.id, p.platform, p.keyword_id, s.publish_at, p.image_id, k.keyword
    FROM posts p
    JOIN schedule s ON s.post_id = p.id
    LEFT JOIN keywords k ON k.id = p.keyword_id
    WHERE s.published = 0
    ORDER BY s.publish_at ASC, p.id ASC
""").fetchall()

print(f"\n=== Total Unpublished Scheduled Posts: {len(scheduled_rows)} Posts ===")

# 3. Group posts into 3-platform batches by publish date/slot
batches = defaultdict(list)
for pid, platform, kw_id, pub_at, img_id, kw_text in scheduled_rows:
    # Group by publish date (YYYY-MM-DD) and keyword/slot
    slot_key = str(pub_at)[:10] + f"_kw_{kw_id}"
    batches[slot_key].append({
        "post_id": pid,
        "platform": platform,
        "publish_at": pub_at,
        "keyword": kw_text or "corporate-transfers"
    })

print(f"=== Total Scheduled Post Batches: {len(batches)} Batches ===\n")

# 4. Assign images strictly 1-by-1 in sequential round-robin across all 3 platforms
updated_count = 0
for batch_idx, (slot_key, post_list) in enumerate(batches.items()):
    img_idx = batch_idx % total_images
    chosen_img = images[img_idx]
    chosen_id, chosen_fn, chosen_url, chosen_cat = chosen_img

    print(f"[*] Batch #{batch_idx + 1:02d} [{slot_key}] -> Photo #{img_idx + 1:02d}: {chosen_fn} (ID {chosen_id})")
    for p in post_list:
        c.execute("UPDATE posts SET image_id = ? WHERE id = ?", (chosen_id, p["post_id"]))
        print(f"    -> Post #{p['post_id']} [{p['platform'].upper()}] scheduled for {p['publish_at']}")
        updated_count += 1

c.commit()
c.close()

print(f"\nSUCCESS: {updated_count} scheduled posts updated with 100% synchronized round-robin photo rotation!")
print(f"Cycle Rule: Photo 1 -> Photo 2 -> ... -> Photo {total_images} across IG, FB, and LinkedIn, then repeats from Photo 1.")