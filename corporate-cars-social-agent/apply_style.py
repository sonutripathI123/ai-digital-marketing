import io
s = io.open('prompts.py', encoding='utf-8').read()
old = "TASK\nWrite ONE social media post"
style = "WRITING STYLE - sound like a real person, not an ad or AI:\n- Use plain, everyday English. Short sentences. One idea at a time.\n- Avoid corporate jargon and heavy words. Do not use: seamless, elevate, reconcile, attributable, consolidate, unparalleled, bespoke, discerning, curated, epitome, testament. Say it the simple way a normal person would.\n- Write like you are talking to one busy person, not a boardroom.\n- Keep the calm, premium, confident feel - but keep it easy to read.\n- No cliches, no hype, no exclamation-heavy lines. Vary sentence length so it reads naturally.\n- Contractions are fine.\n\n"
new = style + old
s = s.replace(old, new, 1)
io.open('prompts.py', 'w', encoding='utf-8').write(s)
print('Done. WRITING STYLE added.')
