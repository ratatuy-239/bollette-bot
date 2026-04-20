import logging
import os
import tempfile
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from sheets import SheetsClient
from bolletta_parser import parse_bolletta

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_PDF, COUNTER_SU, CONFIRM = range(3)

MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
]

sheets = SheetsClient()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono il tuo assistente per le bollette della luce.\n\n"
        "Comandi disponibili:\n"
        "/add — aggiungere dati del mese (invia il PDF della bolletta)\n"
        "/get — visualizzare i dati di un mese\n"
        "/cancel — annullare l'operazione in corso"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 Invia il PDF della bolletta E.ON e leggo i dati automaticamente."
    )
    return WAITING_PDF


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    await update.message.reply_text("⏳ Leggo la bolletta...")

    # Download to a temp file
    tg_file = await context.bot.get_file(doc.file_id)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    await tg_file.download_to_drive(tmp_path)

    data = parse_bolletta(tmp_path)
    os.unlink(tmp_path)

    if not data:
        await update.message.reply_text(
            "❌ Non riesco a leggere i dati dalla bolletta.\n"
            "Assicurati di inviare una bolletta E.ON in formato PDF."
        )
        return WAITING_PDF

    context.user_data.update(data)

    await update.message.reply_text(
        f"✅ *Dati estratti dalla bolletta:*\n\n"
        f"📅 Mese: {data['month']}\n"
        f"⚡ kWh totali: {data['kwh_total']}\n"
        f"💶 Costo energia: €{data['costo_energia']}\n"
        f"💶 Costo accessori: €{data['costo_accessori']}\n\n"
        f"🔌 Inserisci le letture attuali del contatore di *sopra*:\n"
        f"Esempio: `2672.9`",
        parse_mode="Markdown"
    )
    return COUNTER_SU


async def add_counter_su(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        context.user_data["counter_su"] = val
    except ValueError:
        await update.message.reply_text(
            "❌ Inserisci un numero valido. Esempio: `2672.9`", parse_mode="Markdown"
        )
        return COUNTER_SU

    data = context.user_data
    await update.message.reply_text(
        f"📋 *Riepilogo dati da inserire:*\n\n"
        f"📅 Mese: {data['month']}\n"
        f"🔌 Contatore sopra: {data['counter_su']}\n"
        f"💶 Costo energia: €{data['costo_energia']}\n"
        f"💶 Costo accessori: €{data['costo_accessori']}\n"
        f"⚡ kWh totali: {data['kwh_total']}\n\n"
        f"Confermo e salvo? Rispondi *sì* oppure *no*.",
        parse_mode="Markdown"
    )
    return CONFIRM


async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text not in ["sì", "si", "yes", "да", "ок", "ok"]:
        await update.message.reply_text("❌ Operazione annullata.")
        return ConversationHandler.END

    data = context.user_data
    billing_month = data["month"]  # month from the bill (e.g. Marzo)
    current_month = MONTHS[datetime.now().month - 1]  # current calendar month (e.g. Aprile)

    await update.message.reply_text("⏳ Salvataggio in corso...")

    try:
        # Counter reading goes to current month row in Contatore Picotti
        sheets.write_contatore(current_month, data["counter_su"])
        # Bill data goes to billing period month row in Luce
        sheets.write_luce(
            billing_month,
            data["costo_energia"],
            data["costo_accessori"],
            data["kwh_total"]
        )

        result = sheets.get_month_result(billing_month)

        if result:
            await update.message.reply_text(
                f"✅ *Dati salvati!*\n\n"
                f"📅 Bolletta: {billing_month} | Contatore: {current_month}\n\n"
                f"📊 *Risultato per {billing_month}:*\n"
                f"👤 A testa sopra: €{result['a_testa_su']}\n"
                f"👤 A testa sotto: €{result['a_testa_giu']}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"✅ Dati salvati! Bolletta: {billing_month}, contatore: {current_month}\n"
                "⚠️ Non riesco a leggere i risultati calcolati — controlla il foglio."
            )
    except Exception as e:
        logger.error(f"Error saving data: {e}")
        await update.message.reply_text(
            f"❌ Errore durante il salvataggio:\n`{str(e)}`\n\n"
            "Controlla le credenziali e i permessi del foglio.",
            parse_mode="Markdown"
        )

    return ConversationHandler.END


async def get_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[m] for m in MONTHS]
    await update.message.reply_text(
        "📅 Per quale mese vuoi vedere i dati?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return 10  # separate state namespace for /get


async def get_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    month = update.message.text.strip()
    if month not in MONTHS:
        await update.message.reply_text("❌ Mese non valido.")
        return 10

    await update.message.reply_text("⏳ Recupero dati...", reply_markup=ReplyKeyboardRemove())

    try:
        row = sheets.get_luce_row(month)
        result = sheets.get_month_result(month)

        if not row:
            await update.message.reply_text(f"❌ Nessun dato trovato per {month}.")
            return ConversationHandler.END

        msg = (
            f"📊 *Dati per {month}:*\n\n"
            f"💶 Costo energia: €{row.get('costo_energia', '—')}\n"
            f"💶 Costo accessori: €{row.get('costo_accessori', '—')}\n"
            f"⚡ kWh totali: {row.get('kwh_total', '—')}\n"
        )
        if result:
            msg += (
                f"\n📈 *Risultati calcolati:*\n"
                f"👤 A testa sopra: €{result['a_testa_su']}\n"
                f"👤 A testa sotto: €{result['a_testa_giu']}"
            )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error getting data: {e}")
        await update.message.reply_text(f"❌ Errore: `{str(e)}`", parse_mode="Markdown")

    return ConversationHandler.END


async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current_month = MONTHS[datetime.now().month - 1]
        billing_month = MONTHS[(datetime.now().month - 2) % 12]  # previous month as example
        info = sheets.debug_info(current_month, billing_month)
        await update.message.reply_text(
            f"🔍 *Debug* (contatore={current_month}, bolletta={billing_month}):\n\n{info}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: `{e}`", parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN environment variable not set")

    app = Application.builder().token(token).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            WAITING_PDF: [MessageHandler(filters.Document.PDF, handle_pdf)],
            COUNTER_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_counter_su)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_data)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    get_conv = ConversationHandler(
        entry_points=[CommandHandler("get", get_start)],
        states={
            10: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_month)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("debug", debug))
    app.add_handler(add_conv)
    app.add_handler(get_conv)

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
