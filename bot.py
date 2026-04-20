import logging
import os
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
MONTH, COUNTER_SU, COSTO_ENERGIA, COSTO_ACCESSORI, KWH_TOTAL, CONFIRM = range(6)

MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
]

sheets = SheetsClient()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono il tuo assistente per le bollette della luce.\n\n"
        "Comandi disponibili:\n"
        "/add — aggiungere dati del mese\n"
        "/get — visualizzare i dati di un mese\n"
        "/cancel — annullare l'operazione in corso"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[m] for m in MONTHS]
    await update.message.reply_text(
        "📅 Seleziona il mese:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return MONTH


async def add_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    month = update.message.text.strip()
    if month not in MONTHS:
        await update.message.reply_text("❌ Mese non valido. Scegli dalla lista.")
        return MONTH
    context.user_data["month"] = month
    await update.message.reply_text(
        f"✅ Mese: {month}\n\n"
        "🔌 Inserisci le letture del contatore di *sopra* (Contatore Picotti, colonna B):\n"
        "Esempio: `2672.9`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return COUNTER_SU


async def add_counter_su(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        context.user_data["counter_su"] = val
    except ValueError:
        await update.message.reply_text("❌ Inserisci un numero valido. Esempio: `2672.9`", parse_mode="Markdown")
        return COUNTER_SU

    await update.message.reply_text(
        "💶 Inserisci il *costo energia* (colonna B del foglio Luce):\n"
        "Esempio: `87.99`",
        parse_mode="Markdown"
    )
    return COSTO_ENERGIA


async def add_costo_energia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        context.user_data["costo_energia"] = val
    except ValueError:
        await update.message.reply_text("❌ Inserisci un numero valido. Esempio: `87.99`", parse_mode="Markdown")
        return COSTO_ENERGIA

    await update.message.reply_text(
        "💶 Inserisci il *costo accessori* (colonna C del foglio Luce):\n"
        "Esempio: `52.01`",
        parse_mode="Markdown"
    )
    return COSTO_ACCESSORI


async def add_costo_accessori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = [float(p.replace(",", ".")) for p in update.message.text.replace(" ", "").split("+")]
        val = round(sum(parts), 2)
        context.user_data["costo_accessori"] = val
    except ValueError:
        await update.message.reply_text(
            "❌ Inserisci un numero valido. Esempi: `52.01` oppure `24+30+17`",
            parse_mode="Markdown"
        )
        return COSTO_ACCESSORI

    await update.message.reply_text(
        f"✅ Costo accessori: {val}\n\n"
        "⚡ Inserisci i *kWh totali* (colonna D del foglio Luce):\n"
        "Esempio: `350.77`",
        parse_mode="Markdown"
    )
    return KWH_TOTAL


async def add_kwh_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        context.user_data["kwh_total"] = val
    except ValueError:
        await update.message.reply_text("❌ Inserisci un numero valido. Esempio: `350.77`", parse_mode="Markdown")
        return KWH_TOTAL

    data = context.user_data
    month = data["month"]

    await update.message.reply_text(
        f"📋 *Riepilogo dati da inserire:*\n\n"
        f"📅 Mese: {month}\n"
        f"🔌 Contatore sopra: {data['counter_su']}\n"
        f"💶 Costo energia: {data['costo_energia']}\n"
        f"💶 Costo accessori: {data['costo_accessori']}\n"
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
    month = data["month"]

    await update.message.reply_text("⏳ Salvataggio in corso...")

    try:
        # Write to both sheets
        sheets.write_contatore(month, data["counter_su"])
        sheets.write_luce(
            month,
            data["costo_energia"],
            data["costo_accessori"],
            data["kwh_total"]
        )

        # Read back results
        result = sheets.get_month_result(month)

        if result:
            await update.message.reply_text(
                f"✅ *Dati salvati per {month}!*\n\n"
                f"📊 *Risultato:*\n"
                f"💰 Costo 1 kWh: €{result['costo_kwh']}\n"
                f"👤 A testa sopra: €{result['a_testa_su']}\n"
                f"👤 A testa sotto: €{result['a_testa_giu']}\n"
                f"🔄 Torna?: {result['torna']}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"✅ Dati salvati per {month}!\n"
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
    return MONTH


async def get_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    month = update.message.text.strip()
    if month not in MONTHS:
        await update.message.reply_text("❌ Mese non valido.")
        return MONTH

    await update.message.reply_text(
        "⏳ Recupero dati...",
        reply_markup=ReplyKeyboardRemove()
    )

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
                f"💰 Costo 1 kWh: €{result['costo_kwh']}\n"
                f"👤 A testa sopra: €{result['a_testa_su']}\n"
                f"👤 A testa sotto: €{result['a_testa_giu']}\n"
                f"🔄 Torna?: {result['torna']}"
            )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error getting data: {e}")
        await update.message.reply_text(f"❌ Errore: `{str(e)}`", parse_mode="Markdown")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Operazione annullata.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN environment variable not set")

    app = Application.builder().token(token).build()

    # /add conversation
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_month)],
            COUNTER_SU: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_counter_su)],
            COSTO_ENERGIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_costo_energia)],
            COSTO_ACCESSORI: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_costo_accessori)],
            KWH_TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_kwh_total)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_data)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # /get conversation
    get_conv = ConversationHandler(
        entry_points=[CommandHandler("get", get_start)],
        states={
            MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_month)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(get_conv)

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
