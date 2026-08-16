import os, re, requests
from dotenv import load_dotenv

CODE = "AQTHwEfgVdInVpCCqb4GEzgcE626wit963u5P9ceHu-emHwLEruBx6JkLU9E0NpEpzjSRWMmuQMr66asy1P36OmP2u9sXlih749-lJoNs0CdwUQZWh6mnPCIbZdAdRUamvVP5fP0o0DAompU6OF55ABRkW0JSDLb6Uv0g5ehSj9Mx_0kdZ309ed-MKh-tq3ZsuwStrEGTHhQC_f27DY"

load_dotenv()
r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
    "grant_type": "authorization_code",
    "code": CODE,
    "redirect_uri": "http://localhost:8000/callback",
    "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
    "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
})
d = r.json()
if "access_token" not in d:
    print("FAILED:", d)
    raise SystemExit(1)

token = d["access_token"]
refresh = d.get("refresh_token", "")

txt = open(".env", encoding="utf-8").read()

if "LINKEDIN_ACCESS_TOKEN=" in txt:
    txt = re.sub(r"LINKEDIN_ACCESS_TOKEN=.*", f"LINKEDIN_ACCESS_TOKEN={token}", txt)
else:
    txt += f"\nLINKEDIN_ACCESS_TOKEN={token}\n"

if "LINKEDIN_REFRESH_TOKEN=" in txt:
    txt = re.sub(r"LINKEDIN_REFRESH_TOKEN=.*", f"LINKEDIN_REFRESH_TOKEN={refresh}", txt)
else:
    txt += f"LINKEDIN_REFRESH_TOKEN={refresh}\n"

open(".env", "w", encoding="utf-8").write(txt)
print("OK — LinkedIn token .env mein daal diya (len:", len(token), ")")