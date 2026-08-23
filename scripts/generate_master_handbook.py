import os
import sys
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Numbered Canvas for "Page X of Y" and Running Header/Footer
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return  # Skip cover page

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header
        self.drawString(54, letter[1] - 36, "AI Digital Marketing Command Center — Master Operation Handbook")
        self.drawRightString(letter[0] - 54, letter[1] - 36, "Corporate Cars Melbourne")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Footer
        self.line(54, 45, letter[0] - 54, 45)
        self.drawString(54, 32, "Confidential & Proprietary — Automated Marketing Intelligence Engine")
        self.drawRightString(letter[0] - 54, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_handbook_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    c_primary = colors.HexColor("#0f172a")    # Slate 900
    c_navy = colors.HexColor("#1e293b")       # Slate 800
    c_cyan = colors.HexColor("#0284c7")       # Sky 600
    c_cyan_dark = colors.HexColor("#0369a1")  # Sky 700
    c_emerald = colors.HexColor("#059669")    # Emerald 600
    c_purple = colors.HexColor("#7c3aed")     # Violet 600
    c_amber = colors.HexColor("#d97706")      # Amber 600
    c_gray = colors.HexColor("#475569")       # Slate 600
    c_light_bg = colors.HexColor("#f8fafc")   # Slate 50
    c_card_bg = colors.HexColor("#f1f5f9")    # Slate 100

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
        textColor=c_primary,
        alignment=0
    )
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=18,
        textColor=c_cyan_dark,
        alignment=0
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_cyan_dark,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6
    )
    body_bold = ParagraphStyle(
        'Body_Bold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b")
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor("#0f172a")
    )
    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    story = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 40))
    story.append(Paragraph("AI DIGITAL MARKETING COMMAND CENTER", ParagraphStyle('SuperTitle', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=c_purple, spaceAfter=8)))
    story.append(Paragraph("Master Operation & Agent Reference Handbook", title_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=3, color=c_cyan, spaceBefore=4, spaceAfter=14))
    story.append(Paragraph("Comprehensive Guide to Dashboard Controls, Clickable Buttons, 19 Autonomous AI Agents, Live APIs, and Operational Workflows", subtitle_style))
    story.append(Spacer(1, 24))

    # Meta Info Card
    meta_data = [
        [Paragraph("<b>Primary Workspace:</b>", table_cell), Paragraph("Corporate Cars Melbourne (corporatecarsmelbourne.com.au)", table_cell)],
        [Paragraph("<b>System Version:</b>", table_cell), Paragraph("v12.4 Enterprise Autonomous Edition", table_cell)],
        [Paragraph("<b>Active AI Engines:</b>", table_cell), Paragraph("Claude 3.5 Sonnet / Claude Sonnet 4.6, GPT-4o, DeepSeek, Gemini 2.5", table_cell)],
        [Paragraph("<b>Live Connected APIs:</b>", table_cell), Paragraph("Google Search Console (GSC), GA4 Data API, WordPress REST API, Meta Graph API, LinkedIn API", table_cell)],
        [Paragraph("<b>Publication Date:</b>", table_cell), Paragraph(datetime.now().strftime("%B %d, %Y"), table_cell)],
        [Paragraph("<b>Target Audience:</b>", table_cell), Paragraph("Executives, Marketing Managers & Operations Team", table_cell)]
    ]
    meta_table = Table(meta_data, colWidths=[150, 350])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_card_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 30))
    story.append(Paragraph("<b>Handbook Objectives (Is Guide Ka Maqsad):</b>", body_bold))
    story.append(Paragraph("1. Dashboard kholte hi screen par dikhne wale har button, icon aur card ka exact purpose aur result samjhana.", bullet_style))
    story.append(Paragraph("2. Sabhi 19 AI Agents ki complete working, unke report modal ke clickable buttons aur execution flow ko define karna.", bullet_style))
    story.append(Paragraph("3. 100% Reality & Transparency batana ki kaunse agents mein LIVE API data aa raha hai aur jinme simulated data hai unme kyu hai.", bullet_style))
    story.append(Paragraph("4. Word limits, image attachments, cron schedules aur safety rules ka reference provide karna.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # TABLE OF CONTENTS / SUMMARY
    # =========================================================================
    story.append(Paragraph("Table of Contents (Handbook Index)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=12))

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
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(toc_table)
    story.append(Spacer(1, 14))

    # =========================================================================
    # SECTION 1: DASHBOARD UI WALKTHROUGH
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("Section 1: Dashboard UI & Interactive Controls Walkthrough", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("Jab aap browser mein Dashboard (<b>http://127.0.0.1:8000</b>) open karte hain, toh screen par structured dark-mode command center dikhta hai. Is section mein har button, icon aur card ka exact function define kiya gaya hai.", body_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph("1.1 Top Navigation & Header Controls", h2_style))
    
    header_ui_data = [
        [Paragraph("UI Element / Button", table_header), Paragraph("Icon / Visual", table_header), Paragraph("Click Karne Par Kya Hota Hai? (Action & Result)", table_header)],
        [
            Paragraph("<b>Website Switcher Dropdown</b>", table_cell_bold),
            Paragraph("<font color='#0284c7'>🌐 Dropdown</font>", table_cell),
            Paragraph("Ispe click karke aap active website change kar sakte hain (e.g. <i>Corporate Cars Melbourne</i> ya koi doosra brand). Ispe click karte hi saare 19 agents, reports, GSC data aur keywords us specific website ke filter ho jaate hain.", table_cell)
        ],
        [
            Paragraph("<b>Admin Lock / Unlock Button</b>", table_cell_bold),
            Paragraph("<font color='#d97706'>🔒 / 🔓 Shield</font>", table_cell),
            Paragraph("Dashboard by default 'Viewer Mode' (Read-Only) mein rehta hai taaki koi accidental changes na ho. Is button par click karne par <b>Admin Authentication Modal</b> khulta hai. Admin password daalne ke baad live tasks run karne, blog topic schedule karne aur campaigns publish karne ke permissions unlock ho jaate hain.", table_cell)
        ],
        [
            Paragraph("<b>+ Add Campaign Button</b>", table_cell_bold),
            Paragraph("<font color='#7c3aed'>+ Sparkles</font>", table_cell),
            Paragraph("Global campaign creation modal kholta hai jahan se aap Blog + Social + SEO ka combined multi-channel marketing campaign 1-click mein start kar sakte hain.", table_cell)
        ],
        [
            Paragraph("<b>+ Add Blog Topics Button</b>", table_cell_bold),
            Paragraph("<font color='#0284c7'>+ Pen/Blog</font>", table_cell),
            Paragraph("Ek interactive modal khulta hai jahan aap multiple new blog topic titles, primary keywords aur suburbs add kar sakte hain. Submit karne par yeh direct <code>blog-agent/topics.csv</code> mein auto-insert ho jaate hain.", table_cell)
        ],
        [
            Paragraph("<b>+ Add Social Campaign Button</b>", table_cell_bold),
            Paragraph("<font color='#059669'>+ ShareNodes</font>", table_cell),
            Paragraph("Social media keyword campaign modal open karta hai jahan aap target keywords aur theme add kar sakte hain. Submit karne par keywords seedha SQLite database (<code>social_agent.db</code>) mein save hote hain.", table_cell)
        ],
        [
            Paragraph("<b>⬇ Export Monthly Report (PDF)</b>", table_cell_bold),
            Paragraph("<font color='#d97706'>⬇ PDF Icon</font>", table_cell),
            Paragraph("Sabhi 19 agents ki 30-day performance report ko compile karke executive PDF document generate aur browser mein auto-download karta hai.", table_cell)
        ],
        [
            Paragraph("<b>Live Clock & Status Indicator</b>", table_cell_bold),
            Paragraph("<font color='#059669'>🟢 Pulsing Dot</font>", table_cell),
            Paragraph("Melbourne/AEST live time dikhata hai aur batata hai ki backend API server active hai.", table_cell)
        ]
    ]
    t_header = Table(header_ui_data, colWidths=[120, 80, 300])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_header)

    story.append(Spacer(1, 10))
    story.append(Paragraph("1.2 Top KPI Summary Cards", h2_style))
    story.append(Paragraph("Header ke theek niche 4 dynamic KPI cards show hote hain:", body_style))
    story.append(Paragraph("• <b>Active AI Agents:</b> Total enabled agents (19/19 Operational) dikhata hai.", bullet_style))
    story.append(Paragraph("• <b>Total Completed Tasks:</b> Abhi tak execute huye autonomous marketing tasks ka live counter.", bullet_style))
    story.append(Paragraph("• <b>System Success Rate:</b> API calls aur content executions ka success percentage (99.4%+).", bullet_style))
    story.append(Paragraph("• <b>Est. Token / AI Cost (USD):</b> Claude Sonnet aur AI models par kharch huye live token dollars ka hisab.", bullet_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("1.3 Agent Card Structure & 4 Interactive Action Buttons", h2_style))
    story.append(Paragraph("Har agent ke card par 4 standard interactive control buttons hote hain:", body_style))

    agent_btn_data = [
        [Paragraph("Button Name", table_header), Paragraph("Button Style / Color", table_header), Paragraph("Action & Live Result", table_header)],
        [
            Paragraph("<b>👁️ View Report</b>", table_cell_bold),
            Paragraph("<font color='#0284c7'>Cyan / Blue Outline</font>", table_cell),
            Paragraph("Us specific agent ka deep performance audit report modal kholta hai (e.g. SEO metrics, live GSC table, blog schedule, social posts, GA4 stats, keyword clusters).", table_cell)
        ],
        [
            Paragraph("<b>⚡ Run Task / Quick Action</b>", table_cell_bold),
            Paragraph("<font color='#059669'>Solid Gradient Green</font>", table_cell),
            Paragraph("Agent ko turant manual execution command bhejta hai (e.g. Blog Agent naya article likhna shuru kar dega, Social Agent due posts publish kar dega, SEO Agent audit run karega).", table_cell)
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
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_agent_btn)

    # =========================================================================
    # SECTION 2: ALL 19 AGENTS IN-DEPTH BREAKDOWN
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("Section 2: Complete Deep-Dive of All 19 AI Agents", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("Is section mein system ke sabhi 19 AI Agents ki detailed specification, unki working mechanism, report modal ke buttons aur unki live API status ki poori jankari di gayi hai.", body_style))

    # --- AGENT 1 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #1: SEO Keyword Research Agent (<code>seo-keyword-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> SEO & Content | <b>Active Model:</b> Claude Sonnet 4.6 & GSC Engine | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Melbourne local suburbs, airport transfers aur luxury chauffeur vertical ke high-intent commercial keywords discover karta hai, unka search volume, KD% aur intent classify karta hai.", body_style))
    story.append(Paragraph("• <b>Yeh Kaise Kaam Karta Hai?</b> Google Search Console ke live search queries aur Claude AI semantic router ko combine karke suburb-level clustering generate karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>🎯 Check Live Google SERP Rankings:</b> Google Search Console API se live <b>2,486+ genuine keywords</b> ki real SERP ranking table kholta hai jisme exact position (#1.8, #2.2, #5.6, #13.0), impressions, CTR aur landing page URLs show hote hain.", bullet_style))
    story.append(Paragraph("  2. <b>🔍 + Research Any Custom Keyword:</b> Custom Keyword Intelligence Lab kholta hai jahan aap koi bhi custom keyword type karke live AI search volume, CPC, KD% aur 4-step action roadmap generate kar sakte hain.", bullet_style))
    story.append(Paragraph("  3. <b>⚡ + Auto-Cluster Sync:</b> Suburb aur service keywords ko high-converting clusters mein auto-organize karta hai.", bullet_style))

    # --- AGENT 2 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #2: WordPress Blog & Pillar Content Agent (<code>blog-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> SEO & Content | <b>Active Model:</b> Claude Sonnet 4.6 | <b>Live Status:</b> 100% LIVE CONNECTED", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> <code>blog-agent/topics.csv</code> se approved topics uthata hai aur WordPress par 1,200+ words ke in-depth SEO Suburb Pillar articles auto-write aur auto-publish karta hai.", body_style))
    story.append(Paragraph("• <b>Yeh Kaise Kaam Karta Hai?</b> Claude Sonnet 4.6 se structured H1-H3 sections, FAQs, LocalBusiness schema aur high-converting CTAs generate karke WordPress REST API (<code>/wp-json/wp/v2/posts</code>) ke through publish karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>+ Add New Blog Topics:</b> Naye topics add karne ka modal kholta hai.", bullet_style))
    story.append(Paragraph("  2. <b>⚡ Write & Publish Next Due Topic:</b> Queue ke agle approved topic ko turant generate karke WordPress par live publish kar deta hai.", bullet_style))

    # --- AGENT 3 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #3: Corporate Social Media Agent (<code>corporate-cars-social-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Social Media & Branding | <b>Active Model:</b> Claude Sonnet 4.6 | <b>Live Status:</b> 100% LIVE CONNECTED", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Instagram, Facebook, LinkedIn, X, Pinterest aur Threads ke liye platform-specific word limits ke hisab se compact captions generate karta hai aur HD fleet images ke sath auto-publish karta hai.", body_style))
    story.append(Paragraph("• <b>Strict Word Limits:</b> Instagram (40–70 words), Facebook (30–55 words), LinkedIn (60–90 words), X (20–38 words), Threads (30–50 words).", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>+ Create Social Campaign:</b> Naye social target keywords schedule karne ka modal kholta hai.", bullet_style))
    story.append(Paragraph("  2. <b>🚀 Publish Due Posts Now:</b> SQLite database mein schedule huye due posts ko live Meta Graph API aur LinkedIn API par turant send kar deta hai.", bullet_style))

    # --- AGENT 4 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #4: Competitor SERP & Keyword Gap Agent (<code>competitor-analysis-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> SEO & Competitive Intel | <b>Active Model:</b> Claude Sonnet 4.6 | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Melbourne ke top chauffeur competitors (e.g. Hughes, Astra, Silver Top Exec) ki ranking strategies, content gaps aur missed keyword opportunities ko audit karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>🔍 Spy on Competitor Keyword:</b> Kisi bhi competitor domain ya keyword ka deep comparative gap audit karta hai.", bullet_style))

    # --- AGENT 5 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #5: SEO Content Brief & Structure Architect (<code>seo-content-brief-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> SEO & Content | <b>Active Model:</b> Claude Sonnet 4.6 | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Kisi bhi target keyword ke liye comprehensive H1-H3 structural blueprint, LSI entity injection list, FAQSchema JSON-LD aur conversion CTA layout design karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>+ Architect New Brief:</b> Naye target topic ke liye complete structural content brief generate karta hai.", bullet_style))

    # --- AGENT 6 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #6: Internal Linking & PageRank Silo Agent (<code>internal-linking-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> SEO & Technical | <b>Active Model:</b> Live DOM Web Crawler | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Website ke pages ko live crawl karke orphan pages detect karta hai aur topic relevance ke hisab se exact anchor text ke sath 2-way internal link opportunities suggest karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>🔍 Audit Specific URL Links:</b> Kisi bhi live page URL ko paste karke uske internal linking silos ka audit karta hai.", bullet_style))

    # --- AGENT 7 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #7: Technical SEO Health & Audit Agent (<code>seo-audit-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Technical SEO | <b>Active Model:</b> Live HTTP Health Engine | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Live website URLs ka SSL, canonical tags, meta robots, open graph tags, H1 presence aur response speed audit karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>🚀 Audit URL or XML Sitemap:</b> Single URL ya poore sitemap ko live audit karta hai.", bullet_style))

    # --- AGENT 8 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #8: Google Search Console Performance Agent (<code>gsc-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Analytics & Performance | <b>Active Model:</b> Google Search Console API | <b>Live Status:</b> 100% LIVE CONNECTED", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Official Google Search Console API se live organic clicks, impressions, CTR aur average positions pull karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>Fetch Last 28 Days / 90 Days:</b> Live Google API query execute karke top search queries refresh karta hai.", bullet_style))

    # --- AGENT 9 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #9: Google Analytics 4 Traffic Agent (<code>ga4-reporting-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Analytics & Tracking | <b>Active Model:</b> Official Google GA4 Data API | <b>Live Status:</b> 100% LIVE CONNECTED", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> GA4 Property ID <code>550393874</code> (Measurement ID <code>G-2CM2BW6QKN</code>) se live active users, organic sessions, bounce rate aur engagement time fetch karta hai.", body_style))
    story.append(Paragraph("• <b>Report Modal Ke Clickable Buttons:</b>", body_bold))
    story.append(Paragraph("  1. <b>Fetch Live GA4 Traffic:</b> Live Google Analytics Data API se traffic trends refresh karta hai.", bullet_style))

    # --- AGENT 10 & 11 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #10 & #11: Google Ads PPC Monitoring & Optimization Agents", h2_style))
    story.append(Paragraph("<b>Category:</b> Paid Search (PPC) | <b>Active Model:</b> Victorian Chauffeur Benchmark Engine | <b>Live Status:</b> Benchmark Mode (Developer Token Required for Live Spend Changes)", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Google Search Ads ke CPC trends, Quality Score metrics, search terms waste aur negative keyword lists evaluate karta hai.", body_style))
    story.append(Paragraph("• <b>Live Kyu Nahi Hai?</b> Google Ads live account se ad spend modify karne ke liye Google Ads Enterprise Developer Token ki zaroorat hoti hai. Abhi yeh Victoria transport benchmark CPCs ke sath operate karta hai.", body_style))

    # --- AGENT 12 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #12: Meta Ads (Facebook & Instagram) Monitoring Agent", h2_style))
    story.append(Paragraph("<b>Category:</b> Paid Social | <b>Active Model:</b> Meta Benchmark Engine | <b>Live Status:</b> Benchmark Mode", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Retargeting campaigns, lead gen forms aur luxury travel carousel ad performance ko track karta hai.", body_style))
    story.append(Paragraph("• <b>Live Activation:</b> Meta Ads Account ID (<code>act_XXXXXXXX</code>) attach karne par live spend sync shuru ho jaata hai.", body_style))

    # --- AGENT 13 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #13: Social Analytics & Engagement Agent (<code>social-analytics-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Analytics | <b>Active Model:</b> SQLite Metrics Engine | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Published posts ka reach, engagement rate, top performing platforms aur best time-to-post heatmaps calculate karta hai.", body_style))

    # --- AGENT 14 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #14: Online Reputation & Google Reviews Agent (<code>reputation-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Reputation & Trust | <b>Active Model:</b> Claude AI Sentiment Analyzer | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Customer reviews ka sentiment analysis karta hai aur 5-star Google review response drafts auto-generate karta hai.", body_style))

    # --- AGENT 15 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #15: Inbound Lead & Booking CRM Agent (<code>lead-management-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Sales & CRM | <b>Active Model:</b> Lead Attribution Router | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Website booking forms se aane wale inquiries ko capture karke corporate vs wedding leads categorize karta hai.", body_style))

    # --- AGENT 16 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #16: Monthly Executive KPI Report Agent (<code>monthly-report-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Executive Reporting | <b>Active Model:</b> Multi-Agent Aggregator | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Sabhi agents ka 30-day performance data compile karke executive PDF report create karta hai.", body_style))

    # --- AGENT 17 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #17: External Link Building & PR Agent (<code>external-link-building-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Off-Page SEO | <b>Active Model:</b> Directory & PR Engine | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Australian high-authority business directories (YellowPages, TrueLocal, Hotfrog) aur PR outreach opportunities find karta hai.", body_style))

    # --- AGENT 18 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #18: Competitor Meta & Google Ad Spy Agent (<code>competitor-ad-spy-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> Competitive Intel | <b>Active Model:</b> Ad Library Intelligence | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Chauffeur competitors ke live active ads, hooks, creatives aur landing page offers ko spy karke report karta hai.", body_style))

    # --- AGENT 19 ---
    story.append(Spacer(1, 8))
    story.append(Paragraph("Agent #19: Landing Page Conversion Rate Optimizer (<code>page-optimizer-agent</code>)", h2_style))
    story.append(Paragraph("<b>Category:</b> CRO & UX | <b>Active Model:</b> Live DOM HTML/UX Analyzer | <b>Live Status:</b> 100% LIVE", body_bold))
    story.append(Paragraph("• <b>Yeh Kya Kaam Karta Hai?</b> Landing pages ka layout, form friction, CTA visibility aur trust badges analyze karke conversion recommendations deta hai.", body_style))

    # =========================================================================
    # SECTION 3: LIVE VS SIMULATED TRANSPARENCY TABLE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("Section 3: Live vs Simulated Data Transparency Table", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("100% honesty aur clarity ke liye neeche sabhi 19 agents ka live integration status diya gaya hai:", body_style))
    story.append(Spacer(1, 6))

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
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_transparency)

    # =========================================================================
    # SECTION 4: AUTONOMOUS SCHEDULES & CONTENT RULES
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("Section 4: Autonomous Schedules, Word Limits & Content Rules", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("4.1 Strict Social Media Word Limits Table", h2_style))
    story.append(Paragraph("Aapke nirdesh ke anusar, sabhi social media platforms ke liye strict short word count limits set ki gayi hain:", body_style))

    word_limit_data = [
        [Paragraph("Social Platform", table_header), Paragraph("Target Word Range", table_header), Paragraph("Hard Character Cap", table_header), Paragraph("Mandatory Fleet Image Rule", table_header)],
        [Paragraph("<b>Instagram</b>", table_cell_bold), Paragraph("<b>40 – 70 words</b>", table_cell), Paragraph("Max 550 Chars", table_cell), Paragraph("Mandatory (Mercedes S-Class/V-Class/Sprinter attached)", table_cell)],
        [Paragraph("<b>Facebook</b>", table_cell_bold), Paragraph("<b>30 – 55 words</b>", table_cell), Paragraph("Max 450 Chars", table_cell), Paragraph("Mandatory (HD Fleet Image attached)", table_cell)],
        [Paragraph("<b>LinkedIn</b>", table_cell_bold), Paragraph("<b>60 – 90 words</b>", table_cell), Paragraph("Max 750 Chars", table_cell), Paragraph("Mandatory (Executive Fleet Image attached)", table_cell)],
        [Paragraph("<b>X (Twitter)</b>", table_cell_bold), Paragraph("<b>20 – 38 words</b>", table_cell), Paragraph("Max 280 Chars", table_cell), Paragraph("Fleet Image or Card Preview", table_cell)],
        [Paragraph("<b>Threads</b>", table_cell_bold), Paragraph("<b>30 – 50 words</b>", table_cell), Paragraph("Max 380 Chars", table_cell), Paragraph("Fleet Image attached", table_cell)],
        [Paragraph("<b>Pinterest</b>", table_cell_bold), Paragraph("<b>25 – 45 words</b>", table_cell), Paragraph("Max 400 Chars", table_cell), Paragraph("Vertical Luxury Fleet Image", table_cell)]
    ]
    t_wl = Table(word_limit_data, colWidths=[90, 100, 100, 210])
    t_wl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_navy),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_light_bg]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_wl)

    story.append(Spacer(1, 12))
    story.append(Paragraph("4.2 Automated Cron Schedules (24/7 Autonomous Cycle)", h2_style))
    story.append(Paragraph("• <b>Daily Blog Publishing:</b> Subah 10:00 AM IST (2:30 PM Melbourne Time) par <code>blog-agent</code> automatic queue se agla approved topic uthata hai aur WordPress par live post karta hai.", bullet_style))
    story.append(Paragraph("• <b>Social Media Check:</b> Har 5 minute mein background scheduler check karta hai aur scheduled time aate hi post ko publish kar deta hai.", bullet_style))
    story.append(Paragraph("• <b>GSC & GA4 Sync:</b> Daily 00:00 UTC par Google Search Console aur GA4 metrics refresh hote hain.", bullet_style))

    # =========================================================================
    # SECTION 5: TROUBLESHOOTING & SYSTEM STARTUP
    # =========================================================================
    story.append(Spacer(1, 14))
    story.append(Paragraph("Section 5: Server Startup, Controls & Troubleshooting", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=c_cyan, spaceBefore=2, spaceAfter=10))

    story.append(Paragraph("• <b>Dashboard Kaise Start Karein?</b> Project root mein <code>Start_AI_Marketing_Dashboard.bat</code> ya <code>00-CLICK-HERE-TO-OPEN-DASHBOARD.bat</code> file par double-click karein. Yeh background mein FastAPI server start karke browser mein dashboard open kar deta hai.", bullet_style))
    story.append(Paragraph("• <b>Port 8000 Conflict Ya Old Code Cache:</b> Agar kabhi new button par 404 ya purana response aaye, toh browser mein <b>Hard Refresh (Ctrl + F5)</b> karein aur terminal mein server ko restart karein.", bullet_style))
    story.append(Paragraph("• <b>GitHub Synchronisation:</b> Har modification aur feature update seedha GitHub repository <code>origin/main</code> par synced aur push rehta hai.", bullet_style))

    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>End of Master Operation Handbook — AI Digital Marketing Command Center</i>", ParagraphStyle('EndNote', fontName='Helvetica-Oblique', fontSize=8.5, textColor=c_gray, alignment=1)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Handbook PDF generated successfully at: {output_path}")

if __name__ == "__main__":
    out_file = os.path.join(os.getcwd(), "AI_Digital_Marketing_Master_Handbook.pdf")
    build_handbook_pdf(out_file)
