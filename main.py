import sqlite3
import os
import signal
import io
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import arabic_reshaper
import matplotlib
import pandas
import asyncio
import httpcore._async
import asyncio

asyncio.set_event_loop(asyncio.new_event_loop())

# تأكد من استخدام asyncio event loop
asyncio.set_event_loop(asyncio.new_event_loop())

from bidi.algorithm import get_display
import reportlab

print("كل المكتبات جاهزة ✅")

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import arabic_reshaper
from bidi.algorithm import get_display
from datetime import datetime
from io import BytesIO
import re
import os
import tempfile
import logging

# ========= إعداد التسجيل =========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# ========= إعداد التوكن =========
TOKEN = "7568800963:AAEq7EBzt1M8gKazhm6pclwIkFuNmIIVg9o"  # ضع توكنك هنا إن أردت تغييره

# ========= إعداد قاعدة البيانات الدائمة =========
import os

# الحصول على اسم المشروع تلقائياً
try:
    PROJECT_NAME = os.path.basename(os.getcwd())
except:
    PROJECT_NAME = "medical-bot"

DB_PATH = f"/home/runner/{PROJECT_NAME}/operations.db"

# تأكد من وجود المجلد
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# أنشئ الجدول إذا لم يكن موجوداً
cursor.execute("""
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    patient TEXT,
    hospital TEXT,
    department TEXT,
    doctor TEXT,
    procedure TEXT,
    amount REAL,
    discount REAL,
    commission REAL
)
""")
conn.commit()

print(f"✅ قاعدة البيانات محفوظة في: {DB_PATH}")
print(f"✅ البيانات لن تحذف عند إعادة التشغيل")

# ========= الحالات =========
DATE, PATIENT, HOSPITAL, DEPARTMENT, DOCTOR, PROCEDURE, AMOUNT, DISCOUNT, COMMISSION = range(
    9)


# ========= دوال Arabic =========
def arabic_text(text):
    if text is None:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)


# دالة عامة لتنسيق النصوص RTL للبوت (رسائل التليجرام)
def rtl(text: str) -> str:
    # Right-to-Left Embedding ... End embedding
    return "\u202B" + str(text) + "\u202C"


# ========= إعداد الرسوم البيانية العربية =========
def setup_arabic_plot():
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 12


# ========= إعداد خط PDF للعربية =========
def setup_pdf_fonts():
    try:
        font_paths = [
            '/usr/share/fonts/truetype/arabic/arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'c:/windows/fonts/arial.ttf',
            'c:/windows/fonts/tahoma.ttf',
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Arabic', font_path))
                print(f"✅ تم تحميل الخط: {font_path}")
                return

        print("⚠️ استخدام الخط الافتراضي (قد لا يدعم العربية)")

    except Exception as e:
        print(f"❌ خطأ في تحميل الخط: {e}")


# ========= دوال الجداول =========
def create_pivot_table(departments_data, hospitals_data):
    hospitals_list = sorted(hospitals_data.keys())
    departments_list = sorted(departments_data.keys())

    if not hospitals_list or not departments_list:
        return "⚠️ لا توجد بيانات كافية لإنشاء الجدول المفصل"

    max_dept_len = max(len(arabic_text(dept)) for dept in departments_list)
    max_hosp_len = max(len(arabic_text(hosp)) for hosp in hospitals_list)

    pivot_text = "📋 **الجدول المفصل (الأقسام × المستشفيات)**\n\n"

    header = f"{'القسم':<{max_dept_len}} | "
    for hosp in hospitals_list:
        header += f"{arabic_text(hosp):<{max_hosp_len}} | "
    pivot_text += header + "\n"

    separator = "-" * (max_dept_len + 2)
    for _ in hospitals_list:
        separator += "-" * (max_hosp_len + 3)
    pivot_text += separator + "\n"

    for dept in departments_list:
        row = f"{arabic_text(dept):<{max_dept_len}} | "
        for hosp in hospitals_list:
            count = departments_data[dept].get(hosp, 0)
            row += f"{count:<{max_hosp_len}} | "
        pivot_text += row + "\n"

    return pivot_text


def create_summary_table(hospitals_data):
    if not hospitals_data:
        return "⚠️ لا توجد بيانات لإنشاء جدول الإجمالي"

    sorted_hospitals = sorted(hospitals_data.items(),
                              key=lambda x: x[1],
                              reverse=True)

    max_hosp_len = max(len(arabic_text(hosp)) for hosp, _ in sorted_hospitals)
    max_count_len = max(len(str(count)) for _, count in sorted_hospitals)

    summary_text = "📊 **جدول الإجمالي (عدد العمليات لكل مستشفى)**\n\n"

    summary_text += f"{'المستشفى':<{max_hosp_len}} | {'عدد العمليات':<{max_count_len}}\n"
    summary_text += "-" * (max_hosp_len + max_count_len + 5) + "\n"

    total = 0
    for hosp, count in sorted_hospitals:
        summary_text += f"{arabic_text(hosp):<{max_hosp_len}} | {count:<{max_count_len}}\n"
        total += count

    summary_text += "-" * (max_hosp_len + max_count_len + 5) + "\n"
    summary_text += f"{'الإجمالي':<{max_hosp_len}} | {total:<{max_count_len}}\n"

    return summary_text


# ========= دالة إنشاء تقرير PDF للمقارنة =========
async def generate_comparison_pdf(update: Update, hospitals_data,
                                  departments_data, hospital_filter,
                                  month_filter):
    setup_pdf_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=landscape(A4),
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=50,
                            bottomMargin=20)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='ArabicTitle',
                                 fontName='Arabic',
                                 fontSize=16,
                                 alignment=1,
                                 spaceAfter=30)

    subtitle_style = ParagraphStyle(name='ArabicSubtitle',
                                    fontName='Arabic',
                                    fontSize=12,
                                    alignment=1,
                                    spaceAfter=20)

    table_style = ParagraphStyle(name='ArabicTable',
                                 fontName='Arabic',
                                 fontSize=10,
                                 alignment=2,
                                 wordWrap='CJK')

    elements = []

    title = "تقرير مقارنة المستشفيات"
    if hospital_filter:
        title += f" - {hospital_filter}"
    if month_filter:
        title += f" - شهر {month_filter}"

    elements.append(Paragraph(arabic_text(title), title_style))

    elements.append(
        Paragraph(arabic_text("جدول الإجمالي (عدد العمليات لكل مستشفى)"),
                  subtitle_style))

    sorted_hospitals = sorted(hospitals_data.items(),
                              key=lambda x: x[1],
                              reverse=True)
    summary_data = [[arabic_text("المستشفى"), arabic_text("عدد العمليات")]]

    total = 0
    for hosp, count in sorted_hospitals:
        summary_data.append([arabic_text(hosp), str(count)])
        total += count

    summary_data.append([arabic_text("الإجمالي"), str(total)])

    summary_table = Table(summary_data, colWidths=[300, 100])
    summary_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(arabic_text("الجدول المفصل (الأقسام × المستشفيات)"),
                  subtitle_style))

    hospitals_list = sorted(hospitals_data.keys())
    departments_list = sorted(departments_data.keys())

    pivot_data = []

    header_row = [arabic_text("القسم/المستشفى")]
    for hosp in hospitals_list:
        header_row.append(arabic_text(hosp))
    pivot_data.append(header_row)

    for dept in departments_list:
        row = [arabic_text(dept)]
        for hosp in hospitals_list:
            count = departments_data[dept].get(hosp, 0)
            row.append(str(count))
        pivot_data.append(row)

    col_widths = [150] + [60] * len(hospitals_list)
    pivot_table = Table(pivot_data, colWidths=col_widths)

    pivot_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])

    for i in range(1, len(pivot_data)):
        if i % 2 == 0:
            pivot_style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)

    pivot_table.setStyle(pivot_style)
    elements.append(pivot_table)

    setup_arabic_plot()
    fig, ax = plt.subplots(figsize=(10, 6))

    hospitals = [arabic_text(h) for h in hospitals_data.keys()]
    counts = list(hospitals_data.values())

    bars = ax.barh(range(len(hospitals)), counts, color='skyblue')

    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(bar.get_width() + 0.1,
                bar.get_y() + bar.get_height() / 2,
                str(count),
                ha='left',
                va='center',
                fontsize=10)

    ax.set_yticks(range(len(hospitals)))
    ax.set_yticklabels(hospitals)
    ax.set_xlabel(arabic_text('عدد العمليات'))

    title = 'مقارنة عدد العمليات بين المستشفيات'
    if hospital_filter:
        title += f' - {hospital_filter}'
    if month_filter:
        title += f' - شهر {month_filter}'

    ax.set_title(arabic_text(title))
    plt.tight_layout()

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        plt.savefig(tmp.name, format='png', dpi=100, bbox_inches='tight')
        chart_path = tmp.name
    plt.close()

    elements.append(Spacer(1, 20))
    elements.append(
        Paragraph(arabic_text("الرسم البياني للمقارنة"), subtitle_style))
    elements.append(Image(chart_path, width=400, height=300))

    doc.build(elements)
    buffer.seek(0)

    os.unlink(chart_path)

    return buffer


# ========= دوال الرسوم البيانية المعدلة =========
async def generate_hospital_comparison(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    hospital_filter = None
    month_filter = None

    if args:
        numbers = []
        texts = []

        for arg in args:
            if arg.isdigit() and len(arg) <= 2:
                numbers.append(int(arg))
            else:
                texts.append(arg)

        if numbers:
            month_filter = numbers[0]

        if texts:
            hospital_filter = " ".join(texts)

    query = """
        SELECT hospital, department, COUNT(*) as operations_count 
        FROM operations 
        WHERE 1=1
    """
    params = []

    if hospital_filter:
        query += " AND hospital LIKE ?"
        params.append(f"%{hospital_filter}%")

    if month_filter:
        query += " AND strftime('%m', date) = ?"
        params.append(f"{month_filter:02d}")

    query += " GROUP BY hospital, department ORDER BY hospital, operations_count DESC"

    cursor.execute(query, params)
    data = cursor.fetchall()

    if not data:
        await update.message.reply_text(
            rtl("⚠️ لا توجد بيانات للمقارنة بناءً على الفلاتر المحددة"))
        return

    hospitals_data = {}
    departments_data = {}

    for row in data:
        hospital_name = row[0]
        department_name = row[1]
        count = row[2]

        if hospital_name not in hospitals_data:
            hospitals_data[hospital_name] = 0
        hospitals_data[hospital_name] += count

        if department_name not in departments_data:
            departments_data[department_name] = {}
        if hospital_name not in departments_data[department_name]:
            departments_data[department_name][hospital_name] = 0
        departments_data[department_name][hospital_name] = count

    pdf_buffer = await generate_comparison_pdf(update, hospitals_data,
                                               departments_data,
                                               hospital_filter, month_filter)

    await update.message.reply_document(
        document=InputFile(pdf_buffer, filename="مقارنة_المستشفيات.pdf"),
        caption=arabic_text("📊 تقرير مقارنة المستشفيات"))

    message = "✅ تم إنشاء تقرير PDF للمقارنة"
    if hospital_filter:
        message += f" للمستشفى: {hospital_filter}"
    if month_filter:
        message += f" لشهر: {month_filter}"
    await update.message.reply_text(rtl(message))


# ========= دوال البوت الأساسية =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(rtl("أدخل تاريخ العملية (YYYY-MM-DD):"))
    return DATE


async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text(rtl("اسم المريض:"))
    return PATIENT


async def patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patient"] = update.message.text
    await update.message.reply_text(rtl("اسم المستشفى:"))
    return HOSPITAL


async def hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["hospital"] = update.message.text
    await update.message.reply_text(rtl("القسم:"))
    return DEPARTMENT


async def department(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["department"] = update.message.text
    await update.message.reply_text(rtl("اسم الطبيب:"))
    return DOCTOR


async def doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["doctor"] = update.message.text
    await update.message.reply_text(rtl("نوع الإجراء:"))
    return PROCEDURE


async def procedure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["procedure"] = update.message.text
    await update.message.reply_text(rtl("المبلغ:"))
    return AMOUNT


async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["amount"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text(rtl("⚠️ أدخل رقم صحيح للمبلغ:"))
        return AMOUNT
    await update.message.reply_text(rtl("التخفيض (0 إذا لا يوجد):"))
    return DISCOUNT


async def discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["discount"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text(rtl("⚠️ أدخل رقم صحيح للتخفيض:"))
        return DISCOUNT
    await update.message.reply_text(rtl("العمولة (0 إذا لا يوجد):"))
    return COMMISSION


async def commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["commission"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text(rtl("⚠️ أدخل رقم صحيح للعمولة:"))
        return COMMISSION

    cursor.execute(
        """
        INSERT INTO operations (date, patient, hospital, department, doctor, procedure, amount, discount, commission)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (context.user_data["date"], context.user_data["patient"],
          context.user_data["hospital"], context.user_data["department"],
          context.user_data["doctor"], context.user_data["procedure"],
          context.user_data["amount"], context.user_data["discount"],
          context.user_data["commission"]))
    conn.commit()
    await update.message.reply_text(rtl("✅ تم حفظ العملية بنجاح"))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(rtl("❌ تم إلغاء العملية"))
    return ConversationHandler.END


async def report_rtl_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    month = None
    hospital_filter = None

    if args:
        numbers = []
        texts = []

        for arg in args:
            if arg.isdigit() and len(arg) <= 2:
                numbers.append(int(arg))
            else:
                texts.append(arg)

        if numbers:
            month = numbers[0]

        if texts:
            hospital_filter = " ".join(texts)

    cursor.execute("SELECT * FROM operations ORDER BY date")
    data = cursor.fetchall()
    filtered = []
    for row in data:
        try:
            row_month = int(row[1].split("-")[1])
        except:
            row_month = None
        row_hospital = row[3] or ""
        if month and row_month != month:
            continue
        if hospital_filter and hospital_filter.lower(
        ) not in row_hospital.lower():
            continue
        filtered.append(row)

    if not filtered:
        await update.message.reply_text(rtl("⚠️ لا توجد بيانات لهذا التقرير"))
        return

    total_amount = sum(row[7] or 0 for row in filtered)
    total_discount = sum(row[8] or 0 for row in filtered)
    total_commission = sum(row[9] or 0 for row in filtered)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=A4,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=80,
                            bottomMargin=20)

    setup_pdf_fonts()

    elements = []

    style_title = ParagraphStyle(name='title',
                                 fontName='Arabic',
                                 fontSize=18,
                                 alignment=1,
                                 spaceAfter=10)
    style_subtitle = ParagraphStyle(name='subtitle',
                                    fontName='Arabic',
                                    fontSize=12,
                                    alignment=1,
                                    spaceAfter=5)
    style_table = ParagraphStyle(name='table',
                                 fontName='Arabic',
                                 fontSize=10,
                                 alignment=1,
                                 wordWrap='CJK',
                                 leading=12)

    elements.append(
        Paragraph(arabic_text("تقرير العمليات الطبية"), style_title))

    subtitle = ""
    if hospital_filter:
        subtitle += f"المستشفى: {hospital_filter} "
    if month:
        subtitle += f"- الشهر: {month}"
    if not subtitle:
        subtitle = "كل المستشفيات - كل الشهور"

    elements.append(Paragraph(arabic_text(subtitle), style_subtitle))
    elements.append(Spacer(1, 20))

    headers = [
        "م", "التاريخ", "المريض", "المستشفى", "القسم", "الطبيب", "الإجراء",
        "المبلغ", "التخفيض", "العمولة"
    ]
    headers_rtl = list(reversed(headers))
    table_data = [[
        Paragraph(arabic_text(h), style_table) for h in headers_rtl
    ]]

    for idx, row in enumerate(filtered, start=1):
        row_values = [
            Paragraph(arabic_text(str(row[9] or 0)), style_table),
            Paragraph(arabic_text(str(row[8] or 0)), style_table),
            Paragraph(arabic_text(str(row[7] or 0)), style_table),
            Paragraph(arabic_text(row[6] or ""), style_table),
            Paragraph(arabic_text(row[5] or ""), style_table),
            Paragraph(arabic_text(row[4] or ""), style_table),
            Paragraph(arabic_text(row[3] or ""), style_table),
            Paragraph(arabic_text(row[2] or ""), style_table),
            Paragraph(arabic_text(row[1] or ""), style_table),
            Paragraph(arabic_text(str(idx)), style_table)
        ]
        table_data.append(row_values)

    totals_row = [
        Paragraph(arabic_text(str(total_commission)), style_table),
        Paragraph(arabic_text(str(total_discount)), style_table),
        Paragraph(arabic_text(str(total_amount)), style_table),
        Paragraph(arabic_text(""), style_table),
        Paragraph(arabic_text(""), style_table),
        Paragraph(arabic_text(""), style_table),
        Paragraph(arabic_text(""), style_table),
        Paragraph(arabic_text(""), style_table),
        Paragraph(arabic_text(""), style_table),
        Paragraph(arabic_text("المجموع"), style_table)
    ]
    table_data.append(totals_row)

    table = Table(table_data, repeatRows=1, hAlign='RIGHT')

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arabic'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
    ])

    for i in range(1, len(table_data) - 1):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)
        else:
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)

    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    await update.message.reply_document(
        document=InputFile(buffer, filename="report_rtl_final.pdf"))

    message = "📄 تم إنشاء التقرير"
    if hospital_filter:
        message += f" للمستشفى: {hospital_filter}"
    if month:
        message += f" لشهر: {month}"
    await update.message.reply_text(rtl(message))


# ========= الدوال الناقصة =========
async def generate_monthly_stats(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute("""
            SELECT strftime('%m', date) as month, COUNT(*) as count, 
                   SUM(amount) as total_amount, SUM(commission) as total_commission
            FROM operations 
            GROUP BY month 
            ORDER BY month
        """)
        data = cursor.fetchall()

        if not data:
            await update.message.reply_text(
                rtl("⚠️ لا توجد بيانات للإحصائيات الشهرية"))
            return

        setup_arabic_plot()
        months = [f"شهر {row[0]}" for row in data]
        counts = [row[1] for row in data]
        amounts = [row[2] for row in data]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

        ax1.bar(months, counts, color='skyblue')
        ax1.set_title(arabic_text('عدد العمليات لكل شهر'))
        ax1.set_ylabel(arabic_text('عدد العمليات'))

        ax2.bar(months, amounts, color='lightgreen')
        ax2.set_title(arabic_text('إجمالي المبالغ لكل شهر'))
        ax2.set_ylabel(arabic_text('المبلغ'))

        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()

        await update.message.reply_photo(
            photo=InputFile(buf, filename='monthly_stats.png'),
            caption=arabic_text('📊 الإحصائيات الشهرية للعمليات'))

    except Exception as e:
        logger.error(f"Error in generate_monthly_stats: {e}")
        await update.message.reply_text(
            rtl("❌ حدث خطأ أثناء إنشاء الإحصائيات الشهرية"))


async def generate_department_distribution(update: Update,
                                           context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute("""
            SELECT department, COUNT(*) as count 
            FROM operations 
            WHERE department IS NOT NULL AND department != ''
            GROUP BY department 
            ORDER BY count DESC
        """)
        data = cursor.fetchall()

        if not data:
            await update.message.reply_text(
                rtl("⚠️ لا توجد بيانات لتوزيع الأقسام"))
            return

        setup_arabic_plot()
        departments = [arabic_text(row[0]) for row in data]
        counts = [row[1] for row in data]

        plt.figure(figsize=(10, 8))
        plt.pie(counts, labels=departments, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title(arabic_text('توزيع العمليات حسب الأقسام'))

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()

        await update.message.reply_photo(
            photo=InputFile(buf, filename='department_dist.png'),
            caption=arabic_text('📊 توزيع العمليات حسب الأقسام'))

    except Exception as e:
        logger.error(f"Error in generate_department_distribution: {e}")
        await update.message.reply_text(
            rtl("❌ حدث خطأ أثناء إنشاء توزيع الأقسام"))


async def generate_doctor_performance(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute("""
            SELECT doctor, COUNT(*) as operations_count, 
                   SUM(amount) as total_amount, AVG(amount) as avg_amount
            FROM operations 
            WHERE doctor IS NOT NULL AND doctor != ''
            GROUP BY doctor 
            ORDER BY operations_count DESC
            LIMIT 10
        """)
        data = cursor.fetchall()

        if not data:
            await update.message.reply_text(
                rtl("⚠️ لا توجد بيانات لأداء الأطباء"))
            return

        performance_text = "🏥 **أداء الأطباء (أعلى 10)**\n\n"
        performance_text += "| الطبيب | عدد العمليات | إجمالي المبالغ | متوسط المبلغ |\n"
        performance_text += "|--------|-------------|---------------|-------------|\n"

        for row in data:
            doctor_name = arabic_text(row[0] if row[0] else "غير معروف")
            performance_text += f"| {doctor_name} | {row[1]} | {row[2]:.2f} | {row[3]:.2f} |\n"

        await update.message.reply_text(rtl(performance_text),
                                        parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in generate_doctor_performance: {e}")
        await update.message.reply_text(
            rtl("❌ حدث خطأ أثناء إنشاء تقرير أداء الأطباء"))


async def generate_department_comparison(update: Update,
                                         context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor.execute("""
            SELECT department, COUNT(*) as operations_count, 
                   SUM(amount) as total_amount, AVG(amount) as avg_amount
            FROM operations 
            WHERE department IS NOT NULL AND department != ''
            GROUP BY department 
            ORDER BY total_amount DESC
        """)
        data = cursor.fetchall()

        if not data:
            await update.message.reply_text(
                rtl("⚠️ لا توجد بيانات للمقارنة بين الأقسام"))
            return

        setup_arabic_plot()
        departments = [arabic_text(row[0]) for row in data]
        amounts = [row[2] for row in data]

        plt.figure(figsize=(12, 6))
        bars = plt.bar(range(len(departments)), amounts, color='orange')
        plt.xlabel(arabic_text('الأقسام'))
        plt.ylabel(arabic_text('إجمالي المبالغ'))
        plt.title(arabic_text('مقارنة الأقسام حسب إجمالي المبالغ'))
        plt.xticks(range(len(departments)),
                   departments,
                   rotation=45,
                   ha='right')

        for bar, amount in zip(bars, amounts):
            plt.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + max(amounts) * 0.01,
                     f'{amount:.0f}',
                     ha='center',
                     va='bottom')

        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()

        await update.message.reply_photo(
            photo=InputFile(buf, filename='department_comparison.png'),
            caption=arabic_text('📊 مقارنة الأقسام حسب إجمالي المبالغ'))

    except Exception as e:
        logger.error(f"Error in generate_department_comparison: {e}")
        await update.message.reply_text(
            rtl("❌ حدث خطأ أثناء إنشاء مقارنة الأقسام"))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🏥 **أوامر نظام إدارة العمليات الطبية** 🏥

📝 **إضافة البيانات**:
/add - بدء إضافة عملية جديدة

📊 **التقارير والإحصائيات**:
/report [شهر] [مستشفى] - إنشاء تقرير مفصل (PDF)
/compare [شهر] [مستشفى] - مقارنة بين المستشفيات (PDF)
/monthly_stats - الإحصائيات الشهرية
/department_dist - توزيع العمليات حسب الأقسام
/doctor_perf - أداء الأطباء
/compare_departments - مقارنة بين الأقسام

⚙️ **أوامر أخرى**:
/help - عرض هذه الرسالة
/cancel - إلغاء العملية الحالية

📌 **ملاحظات**:
- يمكنك استخدام الأرقام للأشهر (1-12)
- يمكنك كتابة اسم المستشفى للتصفية
- مثال: `/report 5 مستشفى الملك فيصل`
"""
    await update.message.reply_text(rtl(help_text), parse_mode='Markdown')


# ========= تشغيل البوت =========
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date)],
            PATIENT:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, patient)],
            HOSPITAL:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, hospital)],
            DEPARTMENT:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, department)],
            DOCTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, doctor)],
            PROCEDURE:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, procedure)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount)],
            DISCOUNT:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, discount)],
            COMMISSION:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, commission)],
        },
        fallbacks=[CommandHandler("cancel", cancel)])

    app.add_handler(conv)
    app.add_handler(CommandHandler("report", report_rtl_final))
    app.add_handler(CommandHandler("compare", generate_hospital_comparison))
    app.add_handler(CommandHandler("monthly_stats", generate_monthly_stats))
    app.add_handler(
        CommandHandler("department_dist", generate_department_distribution))
    app.add_handler(CommandHandler("doctor_perf", generate_doctor_performance))
    app.add_handler(
        CommandHandler("compare_departments", generate_department_comparison))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", help_command))

    print("🤖 البوت شغال الآن...")
    app.run_polling()


# تأكد أن هذه السطور في آخر الملف بدون مسافات قبلها
if __name__ == "__main__":
    main()
