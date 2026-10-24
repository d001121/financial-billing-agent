"""Render the project Markdown as an editorial Chinese PDF.

Optional document tooling only: reportlab and Pillow; no backend, OCR or model calls.
Run from any directory with a Python environment containing these dependencies.
"""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, KeepTogether, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
PAGE_W, PAGE_H = A4
MARGIN = 48
WIDTH = PAGE_W - MARGIN * 2
NAVY = colors.HexColor("#102C40")
INK = colors.HexColor("#223746")
TEAL = colors.HexColor("#187A7B")
MUTED = colors.HexColor("#647681")
PALE = colors.HexColor("#F1F5F6")
LINE = colors.HexColor("#D9E2E5")


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font color="#187A7B">\1</font>', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'\1', text)
    return text


def make_styles(dense: bool = False) -> dict[str, ParagraphStyle]:
    size, leading = (9.25, 14.4) if dense else (10.15, 16.5)
    base = dict(fontName="Harbor", fontSize=size, leading=leading,
                textColor=INK, wordWrap="CJK", alignment=TA_LEFT,
                splitLongWords=True, allowWidows=0, allowOrphans=0)
    result = {
        "body": ParagraphStyle("body", spaceAfter=8, **base),
        "bullet": ParagraphStyle("bullet", leftIndent=12, firstLineIndent=-10,
                                 spaceAfter=7, **base),
        "sub": ParagraphStyle("sub", fontName="HarborBold", fontSize=11.2,
                              leading=17, spaceBefore=10, spaceAfter=6,
                              textColor=TEAL, wordWrap="CJK", keepWithNext=True),
        "heading": ParagraphStyle("chapter", fontName="HarborBold", fontSize=20,
                                  leading=28, textColor=NAVY, spaceAfter=17,
                                  wordWrap="CJK", keepWithNext=True),
        "kicker": ParagraphStyle("kicker", fontName="HarborBold", fontSize=8,
                                 leading=12, textColor=TEAL, spaceAfter=7),
        "note": ParagraphStyle("note", fontName="Harbor", fontSize=8,
                               leading=12, textColor=MUTED, wordWrap="CJK",
                               spaceBefore=5, spaceAfter=7),
        "requirement": ParagraphStyle("requirement", fontName="Harbor", fontSize=9,
                                      leading=14.5, textColor=NAVY, wordWrap="CJK",
                                      backColor=PALE, borderPadding=9,
                                      spaceBefore=3, spaceAfter=14),
        "cell": ParagraphStyle("cell", fontName="Harbor", fontSize=8.7,
                               leading=13.5, textColor=INK, wordWrap="CJK"),
        "caption": ParagraphStyle("caption", fontName="Harbor", fontSize=7.8,
                                  leading=12, textColor=MUTED, spaceAfter=9,
                                  wordWrap="CJK"),
    }
    return result


class Rule(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 9

    def draw(self):
        self.canv.setStrokeColor(LINE)
        self.canv.setLineWidth(0.6)
        self.canv.line(0, 5, WIDTH, 5)


class Report(BaseDocTemplate):
    def __init__(self, target: Path, chapters: list[str]):
        super().__init__(str(target), pagesize=A4, leftMargin=MARGIN,
                         rightMargin=MARGIN, topMargin=75, bottomMargin=51,
                         title="航账 Harbor | 架构设计与笔试验收答辩",
                         author="Harbor 项目", subject="十项验收、上下文工程与财务智能体方案")
        self.chapters = chapters
        self.chapter_pages: list[dict] = []
        self.addPageTemplates(PageTemplate(
            "report", [Frame(MARGIN, 51, WIDTH, PAGE_H - 126,
                             leftPadding=0, rightPadding=0, topPadding=0,
                             bottomPadding=0)], onPage=self.decorate))

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "chapter":
            title = flowable.getPlainText()
            key = f"chapter-{len(self.chapter_pages) + 1}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=0)
            self.chapter_pages.append({"page": self.page, "title": title})

    def decorate(self, canvas, _doc):
        canvas.saveState()
        if self.page == 1:
            self.cover(canvas)
        else:
            canvas.setFillColor(TEAL)
            canvas.rect(MARGIN, PAGE_H - 42, 22, 3, fill=1, stroke=0)
            canvas.setFont("HarborBold", 8)
            canvas.setFillColor(NAVY)
            canvas.drawString(MARGIN + 31, PAGE_H - 43, "HARBOR / 航账")
            canvas.setFillColor(MUTED)
            canvas.setFont("Harbor", 7.6)
            canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 43,
                                   "架构设计与笔试验收答辩  /  2026.10")
            canvas.setStrokeColor(LINE)
            canvas.line(MARGIN, 37, PAGE_W - MARGIN, 37)
            canvas.setFont("Harbor", 7.3)
            canvas.drawString(MARGIN, 23, "项目方案  ·  以源码与注明范围的验证记录为依据")
            canvas.drawRightString(PAGE_W - MARGIN, 23, f"{self.page:02d}")
        canvas.restoreState()

    def cover(self, c):
        c.setFillColor(NAVY)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # Deterministic line art evokes shipping routes without stock imagery.
        for k in range(22):
            c.setStrokeColor(colors.Color(.14 + k * .003, .32 + k * .003,
                                           .39 + k * .003))
            c.setLineWidth(.45)
            p = c.beginPath()
            for n in range(101):
                x = n * PAGE_W / 100
                y = 405 + k * 6 + 23 * math.sin(x / 100 + k * .15)
                if n == 0:
                    p.moveTo(x, y)
                else:
                    p.lineTo(x, y)
            c.drawPath(p)
        c.setFillColor(colors.HexColor("#70D3C4"))
        c.rect(MARGIN, 758, 30, 4, fill=1, stroke=0)
        c.setFont("HarborBold", 11)
        c.drawString(MARGIN + 42, 753, "HARBOR / 航账")
        c.setFont("Harbor", 9)
        c.drawRightString(PAGE_W - MARGIN, 753, "TECHNICAL PROJECT REPORT")
        c.setFillColor(colors.white)
        c.setFont("HarborBold", 34)
        c.drawString(MARGIN, 669, "让每一笔账单")
        c.drawString(MARGIN, 620, "都有据可循。")
        c.setFont("Harbor", 15)
        c.drawString(MARGIN, 573, "架构设计与笔试验收答辩")
        c.setFillColor(colors.HexColor("#BDD0D8"))
        c.setFont("Harbor", 10)
        c.drawString(MARGIN, 544, "面向多格式航运单据的证据驱动财务智能体")
        c.drawString(MARGIN, 523, "Python  /  LangChain  /  LangGraph  /  Deep Agents  /  Vue")
        box_y, gap = 319, 8
        box_w = (WIDTH - gap * 2) / 3
        for i, (num, label, note) in enumerate([
            ("01", "证据驱动", "字段有引用，原件可回读"),
            ("02", "有界执行", "自主决策，共享预算与退出"),
            ("03", "版本化审核", "修订重算，审批绑定当前版本"),
        ]):
            x = MARGIN + i * (box_w + gap)
            c.setFillColor(colors.HexColor("#17394A"))
            c.roundRect(x, box_y, box_w, 91, 5, fill=1, stroke=0)
            c.setFont("Harbor", 8)
            c.setFillColor(colors.HexColor("#70D3C4"))
            c.drawString(x + 12, box_y + 67, num)
            c.setFont("HarborBold", 13)
            c.setFillColor(colors.white)
            c.drawString(x + 12, box_y + 43, label)
            c.setFont("Harbor", 8)
            c.setFillColor(colors.HexColor("#BDD0D8"))
            c.drawString(x + 12, box_y + 23, note)
        c.setFont("HarborBold", 9)
        c.setFillColor(colors.HexColor("#70D3C4"))
        c.drawString(MARGIN, 267, "READING MAP / 阅读导航")
        c.setFillColor(colors.white)
        c.setFont("Harbor", 10)
        for y, label, page in [
            (238, "项目概要、技术取舍与上下文工程", "02-04"),
            (212, "十项验收：问题、方案、理由与增强路径", "05-14"),
            (186, "标准输出、验证证据与评审演示", "15-17"),
        ]:
            c.drawString(MARGIN, y, label)
            c.drawRightString(PAGE_W - MARGIN, y, page)
        c.setStrokeColor(colors.HexColor("#3B5664"))
        c.line(MARGIN, 130, PAGE_W - MARGIN, 130)
        c.setFont("Harbor", 8)
        c.setFillColor(colors.HexColor("#BDD0D8"))
        c.drawString(MARGIN, 105, "2026.10.24  /  技术评审阅读版")
        c.drawString(MARGIN, 87, "源码实现、历史测量与后续方案分别说明；合成示例明确标记。")
        c.drawRightString(PAGE_W - MARGIN, 47, "01")


def parse_section(section: str, source: Path, index: int) -> list:
    styles = make_styles(dense=index in (12, 16))
    lines = section.strip().splitlines()
    flows = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("<a "):
            i += 1
            continue
        if line.startswith("## "):
            title = line[3:]
            if title.startswith("验收 "):
                label, title = title.split(" | ", 1)
                kicker = f"ACCEPTANCE / {label}"
            else:
                num, title = title.split(" ", 1)
                kicker = f"SOLUTION / CHAPTER {num}"
            flows.append(Paragraph(inline(kicker), styles["kicker"]))
            heading = Paragraph(inline(title), styles["heading"])
            flows.append(heading)
        elif line.startswith("### "):
            flows.append(Paragraph(inline(line[4:]), styles["sub"]))
        elif line.startswith("!["):
            match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            if not match:
                raise ValueError(f"Invalid image: {line}")
            caption, filename = match.groups()
            image = Image(str(source.parent / filename))
            scale = min(WIDTH / image.imageWidth, 224 / image.imageHeight)
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            image.hAlign = "LEFT"
            flows.append(KeepTogether([
                Spacer(1, 6), image, Spacer(1, 5),
                Paragraph(inline(caption), styles["caption"]),
            ]))
        elif line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            code_style = ParagraphStyle(
                "json", fontName="Harbor", fontSize=8.5, leading=10.8,
                textColor=INK, wordWrap="CJK")
            content = "<br/>".join(
                html.escape(row).replace(" ", "&#160;") or "&#160;" for row in code)
            block = Table([[Paragraph(content, code_style)]], colWidths=[WIDTH])
            block.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), .5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            flows.extend([block, Spacer(1, 9)])
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [v.strip() for v in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", v) for v in cells):
                    rows.append([Paragraph(inline(v), styles["cell"]) for v in cells])
                i += 1
            i -= 1
            widths = [WIDTH * .19, WIDTH * .45, WIDTH * .36]
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DBE9EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("LINEBELOW", (0, 0), (-1, 0), .7, TEAL),
                ("LINEBELOW", (0, 1), (-1, -1), .35, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]))
            flows.extend([table, Spacer(1, 9)])
        else:
            text = line
            if line.startswith("题目要求："):
                style = styles["requirement"]
            elif line.startswith(("实现", "依据：", "证据路径：", "代码位置：")):
                flows.append(Rule())
                style = styles["note"]
            elif line.startswith("- "):
                text, style = "• " + line[2:], styles["bullet"]
            elif re.match(r"^\d+\. ", line):
                style = styles["bullet"]
            else:
                style = styles["body"]
            flows.append(Paragraph(inline(text), style))
        i += 1
    return flows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/project-solution.md")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/pdf/Harbor_项目方案与笔试答辩.pdf")
    parser.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = parser.parse_args()
    pdfmetrics.registerFont(TTFont("Harbor", str(args.font_dir / "Deng.ttf")))
    pdfmetrics.registerFont(TTFont("HarborBold", str(args.font_dir / "Dengb.ttf")))
    pdfmetrics.registerFontFamily("Harbor", normal="Harbor", bold="HarborBold",
                                italic="Harbor", boldItalic="HarborBold")
    sections = args.source.read_text(encoding="utf-8-sig").split("<!-- pagebreak -->")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc = Report(args.output, sections)
    story = [Spacer(1, 680), PageBreak()]
    for index, section in enumerate(sections[1:], start=1):
        if index > 1:
            story.append(PageBreak())
        story.extend(parse_section(section, args.source, index))
    doc.build(story)
    print(f"PDF: {args.output}")
    print(f"Pages: {doc.page}")
    for entry in doc.chapter_pages:
        print(f"  {entry['page']:02}: {entry['title']}")
    if doc.page != len(sections):
        raise SystemExit("Layout overflow: inspect page breaks before delivery.")


if __name__ == "__main__":
    main()
