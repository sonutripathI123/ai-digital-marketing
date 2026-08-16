import sqlite3
from datetime import datetime, timedelta

TARGET_POST_ID = 6  # linkedin draft

c = sqlite3.connect("social_agent.db")

# safety: koi bhi purana schedule row na ho
c.execute("DELETE FROM schedule")

# target ko scheduled karo, baaki sab draft
c.execute("UPDATE posts SET status='draft'")
c.execute("UPDATE posts SET status='scheduled' WHERE id=?", (TARGET_POST_ID,))

# ek Schedule row: publish_at = 5 min pehle (UTC), published=False
past = (datetime.utcnow() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
c.execute(
    "INSERT INTO schedule (post_id, publish_at, published, attempts) VALUES (?,?,0,0)",
    (TARGET_POST_ID, past),
)
c.commit()

# VERIFY — publish_due ki exact conditions
now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
due = c.execute("""
    SELECT p.id, p.platform, p.status, s.publish_at, s.published
    FROM schedule s JOIN posts p ON p.id = s.post_id
    WHERE s.published=0 AND s.publish_at <= ? AND p.status='scheduled'
""", (now,)).fetchall()

print("DUE POSTS (publish-due inhe hi bhejega):")
for r in due:
    print("  ", r)
print(f"\nTOTAL DUE = {len(due)}")
assert len(due) == 1 and due[0][1] == "linkedin", "STOP! Expected exactly 1 x post"
print("OK — sirf 1 x post due hai. Aage badh sakte ho.")
c.close()