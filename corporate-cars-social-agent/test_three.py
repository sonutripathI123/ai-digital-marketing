import sqlite3
from datetime import datetime, timedelta

TARGETS = {11: "instagram", 12: "facebook", 13: "linkedin"}

c = sqlite3.connect("social_agent.db")
c.execute("DELETE FROM schedule")
c.execute("UPDATE posts SET status='draft' WHERE status='scheduled'")

past = (datetime.utcnow() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
for pid in TARGETS:
    c.execute("UPDATE posts SET status='scheduled' WHERE id=?", (pid,))
    c.execute("INSERT INTO schedule (post_id, publish_at, published, attempts) VALUES (?,?,0,0)", (pid, past))
c.commit()

now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
due = c.execute("SELECT p.id, p.platform FROM schedule s JOIN posts p ON p.id=s.post_id WHERE s.published=0 AND s.publish_at <= ? AND p.status='scheduled' ORDER BY p.id", (now,)).fetchall()

print("DUE POSTS:", due)
print("TOTAL DUE =", len(due))

assert sorted((r[0], r[1]) for r in due) == sorted(TARGETS.items()), "STOP mismatch"
print("OK - bilkul yahi 3 posts due hain. Aage badh sakte ho.")
c.close()