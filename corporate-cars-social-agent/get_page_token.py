import os, re, shutil, requests
from dotenv import load_dotenv

load_dotenv()
tok = os.getenv("META_ACCESS_TOKEN")
page = os.getenv("META_PAGE_ID")

r = requests.get(f"https://graph.facebook.com/v21.0/{page}",
                 params={"fields": "access_token,name", "access_token": tok})
d = r.json()

if "access_token" not in d:
    print("FAILED — response:", d)
    raise SystemExit(1)

page_token = d["access_token"]
print("Page mila:", d.get("name"))
print("Page token length:", len(page_token), "| starts with:", page_token[:6] + "...")

# .env ka backup
shutil.copy(".env", ".env.backup")

txt = open(".env", encoding="utf-8").read()
if "META_USER_TOKEN=" not in txt:
    txt = txt.replace("META_ACCESS_TOKEN=", "META_USER_TOKEN=", 1)   # purana bachao
    txt += f"\nMETA_ACCESS_TOKEN={page_token}\n"
else:
    txt = re.sub(r"META_ACCESS_TOKEN=.*", f"META_ACCESS_TOKEN={page_token}", txt)

open(".env", "w", encoding="utf-8").write(txt)
print("OK — .env update ho gaya (backup: .env.backup)")