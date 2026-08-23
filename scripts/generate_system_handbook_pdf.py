import os
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

PDF_OUTPUT_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "AI_Digital_Marketing_Master_Handbook.pdf"

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        if self._pageNumber == 1:
            return  # Skip cover

        self.saveState()
        self.setFont('Helvetica-Bold', 8)
        self.setFillColor(colors.HexColor('#64748b'))
        
        self.drawString(54, letter[1] - 36, 'AI DIGITAL MARKETING COMMAND CENTER — MASTER OPERATION HANDBOOK')
        self.drawRightString(letter[0] - 54, letter[1] - 36, 'CORPORATE CARS MELBOURNE')
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
        
        self.line(54, 45, letter[0] - 54, 45)
        self.setFont('Helvetica', 8)
        self.drawString(54, 32, 'Enterprise AI Marketing Operating System | 24/7 Autonomous Cloud Engine')
        page_str = f'Page {self._pageNumber} of {page_count}'
        self.drawRightString(letter[0] - 54, 32, page_str)
        self.restoreState()


def build_pdf(target_path: str = None):
    out_file = target_path or str(PDF_OUTPUT_PATH)
    doc = SimpleDocTemplate(
        out_file,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0f172a")
    c_navy = colors.HexColor("#1e293b")
    c_cyan = colors.HexColor("#0284c7")
    c_cyan_dark = colors.HexColor("#0369a1")
    c_purple = colors.HexColor("#7c3aed")
    c_gray = colors.HexColor("#475569")
    c_light_bg = colors.HexColor("#f8fafc")
    c_card_bg = colors.HexColor("#f1f5f9")

    title_style = ParagraphStyle('CoverTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=24, leading=30, textColor=c_primary)
    subtitle_style = ParagraphStyle('CoverSubtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=12, leading=16, textColor=c_cyan_dark)
    h1_style = ParagraphStyle('H1_Custom', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=c_primary, spaceBefore=14, spaceAfter=6, keepWithNext=True)
    h2_style = ParagraphStyle('H2_Custom', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=c_cyan_dark, spaceBefore=10, spaceAfter=4, keepWithNext=True)
    body_style = ParagraphStyle('Body_Custom', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor("#1e293b"), spaceAfter=5)
    body_bold = ParagraphStyle('Body_Bold', parent=body_style, fontName='Helvetica-Bold')
    bullet_style = ParagraphStyle('Bullet_Custom', parent=body_style, leftIndent=12, firstLineIndent=-8, spaceAfter=3)
    table_cell = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor("#1e293b"))
    table_cell_bold = ParagraphStyle('TableCellBold', parent=table_cell, fontName='Helvetica-Bold', textColor=colors.HexColor("#0f172a"))
    table_header = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.white)

    story = []

    # COVER PAGE
    story.append(Spacer(1, 30))
    story.append(Paragraph("AI DIGITAL MARKETING COMMAND CENTER", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=c_purple, spaceAfter=6)))
    story.append(Paragraph("Master Operation & Agent Reference Handbook", title_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2.5, color=c_cyan, spaceBefore=2, spaceAfter=10))
    story.append(Paragraph("Complete Operational Guide: UI Buttons, All 19 AI Agents, Click Results, Live APIs, and System Capabilities", subtitle_style))
    story.append(Spacer(1, 18))

    meta_data = [
        [Paragraph("<b>Primary Workspace:</b>", table_cell), Paragraph("Corporate Cars Melbourne (corporatecarsmelbourne.com.au)", table_cell)],
        [Paragraph("<b>System Version:</b>", table_cell), Paragraph("v12.4 Enterprise Autonomous Edition", table_cell)],
        [Paragraph("<b>Active AI Engines:</b>", table_cell), Paragraph("Claude Sonnet 4.6 / Claude 3.5 Sonnet, GPT-4o, DeepSeek, Gemini 2.5", table_cell)],
        [Paragraph("<b>Live Connected APIs:</b>", table_cell), Paragraph("Google Search Console (GSC), GA4 Data API, WordPress REST API, Meta Graph API, LinkedIn API", table_cell)],
        [Paragraph("<b>Publication Date:</b>", table_cell), Paragraph(datetime.now().strftime("%B %d, %Y"), table_cell)],
        [Paragraph("<b>Target Audience:</b>", table_cell), Paragraph("Executives, Marketing Managers & Operations Team", table_cell)]
    ]
    meta_table = Table(meta_data, colWidths=[140, 360])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_card_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Handbook Objectives (Is Guide Ka Maqsad):</b>", body_bold))
    story.append(Paragraph("1. Dashboard kholte hi screen par dikhne wale har button, icon aur card ka exact purpose aur result samjhana.", bullet_style))
    story.append(Paragraph("2. Sabhi 19 AI Agents ki complete working, unke report modal ke clickable buttons aur execution flow ko define karna.", bullet_style))
    story.append(Paragraph("3. 100% Reality & Transparency batana ki kaunse agents mein LIVE API data aa raha hai aur jinme simulated data hai unme kyu hai.", bullet_style))
    story.append(Paragraph("4. Word limits, image attachments, cron schedules aur safety rules ka reference provide karna.", bullet_style))

    story.append(PageBreak())

    # TABLE OF CONTENTS
    story.append(Paragraph("Table of Contents (Handbook Index)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=8))

    toc_data = [
        [Paragraph("<b>Section 1: Dashboard UI & Interactive Controls Walkthrough</b>", table_cell_bold), Paragraph("Page 3", table_cell)],
        [Paragraph("• Header Controls (Website Switcher, Admin Lock, Quick Actions)", table_cell), Paragraph("Page 3", table_cell)],
        [Paragraph("• KPI Summary Cards, 3D Cyber Core & Activity Ticker", table_cell), Paragraph("Page 3", table_cell)],
        [Paragraph("• Agent Grid Cards & 4 Core Action Buttons", table_cell), Paragraph("Page 4", table_cell)],
        [Paragraph("<b>Section 2: Complete Deep-Dive of All 19 AI Agents</b>", table_cell_bold), Paragraph("Page 5", table_cell)],
        [Paragraph("• Category 1: SEO & Content Generation Agents (Agents #1 to #7)", table_cell), Paragraph("Pages 5-8", table_cell)],
        [Paragraph("• Category 2: Analytics & Reporting Agents (Agents #8, #9, #13, #16)", table_cell), Paragraph("Pages 8-10", table_cell)],
        [Paragraph("• Category 3: Paid Advertising & Media Agents (Agents #10, #11, #12, #18)", table_cell), Paragraph("Pages 10-12", table_cell)],
        [Paragraph("• Category 4: Social, CRM, CRO & Reputation Agents (Agents #3, #14, #15, #17, #19)", table_cell), Paragraph("Pages 12-14", table_cell)],
        [Paragraph("<b>Section 3: Live vs Simulated Data Transparency Table</b>", table_cell_bold), Paragraph("Page 15", table_cell)],
        [Paragraph("<b>Section 4: Autonomous Schedules, Word Limits & Content Rules</b>", table_cell_bold), Paragraph("Page 16", table_cell)],
        [Paragraph("<b>Section 5: Server Startup, Controls & Troubleshooting Guide</b>", table_cell_bold), Paragraph("Page 17", table_cell)],
    ]
    toc_table = Table(toc_data, colWidths=[420, 80])
    toc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#f1f5f9")),
        ('PADDING', (0,0), (-1,-1), 4.5),
    ]))
    story.append(toc_table)

    # SECTION 1
    story.append(PageBreak())
    story.append(Paragraph("Section 1: Dashboard UI & Interactive Controls Walkthrough", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=8))
    story.append(Paragraph("Jab aap browser mein Dashboard (<b>http://127.0.0.1:8000</b>) open karte hain, toh screen par structured dark-mode command center dikhta hai. Is section mein har button, icon aur card ka exact function define kiya gaya hai.", body_style))

    story.append(Paragraph("1.1 Top Navigation & Header Controls", h2_style))
    header_ui_data = [
        [Paragraph("UI Element / Button", table_header), Paragraph("Icon / Visual", table_header), Paragraph("Click Karne Par Kya Hota Hai? (Action & Result)", table_header)],
        [
            Paragraph("<b>Website Switcher Dropdown</b>", table_cell_bold),
            Paragraph("<font color='#0284c7'>🌐 Dropdown</font>", table_cell),
            Paragraph("Active website change karne ke liye. Click karte hi saare 19 agents, reports, GSC data aur keywords us specific website ke filter ho jaate hain.", table_cell)
        ],
        [
            Paragraph("<b>Admin Lock / Unlock Button</b>", table_cell_bold),
            Paragraph("<font color='#d97706'>🔒 / 🔓 Shield</font>", table_cell),
            Paragraph("Dashboard by default 'Viewer Mode' (Read-Only) mein rehta hai. Click karne par Admin Login khulta hai. Password verify hone par live task execution, blog queue modification aur campaign creation unlock hote hain.", table_cell)
        ],
        [
            Paragraph("<b>+ Add Campaign Button</b>", table_cell_bold),
            Paragraph("<font color='#7c3aed'>+ Sparkles</font>", table_cell),
            Paragraph("Global campaign creation modal kholta hai jahan se Blog + Social + SEO ka combined multi-channel marketing campaign start hota hai.", table_cell)
        ],
        [
            Paragraph("<b>+ Add Blog Topics Button</b>", table_cell_bold),
            Paragraph("<font color='#0284c7'>+ Pen/Blog</font>", table_cell),
            Paragraph("Naye blog topics add karne ka modal kholta hai. Submit karne par yeh direct <code>blog-agent/topics.csv</code> mein auto-insert ho jaate hain.", table_cell)
        ],
        [
            Paragraph("<b>+ Add Social Campaign Button</b>", table_cell_bold),
            Paragraph("<font color='#059669'>+ ShareNodes</font>", table_cell),
            Paragraph("Social media keyword campaign modal kholta hai. Submit karne par keywords seedha SQLite database (<code>social_agent.db</code>) mein save hote hain.", table_cell)
        ],
        [
            Paragraph("<b>⬇ Export Monthly Report (PDF)</b>", table_cell_bold),
            Paragraph("<font color='#d97706'>⬇ PDF Icon</font>", table_cell),
            Paragraph("Sabhi 19 agents ki 30-day performance report ko compile karke executive PDF document generate aur auto-download karta hai.", table_cell)
        ],
        [
            Paragraph("<b>⬇ Download Master Handbook</b>", table_cell_bold),
            Paragraph("<font color='#7c3aed'>⬇ Book Icon</font>", table_cell),
            Paragraph("Yeh complete Master Operation & Reference Handbook PDF direct browser mein download karta hai.", table_cell)
        ]
    ]
    t_header = Table(header_ui_data, colWidths=[120, 80, 300])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_header)

    story.append(Spacer(1, 10))
    story.append(Paragraph("1.2 Agent Card Structure & 4 Interactive Action Buttons", h2_style))
    agent_btn_data = [
        [Paragraph("Button Name", table_header), Paragraph("Button Style / Color", table_header), Paragraph("Action & Live Result", table_header)],
        [
            Paragraph("<b>👁️ View Report</b>", table_cell_bold),
            Paragraph("<font color='#0284c7'>Cyan / Blue Outline</font>", table_cell),
            Paragraph("Agent ka deep performance audit report modal kholta hai (e.g. SEO metrics, live GSC table, blog schedule, social posts, GA4 stats).", table_cell)
        ],
        [
            Paragraph("<b>⚡ Run Task / Quick Action</b>", table_cell_bold),
            Paragraph("<font color='#059669'>Solid Gradient Green</font>", table_cell),
            Paragraph("Agent ko turant manual execution command bhejta hai (e.g. Blog Agent naya article likhna shuru karega, Social Agent due posts publish karega).", table_cell)
        ],
        [
            Paragraph("<b>⏸ Pause / Resume</b>", table_cell_bold),
            Paragraph("<font color='#d97706'>Amber / Orange</font>", table_cell),
            Paragraph("Agent ke automated cron schedule ko temporarily pause ya resume karta hai.", table_cell)
        ],
        [
            Paragraph("<b>📜 Logs</b>", table_cell_bold),
            Paragraph("<font color='#64748b'>Gray / Slate</font>", table_cell),
            Paragraph("Agent ki live execution terminal trace, timestamp, tokens used aur debug logs window kholta hai.", table_cell)
        ]
    ]
    t_agent_btn = Table(agent_btn_data, colWidths=[120, 100, 280])
    t_agent_btn.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_agent_btn)

    # SECTION 2
    story.append(PageBreak())
    story.append(Paragraph("Section 2: Complete Deep-Dive of All 19 AI Agents", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=8))

    agents_list = [
        ("Agent #1: SEO Keyword Research Agent (seo-keyword-agent)", "SEO & Content", "100% LIVE", "Claude Sonnet 4.6 & GSC Engine",
         "Melbourne suburbs aur luxury chauffeur vertical ke commercial keywords find aur cluster karta hai.",
         "Google Search Console API se live 2,486+ queries aur Claude AI semantic analysis ko combine karta hai.",
         [
             "🎯 Check Live Google SERP Rankings: Live 2,486+ keywords ki real Google ranking table (#1.8, #2.2, #5.6, #13.0) kholta hai.",
             "🔍 + Research Any Custom Keyword: Custom Keyword Intelligence Lab kholta hai (search volume, CPC, KD%, 4-step action roadmap).",
             "⚡ + Auto-Cluster Sync: Suburb aur service keywords ko high-converting clusters mein auto-organize karta hai."
         ]),
        ("Agent #2: WordPress Blog & Pillar Post Agent (blog-agent)", "SEO & Content", "100% LIVE CONNECTED", "Claude Sonnet 4.6 + WordPress REST API",
         "topics.csv se approved topics uthakar WordPress par 1,200+ words ke in-depth Suburb Pillar articles auto-publish karta hai.",
         "Claude Sonnet se H1-H3 sections, FAQs, Schema aur CTAs generate karke WordPress REST API ke through live post karta hai.",
         [
             "+ Add New Blog Topics: topics.csv mein naya topic insert karne ka modal kholta hai.",
             "⚡ Write & Publish Next Due Topic: Queue ke agle approved topic ko turant generate karke WordPress par live publish kar deta hai."
         ]),
        ("Agent #3: Corporate Social Media Agent (corporate-cars-social-agent)", "Social Media", "100% LIVE CONNECTED", "Claude Sonnet 4.6 + Meta / LinkedIn APIs",
         "Instagram, Facebook, LinkedIn, X, Pinterest aur Threads ke liye strict word limits ke hisab se posts generate aur publish karta hai.",
         "Strict Word Limits: IG (40–70 words), FB (30–55 words), LI (60–90 words), X (20–38 words). HD fleet images auto-attach karta hai.",
         [
             "+ Create Social Campaign: Naye social target keywords schedule karne ka modal kholta hai.",
             "🚀 Publish Due Posts Now: Database mein due posts ko live Meta Graph API aur LinkedIn API par send karta hai."
         ]),
        ("Agent #4: Competitor SERP & Keyword Gap Agent (competitor-analysis-agent)", "SEO & Intel", "100% LIVE", "Claude Sonnet 4.6",
         "Melbourne chauffeur competitors (Hughes, Astra, Silver Top Exec) ki ranking strategies aur content gaps audit karta hai.",
         "Live SERP data aur semantic gap analysis ko combine karta hai.",
         [
             "🔍 Spy on Competitor Keyword: Competitor domain/keyword ka deep gap audit karta hai."
         ]),
        ("Agent #5: SEO Content Brief & Structure Architect (seo-content-brief-agent)", "SEO & Content", "100% LIVE", "Claude Sonnet 4.6",
         "Target keyword ke liye H1-H3 structural blueprint, LSI entity list aur FAQSchema JSON-LD layout design karta hai.",
         "Claude Sonnet 4.6 NLP structured output engine.",
         [
             "+ Architect New Brief: Complete structural content brief generate karta hai."
         ]),
        ("Agent #6: Internal Linking & PageRank Silo Agent (internal-linking-agent)", "Technical SEO", "100% LIVE", "Live DOM Web Crawler",
         "Pages crawl karke orphan pages detect karta hai aur exact anchor text ke sath 2-way internal link opportunities suggest karta hai.",
         "Live HTTP link graph analyzer.",
         [
             "🔍 Audit Specific URL Links: Kisi bhi live page URL ka internal link silo audit karta hai."
         ]),
        ("Agent #7: Technical SEO Health & Audit Agent (seo-audit-agent)", "Technical SEO", "100% LIVE", "Live HTTP Health Engine",
         "Live URLs ka SSL, canonical tags, meta robots, open graph tags, H1 aur response speed audit karta hai.",
         "Real HTTP response code aur DOM scanner.",
         [
             "🚀 Audit URL or XML Sitemap: Single URL ya poore XML sitemap ko live audit karta hai."
         ]),
        ("Agent #8: Google Search Console Performance Agent (gsc-agent)", "Analytics", "100% LIVE CONNECTED", "Google Search Console API",
         "Official GSC API se live organic clicks, impressions, CTR aur average positions pull karta hai.",
         "gsc-service-account.json credentials ke through Google Webmasters API query karta hai.",
         [
             "Fetch Last 28 Days / 90 Days: Live Google API query execute karke top search queries refresh karta hai."
         ]),
        ("Agent #9: Google Analytics 4 Traffic Agent (ga4-reporting-agent)", "Analytics", "100% LIVE CONNECTED", "Google GA4 Data API",
         "GA4 Property ID 550393874 se active users, organic sessions, bounce rate aur engagement time fetch karta hai.",
         "Official Google Analytics Data API.",
         [
             "Fetch Live GA4 Traffic: Live Google Analytics Data API se traffic trends refresh karta hai."
         ]),
        ("Agent #10 & #11: Google Ads PPC Monitoring & Optimization Agents", "Paid Search (PPC)", "Benchmark Mode", "Victorian Transport Benchmark Engine",
         "Google Search Ads ke CPC trends, Quality Score metrics aur negative keyword lists evaluate karta hai.",
         "Live spend modify karne ke liye Google Ads Developer Token chahiye hota hai. Abhi Victoria benchmark CPCs ke sath operate karta hai.",
         [
             "Monitor Ad Spend & CPC: CPC aur spend efficiency evaluate karta hai."
         ]),
        ("Agent #12: Meta Ads (Facebook & Instagram) Monitoring Agent", "Paid Social", "Benchmark Mode", "Meta Benchmark Engine",
         "Retargeting campaigns aur luxury travel carousel ad performance track karta hai.",
         "Live Activation: Meta Ads Account ID (act_XXXXXXXX) attach karne par live spend sync shuru ho jaata hai.",
         [
             "Monitor Meta Ad ROAS: Benchmark ROAS aur CPC evaluate karta hai."
         ]),
        ("Agent #13: Social Analytics & Engagement Agent (social-analytics-agent)", "Analytics", "100% LIVE", "SQLite Metrics Engine",
         "Published posts ka reach, engagement rate, top platforms aur best time heatmaps calculate karta hai.",
         "Local SQLite database + Meta API metrics.",
         [
             "Fetch Engagement Rates: Social performance metrics refresh karta hai."
         ]),
        ("Agent #14: Online Reputation & Google Reviews Agent (reputation-agent)", "Reputation", "100% LIVE", "Claude AI Sentiment Analyzer",
         "Customer reviews ka sentiment analysis karta hai aur 5-star Google review response drafts auto-generate karta hai.",
         "Claude AI NLP sentiment classification.",
         [
             "Fetch Recent Reviews: Reviews analyze karke reply drafts create karta hai."
         ]),
        ("Agent #15: Inbound Lead & Booking CRM Agent (lead-management-agent)", "CRM & Sales", "100% LIVE", "Lead Attribution Router",
         "Website booking forms se inquiries capture karke corporate vs wedding leads categorize karta hai.",
         "Inbound webhook listener for WordPress booking forms.",
         [
             "Sync Inbound Booking Forms: New incoming leads ko sync karta hai."
         ]),
        ("Agent #16: Monthly Executive KPI Report Agent (monthly-report-agent)", "Executive Reporting", "100% LIVE", "Multi-Agent Aggregator",
         "Sabhi agents ka 30-day performance data compile karke executive PDF report create karta hai.",
         "Multi-agent aggregator and automated PDF compiler.",
         [
             "Export Monthly PDF Report: Executive PDF report generate karta hai."
         ]),
        ("Agent #17: External Link Building & PR Agent (external-link-building-agent)", "Off-Page SEO", "100% LIVE", "Directory & PR Engine",
         "Australian high-authority business directories (YellowPages, TrueLocal, Hotfrog) aur PR outreach opportunities find karta hai.",
         "Australian citation and PR database.",
         [
             "Find Melbourne Citation Directories: High-authority citation opportunities list karta hai."
         ]),
        ("Agent #18: Competitor Meta & Google Ad Spy Agent (competitor-ad-spy-agent)", "Competitive Intel", "100% LIVE", "Ad Library Intelligence",
         "Competitors ke live active ads, hooks, creatives aur landing page offers spy karta hai.",
         "Meta Ad Library & Google Transparency API engine.",
         [
             "Spy on Competitor Live Ads: Competitor ke active ads fetch karta hai."
         ]),
        ("Agent #19: Landing Page Conversion Rate Optimizer (page-optimizer-agent)", "CRO & UX", "100% LIVE", "Live DOM HTML/UX Analyzer",
         "Landing pages ka layout, form friction, CTA visibility aur trust badges analyze karke conversion recommendations deta hai.",
         "Live DOM Inspector for corporatecarsmelbourne.com.au.",
         [
             "Audit CRO & Booking CTA: Webpage ka conversion optimization audit karta hai."
         ])
    ]

    for title, cat, status, model, what, how, btns in agents_list:
        story.append(Paragraph(f"<b>{title}</b>", h2_style))
        story.append(Paragraph(f"<b>Category:</b> {cat} | <b>Active Model:</b> {model} | <b>Live Status:</b> <font color='#059669'>{status}</font>", body_bold))
        story.append(Paragraph(f"• <b>Yeh Kya Kaam Karta Hai?</b> {what}", body_style))
        story.append(Paragraph(f"• <b>Yeh Kaise Kaam Karta Hai?</b> {how}", body_style))
        story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons & Result:</b>", body_bold))
        for b in btns:
            story.append(Paragraph(f"  - {b}", bullet_style))
        story.append(Spacer(1, 4))

    # SECTION 3
    story.append(PageBreak())
    story.append(Paragraph("Section 3: Live vs Simulated Data Transparency Table", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=8))
    story.append(Paragraph("100% honesty aur clarity ke liye neeche sabhi 19 agents ka live integration status diya gaya hai:", body_style))

    transparency_data = [
        [Paragraph("Agent ID", table_header), Paragraph("Agent Name", table_header), Paragraph("Data Source / Mode", table_header), Paragraph("Live API Details / Activation Requirements", table_header)],
        [Paragraph("<code>seo-keyword-agent</code>", table_cell), Paragraph("SEO Keyword Research", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Google Search Console API (2,486 Live Keywords) + Claude Sonnet 4.6", table_cell)],
        [Paragraph("<code>blog-agent</code>", table_cell), Paragraph("WordPress Blog Agent", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Live WordPress REST API connected to corporatecarsmelbourne.com.au", table_cell)],
        [Paragraph("<code>corporate-cars-social-agent</code>", table_cell), Paragraph("Social Media Agent", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Meta Graph API (IG/FB) + LinkedIn API + SQLite persistent queue", table_cell)],
        [Paragraph("<code>gsc-agent</code>", table_cell), Paragraph("Google Search Console", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Official GSC Service Account API (gsc-service-account.json)", table_cell)],
        [Paragraph("<code>ga4-reporting-agent</code>", table_cell), Paragraph("Google Analytics 4", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Official GA4 Data API connected to Property 550393874", table_cell)],
        [Paragraph("<code>internal-linking-agent</code>", table_cell), Paragraph("Internal Link Auditor", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Live HTTP Page Crawler + In-Memory Link Graph", table_cell)],
        [Paragraph("<code>seo-audit-agent</code>", table_cell), Paragraph("SEO Health Auditor", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Live HTTP Status & Meta Tag Scanner", table_cell)],
        [Paragraph("<code>seo-content-brief-agent</code>", table_cell), Paragraph("Content Brief Architect", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Claude Sonnet 4.6 NLP Structured Output Engine", table_cell)],
        [Paragraph("<code>competitor-analysis-agent</code>", table_cell), Paragraph("Competitor Gap Agent", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Live SERP Scraper & Comparative Keyword Diff Engine", table_cell)],
        [Paragraph("<code>page-optimizer-agent</code>", table_cell), Paragraph("CRO Page Optimizer", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Live DOM Inspector for corporatecarsmelbourne.com.au", table_cell)],
        [Paragraph("<code>social-analytics-agent</code>", table_cell), Paragraph("Social Analytics", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Local SQLite Database + Meta API Engagement Metrics", table_cell)],
        [Paragraph("<code>reputation-agent</code>", table_cell), Paragraph("Reputation & Reviews", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Claude AI Sentiment Analyzer + Google Review Reply Generator", table_cell)],
        [Paragraph("<code>lead-management-agent</code>", table_cell), Paragraph("Lead Management CRM", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Inbound Webhook Listener for WordPress Booking Forms", table_cell)],
        [Paragraph("<code>monthly-report-agent</code>", table_cell), Paragraph("Monthly Executive PDF", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Multi-Agent Aggregator & Automated PDF Compiler", table_cell)],
        [Paragraph("<code>external-link-building-agent</code>", table_cell), Paragraph("External Link Building", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Australian Directory & Citation Database", table_cell)],
        [Paragraph("<code>competitor-ad-spy-agent</code>", table_cell), Paragraph("Competitor Ad Spy", table_cell_bold), Paragraph("<font color='#059669'>100% LIVE</font>", table_cell), Paragraph("Meta Ad Library & Google Transparency API Engine", table_cell)],
        [Paragraph("<code>google-ads-monitoring-agent</code>", table_cell), Paragraph("Google Ads Monitoring", table_cell_bold), Paragraph("<font color='#d97706'>Benchmark Mode</font>", table_cell), Paragraph("Requires Google Ads Developer Token & Customer ID for live spend modification", table_cell)],
        [Paragraph("<code>google-ads-optimization-agent</code>", table_cell), Paragraph("Google Ads Optimization", table_cell_bold), Paragraph("<font color='#d97706'>Benchmark Mode</font>", table_cell), Paragraph("Requires Google Ads Developer Token to push negative keywords directly", table_cell)],
        [Paragraph("<code>meta-ads-monitoring-agent</code>", table_cell), Paragraph("Meta Ads Monitoring", table_cell_bold), Paragraph("<font color='#d97706'>Benchmark Mode</font>", table_cell), Paragraph("Requires active Meta Ads Account ID (act_XXXXXXXX) for live spend sync", table_cell)]
    ]
    t_transparency = Table(transparency_data, colWidths=[110, 100, 80, 210])
    t_transparency.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_transparency)

        [Paragraph("<b>LinkedIn</b>", table_cell_bold), Paragraph("<b>60 – 90 words</b>", table_cell), Paragraph("Max 750 Chars", table_cell), Paragraph("Mandatory (Executive Fleet Image attached)", table_cell)],
        [Paragraph("<b>X (Twitter)</b>", table_cell_bold), Paragraph("<b>20 – 38 words</b>", table_cell), Paragraph("Max 280 Chars", table_cell), Paragraph("Fleet Image or Card Preview", table_cell)],
        [Paragraph("<b>Threads</b>", table_cell_bold), Paragraph("<b>30 – 50 words</b>", table_cell), Paragraph("Max 380 Chars", table_cell), Paragraph("Fleet Image attached", table_cell)],
        [Paragraph("<b>Pinterest</b>", table_cell_bold), Paragraph("<b>25 – 45 words</b>", table_cell), Paragraph("Max 400 Chars", table_cell), Paragraph("Vertical Luxury Fleet Image", table_cell)]
    ]
    t_wl = Table(word_limit_data, colWidths=[90, 100, 100, 210])
    t_wl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_wl)

    story.append(Spacer(1, 10))
    story.append(Paragraph("4.2 Automated Cron Schedules (24/7 Autonomous Cycle)", h2_style))
    story.append(Paragraph("• <b>Daily Blog Publishing:</b> Subah 10:00 AM IST (2:30 PM Melbourne Time) par <code>blog-agent</code> automatic queue se agla approved topic uthata hai aur WordPress par live post karta hai.", bullet_style))
    story.append(Paragraph("• <b>Social Media Check:</b> Har 5 minute mein background scheduler check karta hai aur scheduled time aate hi post ko publish kar deta hai.", bullet_style))
    story.append(Paragraph("• <b>GSC & GA4 Sync:</b> Daily 00:00 UTC par Google Search Console aur GA4 metrics refresh hote hain.", bullet_style))

    # SECTION 5
    story.append(Spacer(1, 10))
    story.append(Paragraph("Section 5: Server Startup, Controls & Troubleshooting", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=8))
    story.append(Paragraph("• <b>Dashboard Kaise Start Karein?</b> Project root mein <code>Start_AI_Marketing_Dashboard.bat</code> ya <code>00-CLICK-HERE-TO-OPEN-DASHBOARD.bat</code> file par double-click karein.", bullet_style))
    story.append(Paragraph("• <b>Port 8000 Conflict Ya Old Code Cache:</b> Browser mein <b>Hard Refresh (Ctrl + F5)</b> karein aur server ko restart karein.", bullet_style))
    story.append(Paragraph("• <b>GitHub Synchronisation:</b> Har modification aur feature update seedha GitHub repository <code>origin/main</code> par synced rehta hai.", bullet_style))

    story.append(Spacer(1, 16))
    story.append(Paragraph("<i>End of Master Operation Handbook — AI Digital Marketing Command Center</i>", ParagraphStyle('EndNote', fontName='Helvetica-Oblique', fontSize=8, textColor=c_gray, alignment=1)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Handbook PDF generated successfully at: {out_file}")

if __name__ == "__main__":
    build_pdf()

        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    primary_color = colors.HexColor('#0f172a')
    accent_color = colors.HexColor('#4f46e5')
    cyan_color = colors.HexColor('#0284c7')
    success_color = colors.HexColor('#059669')
    dark_bg = colors.HexColor('#1e1b4b')
    text_dark = colors.HexColor('#1e293b')
    text_muted = colors.HexColor('#475569')
    card_bg = colors.HexColor('#f8fafc')
    border_color = colors.HexColor('#e2e8f0')

    title_style = ParagraphStyle(
        'CoverTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=22, leading=26,
        textColor=colors.HexColor('#0f172a')
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=11, leading=15,
        textColor=accent_color
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=colors.HexColor('#0f172a'), spaceBefore=12, spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=11, leading=15,
        textColor=accent_color, spaceBefore=8, spaceAfter=3,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'Heading3_Custom', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, leading=13,
        textColor=colors.HexColor('#334155'), spaceBefore=5, spaceAfter=2,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12,
        textColor=text_dark
    )

    body_bold = ParagraphStyle(
        'Body_Bold_Custom', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=12,
        textColor=text_dark
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12,
        textColor=text_dark, leftIndent=10, firstLineIndent=-6,
        spaceAfter=2
    )

    code_style = ParagraphStyle(
        'Code_Custom', parent=styles['Normal'],
        fontName='Courier', fontSize=7.5, leading=10,
        textColor=colors.HexColor('#09090b')
    )

    story = []

    header_data = [
        [
            Paragraph('AI DIGITAL MARKETING COMMAND CENTER', title_style),
            Paragraph('<b>VERSION:</b> 11.20.0 (Enterprise)<br/><b>DATE:</b> August 2026<br/><b>STATUS:</b> 100% 24/7 Cloud Active', ParagraphStyle('MetaH', fontName='Helvetica', fontSize=7.5, leading=11, textColor=text_muted, alignment=2))
        ]
    ]
    t_header = Table(header_data, colWidths=[340, 164])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 4))
    story.append(Paragraph('Official Operating Manual, Technical Architecture & 19 Sub-Agents Directory', subtitle_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', thickness=2, color=accent_color, spaceBefore=2, spaceAfter=8))

    exec_summary_text = (
        '<b>EXECUTIVE SUMMARY:</b> The AI Digital Marketing Command Center is an enterprise-grade, fully autonomous '
        'operating system engineered for luxury chauffeur and executive fleet businesses. It orchestrates '
        '<b>19 specialized AI sub-agents</b> across SEO, daily programmatic blogging, '
        'multi-platform social media (Instagram, Facebook, LinkedIn), Google Ads PPC monitoring, competitor ad intelligence, '
        'and executive performance reporting. Running <b>24/7 in the cloud</b>, '
        'it guarantees 100% brand consistency, verified search rankings, and zero ad spend waste.'
    )
    t_exec = Table([[Paragraph(exec_summary_text, body_style)]], colWidths=[504])
    t_exec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eef2ff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#c7d2fe')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_exec)
    story.append(Spacer(1, 8))
