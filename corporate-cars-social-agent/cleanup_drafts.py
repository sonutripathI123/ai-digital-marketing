import re, io
from cli import _session
from models import Post
s = _session()
# normal-ify fancy unicode bold + strip markdown + fix broken hashtag
def fix_bold(t):
    out = []
    for ch in t:
        o = ord(ch)
        if 0x1D5D4 <= o <= 0x1D5ED: out.append(chr(o - 0x1D5D4 + ord('A')))
        elif 0x1D5EE <= o <= 0x1D607: out.append(chr(o - 0x1D5EE + ord('a')))
        else: out.append(ch)
    return "".join(out)
n = 0
for p in s.query(Post).filter(Post.status=='draft').all():
    c = p.caption
    c = fix_bold(c)
    c = c.replace("**", "")
    c = c.replace("CorporateCarsM elbourne", "CorporateCarsMelbourne")
    if p.hashtags: p.hashtags = p.hashtags.replace("CorporateCarsM elbourne","CorporateCarsMelbourne")
    if c != p.caption:
        p.caption = c; n += 1
s.commit()
print("Cleaned", n, "drafts")
s.close()
