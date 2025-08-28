import sqlite3
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from tabulate import tabulate  # مكتبة جديدة للجداول

# ========= إعداد التسجيل =========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========= إعداد قاعدة البيانات =========
conn = sqlite3.connect("operations.db", check_same_thread=False)
cursor = conn.cursor()
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

# ========= الحالات =========
DATE, PATIENT, HOSPITAL, DEPARTMENT, DOCTOR, PROCEDURE, AMOUNT, DISCOUNT, COMMISSION = range(9)

# ========= دوال البوت الأساسية =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أدخل تاريخ العملية (YYYY-MM-DD):")
    return DATE

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text("اسم المريض:")
    return PATIENT

async def patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patient"] = update.message.text
    await update.message.reply_text("اسم المستشفى:")
    return HOSPITAL

async def hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["hospital"] = update.message.text
    await update.message.reply_text("القسم:")
    return DEPARTMENT

async def department(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["department"] = update.message.text
    await update.message.reply_text("اسم الطبيب:")
    return DOCTOR

async def doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["doctor"] = update.message.text
    await update.message.reply_text("نوع الإجراء:")
    return PROCEDURE

async def procedure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["procedure"] = update.message.text
    await update.message.reply_text("المبلغ:")
    return AMOUNT

async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["amount"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("⚠️ أدخل رقم صحيح للمبلغ:")
        return AMOUNT
    await update.message.reply_text("التخفيض (0 إذا لا يوجد):")
    return DISCOUNT

async def discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["discount"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("⚠️ أدخل رقم صحيح للتخفيض:")
        return DISCOUNT
    await update.message.reply_text("العمولة (0 إذا لا يوجد):")
    return COMMISSION

async def commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["commission"] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("⚠️ أدخل رقم صحيح للعمولة:")
        return COMMISSION

    cursor.execute("""
        INSERT INTO operations (date, patient, hospital, department, doctor, procedure, amount, discount, commission)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        context.user_data["date"], context.user_data["patient"], context.user_data["hospital"],
        context.user_data["department"], context.user_data["doctor"], context.user_data["procedure"],
        context.user_data["amount"], context.user_data["discount"], context.user_data["commission"]
    ))
    conn.commit()
    await update.message.reply_text("✅ تم حفظ العملية بنجاح")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم إلغاء العملية")
    return ConversationHandler.END

async def simple_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT COUNT(*), SUM(amount) FROM operations")
    data = cursor.fetchone()
    count = data[0] or 0
    total = data[1] or 0
    
    await update.message.reply_text(
        f"📊 تقرير مبسط:\n"
        f"• عدد العمليات: {count}\n"
        f"• إجمالي المبالغ: {total:.2f}\n"
        f"• استخدام /add لإضافة عمليات جديدة"
    )

# ========= دالة التقرير المفصل الجديدة (المرحلة 1) =========
async def detailed_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء تقرير مفصل بجدول"""
    try:
        # جلب جميع البيانات من قاعدة البيانات
        cursor.execute("""
            SELECT date, patient, hospital, department, doctor, procedure, amount 
            FROM operations ORDER BY date DESC
        """)
        data = cursor.fetchall()

        if not data:
            await update.message.reply_text("📭 لا توجد عمليات مسجلة")
            return

        # إنشاء جدول البيانات
        headers = ["التاريخ", "المريض", "المستشفى", "القسم", "الطبيب", "الإجراء", "المبلغ"]
        
        # تحويل البيانات إلى قائمة من القوائم
        table_data = []
        for row in data:
            table_data.append([
                row[0], row[1], row[2], row[3], row[4], row[5], f"{row[6]:.2f}"
            ])

        # إنشاء الجدول باستخدام tabulate
        table = tabulate(table_data, headers=headers, tablefmt="grid")

        # إضافة الإجماليات
        cursor.execute("SELECT COUNT(*), SUM(amount) FROM operations")
        count, total = cursor.fetchone()
        
        summary = f"\n📊 **الإجماليات:**\n"
        summary += f"• عدد العمليات: {count}\n"
        summary += f"• مجموع المبالغ: {total:.2f}\n"

        # إرسال التقرير (مقسم إذا كان طويلاً)
        report = f"📋 **التقرير المفصل للعمليات**\n\n```\n{table}\n```\n{summary}"
        
        if len(report) > 4000:
            # إذا كان التقرير طويلاً، نقسمه
            parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            await update.message.reply_text(report, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in detailed_report: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء إنشاء التقرير")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🏥 **أوامر البوت**:
/add - إضافة عملية جديدة
/report - عرض تقرير مفصل
/simple_report - تقرير مبسط
/help - المساعدة
/cancel - إلغاء العملية الحالية
"""
    await update.message.reply_text(help_text)

# ========= تشغيل البوت =========
def main():
    # جلب التوكن من environment variables في Render
    TOKEN = os.environ['TOKEN']
    
    app = Application.builder().token(TOKEN).build()

    # محادثة إضافة العمليات
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date)],
            PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, patient)],
            HOSPITAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, hospital)],
            DEPARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, department)],
            DOCTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, doctor)],
            PROCEDURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, procedure)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount)],
            DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount)],
            COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, commission)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(add_conv)
    app.add_handler(CommandHandler("report", detailed_report))  # التقرير المفصل
    app.add_handler(CommandHandler("simple_report", simple_report))  # التقرير المبسط
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", help_command))

    print("🤖 البوت شغال الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
