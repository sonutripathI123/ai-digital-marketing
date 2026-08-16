# Chauffeur Blog Agent

Regular basis pe apni chauffeur sites pe SEO blog posts auto-publish karne ka
Python agent. Hybrid approval + draft-phir-auto-live model pe chalta hai.

## Kaise kaam karta hai

```
suggest  ->  AI topic ideas deta hai (status: suggested). Tu topics.csv me
             pasand ke topics ka status "approved" kar deta hai.
write    ->  approved topics ko full post me likhta hai + WordPress DRAFT banata
             hai. go_live_at = ab + 24h set hota hai (status: drafted).
publish  ->  jin drafts ka 24h window nikal gaya unhe LIVE kar deta hai
             (status: published). Jise rokna ho, uska status "hold" kar de.
status   ->  queue ka summary dikhata hai.
```

Status flow: `suggested -> approved -> drafted -> published`
Kabhi bhi kisi row ka status `hold` ya `rejected` karke rok sakta hai.

## One-time setup

1. **Python deps**
   ```bash
   pip install -r requirements.txt
   ```

2. **Secrets**
   ```bash
   cp .env.example .env
   ```
   `.env` me `ANTHROPIC_API_KEY` aur har site ke WordPress creds bhar.
   WordPress creds = Application Password (WP admin > Users > Profile >
   Application Passwords > naya banao). Env prefix = `config.yaml` ka site key
   upper-case me (`opal` -> `OPAL_WP_USER` / `OPAL_WP_APP_PASSWORD`).

3. **Yoast REST meta (zaroori)** — bina iske focus keyword aur meta description
   REST se set nahi honge. `wp-yoast-rest-meta.php` ko har site pe yahan copy kar:
   ```
   wp-content/mu-plugins/wp-yoast-rest-meta.php
   ```
   `mu-plugins` folder na ho to bana le. Ye khud active ho jata hai.

4. **Sites + links** — `config.yaml` me apni sites check kar. Har site ke
   internal link targets `internal_links_<site>.csv` me daal (agent inhi me se
   2-4 links chunta hai, khud URL invent nahi karta).

## Rozana use

**Titles bulk import (tera main workflow):** apne 15-20 titles `titles_template.csv`
ke format me (`site,suburb,keyword,title`) daal, phir:

```bash
python3 blog_agent.py import --file my_titles.csv --site ccm
```

Ye sab titles ko `approved` status me queue me daal deta hai. Phir `write`
inhe drafts me badal deta hai. (Chaho to `suggest` se AI se naye ideas bhi
manga sakte ho.)

```bash
python3 blog_agent.py write --site ccm     # approved titles -> drafts
python3 blog_agent.py status
```

**Featured image:** har draft ke liye agent teri WordPress media library se ek
relevant image dhundta hai (suburb + keyword + "chauffeur/mercedes/melbourne"
search karke) aur featured image set kar deta hai. Pichli 12 images dobara nahi
chunta, taaki repeat na ho. Config `config.yaml > featured_image` me hai.

**Suburb linking + no cannibalisation:** har suburb blog apne suburb page ko
commercial anchor se link karta hai, aur khud alag informational query target
karta hai. Iske liye `suburb_pages_ccm.csv` me apni real pages bhar:
`suburb,url,keyword` (keyword = wo commercial term jo page own karta hai).

## Cron (automation ka dil)

`crontab -e` me daal (paths apne hisaab se badal). Sunday chhod ke chalega:

```cron
# write: Mon-Sat subah 9 baje, max approved topics -> drafts
0 9 * * 1-6  cd /path/to/blog-agent && /usr/bin/python3 blog_agent.py write >> logs/cron.log 2>&1

# publish: Mon-Sat har ghante, jin drafts ka window nikal gaya unhe live karo
15 * * * 1-6 cd /path/to/blog-agent && /usr/bin/python3 blog_agent.py publish >> logs/cron.log 2>&1
```

Sunday double-protected hai: cron me `1-6` (Mon-Sat) hai, aur code me bhi
`skip_sunday` guard hai, to Sunday koi post live nahi hoga. Server ka Sunday
`config.yaml > timezone` (Australia/Melbourne) ke hisaab se judge hota hai.

`posts_per_write_run`, `review_window_hours`, `default_model`, `skip_sunday`,
`timezone` sab `config.yaml` me adjustable hain.

## Google auto-indexing (optional)

Publish hote hi agent naye URL ko Google Indexing API pe notify kar sakta hai,
taaki crawl jaldi ho. Ye GSC ka "Request Indexing" button nahi hai (uska koi
official API nahi), par practically crawl ko nudge karta hai. Sitemap phir bhi
primary rehta hai (Yoast publish pe khud sitemap update karta hai).

One-time setup:
1. Google Cloud Console me ek project banao. "Indexing API" enable karo.
2. Ek Service Account banao. Uski JSON key download karke is folder me
   `gsc-service-account.json` naam se rakho (path config me badal sakte ho).
3. Us service account ka email (jaise `name@project.iam.gserviceaccount.com`)
   copy karo. Search Console me apni property kholo > Settings > Users and
   permissions > Add user > wo email **Owner** role ke saath add karo.
4. `config.yaml` me `google_indexing.enabled: true` kar do.

Ab har publish ke baad URL automatically Google ko submit hoga. Fail hone pe
post live hi rehta hai, bas queue ke notes me reason likh jata hai.

Caveat: Google officially Indexing API ko JobPosting/livestream tak seemit
batata hai. General blogs ke liye ye best-effort nudge hai, guarantee nahi.
Sabse pakka tarika: sitemap GSC me ek baar submit kar do.

## Safety notes

- Har post pehle **draft** banta hai. 24h window me tu WordPress me edit kar
  sakta hai. Edits preserve rehte hain (publish sirf status flip karta hai).
- Cannibalisation guard: agar blog ka focus keyword suburb page ke keyword se
  clash kare, ek retry hota hai, phir bhi clash rahe to draft nahi banta
  (queue me `error` dikhega).
- Sunday ko koi post live nahi hota.
- `.env` kabhi commit mat karna.
