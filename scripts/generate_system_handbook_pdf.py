import os
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

PDF_OUTPUT_PATH = Path('AI_Digital_Marketing_Command_Center_Official_Manual.pdf').resolve()

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
        self.saveState()
        self.setFont('Helvetica-Bold', 8)
        self.setFillColor(colors.HexColor('#64748b'))
        
        if self._pageNumber > 1:
            self.drawString(54, 11 * inch - 36, 'AI DIGITAL MARKETING COMMAND CENTER - OFFICIAL OPERATING MANUAL')
            self.drawRightString(8.5 * inch - 54, 11 * inch - 36, 'CONFIDENTIAL & PROPRIETARY')
            self.setStrokeColor(colors.HexColor('#cbd5e1'))
            self.setLineWidth(0.75)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)
        
        self.setStrokeColor(colors.HexColor('#e2e8f0'))
        self.setLineWidth(0.75)
        self.line(54, 45, 8.5 * inch - 54, 45)
        
        self.setFont('Helvetica', 8)
        self.drawString(54, 30, 'Enterprise AI Marketing Operating System | 24/7 Autonomous Cloud Engine')
        page_str = f'Page {self._pageNumber} of {page_count}'
        self.drawRightString(8.5 * inch - 54, 30, page_str)
        self.restoreState()

def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_OUTPUT_PATH),
        pagesize=letter,
        leftMargin=54,
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
