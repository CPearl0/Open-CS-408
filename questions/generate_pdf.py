#!/usr/bin/env python3
"""
Open-CS-408 习题册PDF生成工具
- 科目标题：20pt 居中
- 章节标题：16pt 左对齐
- 题目与答案使用相同全局编号
- 使用 NotoSansSC-Regular.ttf
- 输出文件：Open-CS-408习题册.pdf
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from itertools import groupby

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as PlatypusImage
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# === 配置 ===
DB_PATH = "questions.db"
OUTPUT_PDF = "Open-CS-408习题册.pdf"
FONT_PATH = "fonts/NotoSansSC-Regular.ttf"

# 科目与章节
SUBJECTS = {
    "DS": {"name": "数据结构", "chapters": {"01": "基本概念", "02": "线性表", "03": "栈、队列和数组", "04": "树与二叉树", "05": "图", "06": "查找", "07": "排序"}},
    "CO": {"name": "计算机组成原理", "chapters": {"01": "计算机系统概述", "02": "数据的表示和运算", "03": "存储器层次结构", "04": "指令系统", "05": "中央处理器", "06": "总线和输入输出系统"}},
    "OS": {"name": "操作系统", "chapters": {"01": "操作系统概述", "02": "进程管理", "03": "内存管理", "04": "文件管理", "05": "输入输出管理"}},
    "CN": {"name": "计算机网络", "chapters": {"01": "计算机网络体系结构", "02": "物理层", "03": "数据链路层", "04": "网络层", "05": "传输层", "06": "应用层"}},
}
QUESTION_TYPES = {"single_choice": "单选题", "application": "应用题"}

SUBJECT_ORDER = list(SUBJECTS.keys())  # ['DS', 'CO', 'OS', 'CN']

CHAPTER_ORDER_MAP = {
    subject_code: {ch_num: idx for idx,
                   ch_num in enumerate(info["chapters"].keys())}
    for subject_code, info in SUBJECTS.items()
}

# === 注册中文字体 ===


def register_chinese_font():
    font_path = Path(FONT_PATH)
    if not font_path.exists():
        raise FileNotFoundError(f"字体文件未找到: {font_path.resolve()}")
    pdfmetrics.registerFont(TTFont('NotoSansSC', str(font_path)))
    return 'NotoSansSC'


CHINESE_FONT = register_chinese_font()

# === 工具函数 ===


def safe_image(image_path, max_width=5*inch):
    if not image_path or not Path(image_path).exists():
        return None
    try:
        img = PlatypusImage(image_path, width=max_width)
        img.hAlign = 'CENTER'
        return img
    except Exception:
        return None

# === 1. 读取已发布题目 ===


def fetch_published_questions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM questions
        WHERE status = 'published'
        ORDER BY id  -- 仅保证确定性，主排序在Python中做
    """)
    questions = [dict(row) for row in cur.fetchall()]
    conn.close()

    # 按照 SUBJECTS 中定义的顺序排序
    def sort_key(q):
        sub = q["subject_code"]
        chap = q["chapter_num"]
        sub_idx = SUBJECT_ORDER.index(sub) if sub in SUBJECT_ORDER else 999
        chap_idx = CHAPTER_ORDER_MAP[sub].get(
            chap, 999) if sub in CHAPTER_ORDER_MAP else 999
        return (sub_idx, chap_idx, q["id"])

    questions.sort(key=sort_key)
    return questions

# === 2. 生成PDF内容 ===


def generate_content_pdf(questions, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=72,
                            rightMargin=72, topMargin=72, bottomMargin=72)

    # 样式定义
    normal_style = ParagraphStyle(
        'Normal', fontName=CHINESE_FONT, fontSize=11, leading=14, spaceAfter=6)

    subject_title_style = ParagraphStyle(
        'SubjectTitle',
        fontName=CHINESE_FONT,
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        spaceBefore=18,
        spaceAfter=12
    )

    chapter_title_style = ParagraphStyle(
        'ChapterTitle',
        fontName=CHINESE_FONT,
        fontSize=16,
        leading=18,
        spaceBefore=12,
        spaceAfter=8
    )

    cover_title_style = ParagraphStyle(
        'CoverTitle',
        fontName=CHINESE_FONT,
        fontSize=28,
        alignment=TA_CENTER,
        spaceAfter=30
    )

    story = []

    # 封面
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("Open-CS-408", cover_title_style))
    story.append(Paragraph("习题册", cover_title_style))
    story.append(Spacer(1, 0.5 * inch))
    story.append(
        Paragraph(f"生成时间：{datetime.now().strftime('%Y年%m月%d日')}", normal_style))
    story.append(PageBreak())

    # 第一部分：习题
    story.append(Paragraph("习题", chapter_title_style))
    story.append(Spacer(1, 12))

    question_index = 1

    # 按科目分组
    for subject_code, subject_group_iter in groupby(questions, key=lambda x: x["subject_code"]):
        subject_group = list(subject_group_iter)  # 转为列表以便遍历
        subject_name = SUBJECTS[subject_code]["name"]
        story.append(Paragraph(subject_name, subject_title_style))

        # 按章节分组
        for chapter_num, chapter_group in groupby(subject_group, key=lambda x: x["chapter_num"]):
            chapter_name = SUBJECTS[subject_code]["chapters"][chapter_num]
            story.append(Paragraph(chapter_name, chapter_title_style))

            for q in chapter_group:
                story.append(Paragraph(
                    f"{question_index}. {q['question_text'].replace('\n', '<br/>')}", normal_style))

                if q["question_type"] == "single_choice":
                    for opt in "ABCD":
                        val = q.get(f"option_{opt.lower()}")
                        if val:
                            story.append(
                                Paragraph(f"{opt}. {val}", normal_style))

                img = safe_image(q.get("image_path"))
                if img:
                    story.append(Spacer(1, 6))
                    story.append(img)

                story.append(Spacer(1, 12))
                question_index += 1

        # 每个科目结束后换页（但最后一个科目不需要额外换页）
        # 为了简单，我们统一加 PageBreak，即使最后一页空也无妨
        story.append(PageBreak())

    # 第二部分：答案与解析
    story.append(Paragraph("答案解析", chapter_title_style))
    story.append(Spacer(1, 12))

    for i, q in enumerate(questions, 1):
        story.append(
            Paragraph(f"{i}. 参考答案：{q['correct_answer']}", normal_style))

        if q["explanation"]:
            story.append(Paragraph("解析：", normal_style))
            story.append(Paragraph(q["explanation"].replace(
                "\n", "<br/>"), normal_style))

        if q.get("image_path"):
            img = safe_image(q["image_path"])
            if img:
                story.append(Spacer(1, 6))
                story.append(img)

        story.append(Spacer(1, 12))

    doc.build(story)
    print(f"✅ 内容PDF已生成：{output_path}")

# === 3. 添加书签（大纲）===


def add_bookmarks(pdf_path, questions):
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    part1 = writer.add_outline_item("习题", page_number=1)
    current_page = 1

    for subject_code, subject_group in groupby(questions, key=lambda x: x["subject_code"]):
        subject_name = SUBJECTS[subject_code]["name"]
        subj_bm = writer.add_outline_item(
            subject_name, page_number=current_page, parent=part1)

        for chapter_num, _ in groupby(subject_group, key=lambda x: x["chapter_num"]):
            chapter_name = SUBJECTS[subject_code]["chapters"][chapter_num]
            writer.add_outline_item(
                chapter_name, page_number=current_page, parent=subj_bm)
            current_page += 1

    answer_page = len(reader.pages) - 1
    writer.add_outline_item("答案解析", page_number=answer_page)

    final_path = OUTPUT_PDF
    with open(final_path, "wb") as f:
        writer.write(f)
    print(f"✅ 带书签PDF已生成：{final_path}")
    return final_path

# === 主函数 ===


def main():
    font_file = Path(FONT_PATH)
    if not font_file.exists():
        print(f"❌ 字体文件不存在，请将 NotoSansSC-Regular.ttf 放入 {font_file.parent} 目录")
        return

    questions = fetch_published_questions()
    if not questions:
        print("⚠️ 无已发布题目")
        return

    print(f"📚 共 {len(questions)} 道题，正在生成PDF...")
    temp_pdf = "temp_workbook.pdf"
    generate_content_pdf(questions, temp_pdf)
    final_pdf = add_bookmarks(temp_pdf, questions)
    Path(temp_pdf).unlink(missing_ok=True)
    print(f"\n🎉 完成！最终文件：{final_pdf}")


if __name__ == "__main__":
    main()
