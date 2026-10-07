import os
import math
from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas


class CertificateGenerator:
    """Predefined professional certificate template generator using ReportLab."""

    PAGE_WIDTH, PAGE_HEIGHT = landscape(letter)  # 792 x 612 pt

    # Design palette
    COLOR_PRIMARY = colors.HexColor("#0F2A4A")      # Rich Navy Blue
    COLOR_GOLD = colors.HexColor("#C59B27")         # Classic Metallic Gold
    COLOR_LIGHT_GOLD = colors.HexColor("#E5C158")   # Bright Gold Accent
    COLOR_DARK_TEXT = colors.HexColor("#1E293B")    # Slate Charcoal
    COLOR_MUTED_TEXT = colors.HexColor("#64748B")   # Muted Slate Gray
    COLOR_BORDER_FRAME = colors.HexColor("#E2E8F0") # Subtle Inner Border

    @classmethod
    def _draw_ornate_borders(cls, c: canvas.Canvas) -> None:
        """Draw decorative double borders and corner accents."""
        w, h = cls.PAGE_WIDTH, cls.PAGE_HEIGHT

        # Outer thick navy border
        c.setStrokeColor(cls.COLOR_PRIMARY)
        c.setLineWidth(5.0)
        c.rect(24, 24, w - 48, h - 48)

        # Gap frame - gold border
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setLineWidth(2.0)
        c.rect(32, 32, w - 64, h - 64)

        # Fine inner line
        c.setStrokeColor(cls.COLOR_BORDER_FRAME)
        c.setLineWidth(0.75)
        c.rect(36, 36, w - 72, h - 72)

        # Decorative Corner Brackets
        corner_size = 20
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setLineWidth(2.5)

        # Top-Left
        c.line(40, h - 40, 40 + corner_size, h - 40)
        c.line(40, h - 40, 40, h - 40 - corner_size)

        # Top-Right
        c.line(w - 40, h - 40, w - 40 - corner_size, h - 40)
        c.line(w - 40, h - 40, w - 40, h - 40 - corner_size)

        # Bottom-Left
        c.line(40, 40, 40 + corner_size, 40)
        c.line(40, 40, 40, 40 + corner_size)

        # Bottom-Right
        c.line(w - 40, 40, w - 40 - corner_size, 40)
        c.line(w - 40, 40, w - 40, 40 + corner_size)

    @classmethod
    def _draw_top_crest(cls, c: canvas.Canvas, center_x: float, y: float) -> None:
        """Draw an elegant circular vector badge at the top."""
        c.saveState()
        # Gold emblem circles
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setFillColor(colors.HexColor("#FEF3C7"))  # Soft warm background
        c.setLineWidth(1.5)
        c.circle(center_x, y, 16, stroke=1, fill=1)

        c.setFillColor(cls.COLOR_GOLD)
        c.circle(center_x, y, 12, stroke=0, fill=1)

        # Center star/diamond
        c.setFillColor(colors.white)
        p = c.beginPath()
        p.moveTo(center_x, y + 7)
        p.lineTo(center_x + 5, y)
        p.lineTo(center_x, y - 7)
        p.lineTo(center_x - 5, y)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

        # Small side wings
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setLineWidth(1.2)
        c.line(center_x - 22, y, center_x - 45, y)
        c.line(center_x + 22, y, center_x + 45, y)
        c.circle(center_x - 47, y, 2, fill=1, stroke=0)
        c.circle(center_x + 47, y, 2, fill=1, stroke=0)
        c.restoreState()

    @classmethod
    def _draw_gold_divider(cls, c: canvas.Canvas, center_x: float, y: float, width: float = 320) -> None:
        """Draw a horizontal flourish with a center diamond."""
        half = width / 2
        c.saveState()
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setLineWidth(1.2)
        c.line(center_x - half, y, center_x - 12, y)
        c.line(center_x + 12, y, center_x + half, y)

        # Small diamond in center
        c.setFillColor(cls.COLOR_GOLD)
        p = c.beginPath()
        p.moveTo(center_x, y + 4)
        p.lineTo(center_x + 5, y)
        p.lineTo(center_x, y - 4)
        p.lineTo(center_x - 5, y)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.restoreState()

    @classmethod
    def _draw_verification_seal(cls, c: canvas.Canvas, x: float, y: float, code: str) -> None:
        """Draw official certificate verification seal badge."""
        c.saveState()
        radius = 28

        # Scalloped/geared outer ring
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setFillColor(colors.HexColor("#FFFBEB"))
        c.setLineWidth(1.5)
        c.circle(x, y, radius, stroke=1, fill=1)

        # Inner ring
        c.setStrokeColor(cls.COLOR_GOLD)
        c.setLineWidth(0.8)
        c.circle(x, y, radius - 4, stroke=1, fill=0)

        # Seal text
        c.setFillColor(cls.COLOR_PRIMARY)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(x, y + 10, "OFFICIAL")
        c.drawCentredString(x, y + 1, "CERTIFIED")
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(x, y - 9, "AUTHENTIC")

        # Verification code below seal
        c.setFillColor(cls.COLOR_MUTED_TEXT)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x, y - radius - 14, f"ID: {code}")
        c.restoreState()

    @classmethod
    def _wrap_text(cls, text: str, max_chars_per_line: int = 75) -> list[str]:
        """Simple text line wrapping to keep lines centered and balanced."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + (1 if current_line else 0) <= max_chars_per_line:
                current_line.append(word)
                current_length += len(word) + (1 if len(current_line) > 1 else 0)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    @classmethod
    def generate(
        cls,
        recipient_name: str,
        title: str,
        description: str,
        issuer_name: str,
        issuer_title: Optional[str],
        issue_date: str,
        certificate_code: str,
        output_file_path: str,
    ) -> int:
        """
        Generate a high-quality PDF certificate for a recipient.
        Returns the generated file size in bytes.
        """
        out_path = Path(output_file_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        w, h = cls.PAGE_WIDTH, cls.PAGE_HEIGHT
        c = canvas.Canvas(str(out_path), pagesize=(w, h))
        c.setTitle(f"Certificate - {recipient_name}")
        c.setAuthor(issuer_name)
        c.setSubject(title)

        # 1. Borders & Crest
        cls._draw_ornate_borders(c)
        cls._draw_top_crest(c, w / 2, h - 75)

        # 2. Main Title Header
        c.setFillColor(cls.COLOR_PRIMARY)
        c.setFont("Helvetica-Bold", 26)
        c.drawCentredString(w / 2, h - 120, "CERTIFICATE OF ACHIEVEMENT")

        # 3. Presentation Subtitle
        c.setFillColor(cls.COLOR_MUTED_TEXT)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawCentredString(w / 2, h - 150, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

        # 4. Recipient Name (with dynamic font scaling to prevent overflow)
        name_clean = recipient_name.strip()
        font_size = 32
        if len(name_clean) > 35:
            font_size = 22
        elif len(name_clean) > 25:
            font_size = 26

        c.setFillColor(cls.COLOR_PRIMARY)
        c.setFont("Helvetica-Bold", font_size)
        c.drawCentredString(w / 2, h - 200, name_clean)

        # Decorative gold underline flourish
        cls._draw_gold_divider(c, w / 2, h - 215, width=max(260, min(len(name_clean) * 14, 460)))

        # 5. Purpose & Achievement Text
        c.setFillColor(cls.COLOR_MUTED_TEXT)
        c.setFont("Helvetica", 11)
        c.drawCentredString(w / 2, h - 250, "for successfully completing and demonstrating excellence in")

        # Course / Event Title
        c.setFillColor(cls.COLOR_PRIMARY)
        c.setFont("Helvetica-Bold", 17)
        c.drawCentredString(w / 2, h - 280, title.strip())

        # Description (wrapped)
        c.setFillColor(cls.COLOR_DARK_TEXT)
        c.setFont("Helvetica", 10.5)
        wrapped_desc = cls._wrap_text(description.strip(), max_chars_per_line=80)
        curr_y = h - 310
        for line in wrapped_desc[:3]:  # limit to 3 lines for visual balance
            c.drawCentredString(w / 2, curr_y, line)
            curr_y -= 16

        # 6. Bottom Signatures & Seal Section
        bottom_y = 100

        # Left Column: Date of Issue
        c.setStrokeColor(cls.COLOR_MUTED_TEXT)
        c.setLineWidth(1)
        c.line(100, bottom_y + 20, 240, bottom_y + 20)

        c.setFillColor(cls.COLOR_DARK_TEXT)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(170, bottom_y + 5, issue_date)

        c.setFillColor(cls.COLOR_MUTED_TEXT)
        c.setFont("Helvetica", 8)
        c.drawCentredString(170, bottom_y - 8, "DATE OF ISSUANCE")

        # Center Column: Verification Seal & Code
        cls._draw_verification_seal(c, w / 2, bottom_y + 15, certificate_code)

        # Right Column: Issuer Signature & Title
        c.setStrokeColor(cls.COLOR_MUTED_TEXT)
        c.setLineWidth(1)
        c.line(w - 240, bottom_y + 20, w - 100, bottom_y + 20)

        c.setFillColor(cls.COLOR_PRIMARY)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(w - 170, bottom_y + 5, issuer_name.strip())

        c.setFillColor(cls.COLOR_MUTED_TEXT)
        c.setFont("Helvetica", 8.5)
        signatory_title = (issuer_title or "Authorized Signatory").strip()
        c.drawCentredString(w - 170, bottom_y - 8, signatory_title)

        # Save and return size
        c.save()
        return out_path.stat().st_size
