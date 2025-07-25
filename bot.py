import os
import re
import fitz  # PyMuPDF
import pdfplumber
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === CONFIG ===
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'
SIGNATURE_NAME = 'Ali Khursanov'
LAST_FILE_PATH = 'temp/last_uploaded.pdf'

# === UTILITIES ===

def extract_fields_from_pdf(pdf_path):
    extracted = {
        "Rate Confirmation #": "",
        "Bill of Lading #": "",
        "Reference #": "",
        "Weight": "",
        "Description": "",
        "Total Rate": "",
        "Pickup Location": "",
        "Pickup Time": "",
        "Dropoff Location": "",
        "Dropoff Time": ""
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        patterns = {
            "Rate Confirmation #": r"(Route\s*#|Rate\s*Confirmation\s*#?)\s*[:\-]?\s*(\w+)",
            "Bill of Lading #": r"(BOL|Bill\s+of\s+Lading)\s*#?\s*[:\-]?\s*(\w+)",
            "Reference #": r"(Reference\s*#)\s*[:\-]?\s*(\w+)",
            "Weight": r"Weight\s*[:\-]?\s*([\d,]+\s*(lbs|pounds)?)",
            "Description": r"(Commodity|Item|Description)\s*[:\-]?\s*(.+)",
            "Total Rate": r"(Total\s+(Carrier\s+Pay|Rate))\s*[:\-]?\s*\$?([\d,]+\.\d{2})",
            "Pickup Location": r"Pickup\s*(Location|Address)?\s*[:\-]?\s*(.+)",
            "Dropoff Location": r"(Drop|Delivery)\s*(Location|Address)?\s*[:\-]?\s*(.+)",
            "Pickup Time": r"Pickup\s*(Date|Time)?\s*[:\-]?\s*([\d\/\-]+\s*[\d:apm\s]*)",
            "Dropoff Time": r"(Drop|Delivery)\s*(Date|Time)?\s*[:\-]?\s*([\d\/\-]+\s*[\d:apm\s]*)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                extracted[key] = match.groups()[-1].strip()

    except Exception as e:
        print("Extraction error:", e)

    return extracted

def sign_pdf(original_pdf_path, output_pdf_path):
    doc = fitz.open(original_pdf_path)
    text_variants = [
        "signature", "sign here", "please sign", "sign and return", "sign and fax"
    ]

    for page in doc:
        found = False
        text_instances = page.search_for("signature", quads=True)
        if text_instances:
            for inst in text_instances:
                page.insert_text(inst.rect.bottom_left, SIGNATURE_NAME, fontsize=12, color=(0, 0, 0))
                found = True
                break

        # Fallback: Search by keyword
        if not found:
            text = page.get_text().lower()
            if any(var in text for var in text_variants):
                page.insert_text((72, page.rect.height - 72), SIGNATURE_NAME, fontsize=12)
                break

    doc.save(output_pdf_path)
    doc.close()

# === HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Upload a PDF and use /extract or /sign.")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    if not file or not file.file_name.endswith('.pdf'):
        await update.message.reply_text("Please send a valid PDF file.")
        return

    file_path = LAST_FILE_PATH
    await file.get_file().download_to_drive(file_path)
    await update.message.reply_text("PDF received. Use /extract or /sign to proceed.")

async def extract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(LAST_FILE_PATH):
        await update.message.reply_text("Please upload a PDF first.")
        return

    data = extract_fields_from_pdf(LAST_FILE_PATH)
    response = "\n".join([f"{k}: {v or 'Not found'}" for k, v in data.items()])
    await update.message.reply_text(f"📄 Extracted Info:\n\n{response}")

async def sign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(LAST_FILE_PATH):
        await update.message.reply_text("Please upload a PDF first.")
        return

    signed_path = "temp/signed_rate_confirmation.pdf"
    sign_pdf(LAST_FILE_PATH, signed_path)
    await update.message.reply_document(InputFile(signed_path), caption="✅ Signed by Ali Khursanov")

# === MAIN APP ===

def main():
    os.makedirs("temp", exist_ok=True)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("extract", extract))
    app.add_handler(CommandHandler("sign", sign))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
