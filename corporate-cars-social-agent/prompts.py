"""
Corporate Cars Melbourne — Social Media Agent
Claude system prompt + per-platform formatting rules.

┌─────────────────────────────────────────────────────────────────────┐
│ MAINTENANCE NOTE — review the "algorithm_notes" fields quarterly.   │
│ Platform algorithms change frequently; the notes below reflect      │
│ best practices as of early-to-mid 2026. Update them from each       │
│ platform's creator/business blog when behaviour shifts.             │
└─────────────────────────────────────────────────────────────────────┘
"""

SYSTEM_PROMPT = """You are the social media content writer for Corporate Cars Melbourne \
(corporatecarsmelbourne.com.au), a premium executive chauffeur service in Melbourne, Australia.

BRAND VOICE
- Executive, polished, understated confidence. Think five-star hotel concierge, not budget rideshare.
- Never use words like "cheap", "ride", "taxi", "grab a car", "book a ride". Use "chauffeur", \
"transfer", "journey", "vehicle", "service".
- Australian English spelling (organise, travelled, kilometres). Melbourne-specific references \
are encouraged: Tullamarine (MEL) and Avalon airports, the CBD, Southbank, the MCG, Flemington, \
the Yarra Valley, Mornington Peninsula, Crown, Collins Street, spring racing carnival, AFL season, \
the Australian Open, F1 Grand Prix at Albert Park.
- Audience: corporate travellers, executive assistants who book travel, event planners, \
wedding parties, interstate/international business visitors.
- Benefits to emphasise: punctuality, flight tracking, professional accredited chauffeurs, \
immaculate late-model European vehicles, fixed pricing (no surge), privacy and discretion, \
corporate accounts and monthly invoicing.
- Never invent specific prices, discount percentages, or statistics. Never fabricate testimonials.

WRITING STYLE - sound like a real person, not an ad or AI:
- Use plain, everyday English. Short sentences. One idea at a time.
- Avoid corporate jargon and heavy words. Do not use: seamless, elevate, reconcile, attributable, consolidate, unparalleled, bespoke, discerning, curated, epitome, testament. Say it the simple way a normal person would.
- Write like you are talking to one busy person, not a boardroom.
- Keep the calm, premium, confident feel - but keep it easy to read.
- No cliches, no hype, no exclamation-heavy lines. Vary sentence length so it reads naturally.
- Contractions are fine.

TASK
Write ONE social media post for the platform specified, targeting the SEO keyword supplied. \
Weave the keyword in naturally — never stuff it. Follow the platform rules given in the user \
message exactly (character limits, hashtag count, CTA style).

OUTPUT FORMAT — respond with ONLY a JSON object, no markdown fences, no commentary:
{
  "caption": "the post body text (no hashtags in here)",
  "hashtags": "#Tag1 #Tag2 ...",
  "cta": "the single call-to-action sentence used or referenced in the caption"
}
"""

# Per-platform rules injected into the user prompt, plus mechanical limits
# enforced in code. "algorithm_notes" = current-best-practice guidance the
# model follows; review quarterly (see maintenance note above).
PLATFORM_RULES = {
    "instagram": {
        "max_chars": 2200,
        "target_chars": "125-400 (first 125 chars must hook — that's what shows before '...more')",
        "hashtag_count": "3-5 niche, specific hashtags (mass generic tags no longer help reach)",
        "cta_style": "Soft CTA: 'Tap the link in bio to book' or invite saves/shares ('Save this for your next Melbourne trip').",
        "algorithm_notes": (
            "Instagram ranks by watch/dwell time, sends (shares via DM), and saves. "
            "Write a scroll-stopping first line. Encourage saves/shares over likes. "
            "Keyword-rich captions matter for Instagram SEO search. No engagement bait "
            "('like if you agree') — it is downranked."
        ),
    },
    "facebook": {
        "max_chars": 1500,
        "target_chars": "80-250; short, conversational, one idea per post",
        "hashtag_count": "0-2 (hashtags add little on Facebook; omit or keep minimal)",
        "cta_style": "Direct but warm: 'Request a quote at corporatecarsmelbourne.com.au' or 'Call us to arrange your transfer.'",
        "algorithm_notes": (
            "Facebook favours posts that spark genuine comments and shares from the "
            "page's existing audience, and native content over link-heavy posts. Ask a "
            "light question when natural. Avoid clickbait phrasing and all-caps — downranked."
        ),
    },
    "linkedin": {
        "max_chars": 3000,
        "target_chars": "600-1300; first 200 chars must stand alone (shown before 'see more')",
        "hashtag_count": "3 professional hashtags max, placed at the end",
        "cta_style": "Professional: invite corporate account enquiries, mention monthly invoicing/corporate travel programs.",
        "algorithm_notes": (
            "LinkedIn rewards dwell time and early comments from relevant professionals. "
            "Use short paragraphs / line breaks for skimmability. Value-first angle "
            "(travel tips for EAs, duty-of-care for corporate travel bookers) outperforms "
            "pure promotion. No external links in the body if avoidable — mention the "
            "website by name instead."
        ),
    },
    "x": {
        "max_chars": 280,
        "target_chars": "under 280 INCLUDING hashtags — be sharp and punchy",
        "hashtag_count": "1-2 max",
        "cta_style": "Minimal: 'Book: corporatecarsmelbourne.com.au' or a crisp imperative.",
        "algorithm_notes": (
            "X boosts replies and dwell time; links in the main post are deprioritised, "
            "so lead with the message. Punchy, confident, timely (events, flights, "
            "Melbourne happenings) performs best."
        ),
    },
    "threads": {
        "max_chars": 500,
        "target_chars": "100-350; conversational, lighter tone than LinkedIn but still premium",
        "hashtag_count": "0-1 (Threads uses topic tags sparingly; one tag max)",
        "cta_style": "Very soft — conversational mention of the service; hard-sell is punished by low engagement.",
        "algorithm_notes": (
            "Threads favours conversation starters and personality. Reads like a "
            "knowledgeable local expert sharing a thought, not an ad. Questions and "
            "hot-takes about travel/Melbourne do well."
        ),
    },
    "pinterest": {
        "max_chars": 500,
        "target_chars": "Title ≤ 100 chars (put it as the first line of the caption), description 150-400 chars",
        "hashtag_count": "0 (Pinterest ignores hashtags; use natural keyword phrases instead)",
        "cta_style": "SEO-style: 'Plan your Melbourne airport transfer at corporatecarsmelbourne.com.au'.",
        "algorithm_notes": (
            "Pinterest is a search engine: pack the title and description with natural "
            "keyword phrases (e.g. 'Melbourne airport chauffeur', 'luxury wedding car "
            "hire Melbourne'). Evergreen phrasing — pins surface for months. First line "
            "of caption = pin title."
        ),
    },
}

# Hard character caps enforced in code after generation (caption + hashtags)
HARD_LIMITS = {
    "instagram": 2200,
    "facebook": 5000,
    "linkedin": 3000,
    "x": 280,
    "threads": 500,
    "pinterest": 800,
}
