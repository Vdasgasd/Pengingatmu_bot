import os
from dotenv import load_dotenv
import mysql.connector
from telegram import Update
import schedule
import time
import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext


load_dotenv()

TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")

db_connection = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_DATABASE
)

db_cursor = db_connection.cursor()

# Daftar status untuk mesin percakapan (ConversationHandler)
CHOOSING, TYPING_EVENT_NAME, TYPING_EVENT_DATE = range(3)

def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Selamat datang di Bot Reminder! Gunakan /events untuk membuat event baru.")

def create_event(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Silakan masukkan nama event:")
    return TYPING_EVENT_NAME

def receive_event_name(update: Update, context: CallbackContext) -> int:
    event_name = update.message.text
    context.user_data['event_name'] = event_name
    update.message.reply_text("Masukkan tanggal event (YYYY-MM-DD):")
    return TYPING_EVENT_DATE

def receive_event_date(update: Update, context: CallbackContext) -> int:
    event_date = update.message.text
    event_name = context.user_data['event_name']
    user_id = update.message.from_user.id
    # Simpan event ke database MySQL
    insert_event(update, user_id, event_name, event_date)
    update.message.reply_text(f"Event '{event_name}' telah dibuat pada tanggal {event_date}.")
    return ConversationHandler.END



def insert_event(update: Update, user_id, event_name, event_date):
    # Buat query SQL untuk menyimpan event ke database
    query = "INSERT INTO events (user_id, event_name, event_date) VALUES (%s, %s, %s)"
    values = (user_id, event_name, event_date)
    db_cursor.execute(query, values)
    db_connection.commit()

    # Konversi tanggal event ke format yang dapat dipahami oleh schedule
    event_date_obj = datetime.datetime.strptime(event_date, '%Y-%m-%d')

    # Jadwalkan tugas untuk mengirim pesan pada tanggal event
    schedule.every().day.at(event_date_obj.strftime('%H:%M')).do(send_event_reminder, update, event_name)

def send_event_reminder(update: Update, event_name):
    # Kirim pesan pengingat ke pengguna
    update.message.reply_text(f"Ingat, hari ini adalah '{event_name}'!")
    
def list_events(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    # Query database untuk mengambil daftar event milik pengguna berdasarkan user_id
    query = "SELECT event_name, event_date FROM events WHERE user_id = %s"
    db_cursor.execute(query, (user_id,))
    events = db_cursor.fetchall()

    if events:
        event_list = "\n".join([f"{event[0]} pada {event[1].strftime('%Y-%m-%d')}" for event in events])
        update.message.reply_text(f"Daftar Event Anda:\n{event_list}")
    else:
        update.message.reply_text("Anda belum memiliki event yang dibuat.")    


def main():
    updater = Updater(token=TELEGRAM_API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create_event)],
        states={
            TYPING_EVENT_NAME: [MessageHandler(Filters.text & ~Filters.command, receive_event_name)],
            TYPING_EVENT_DATE: [MessageHandler(Filters.text & ~Filters.command, receive_event_date)],
        },
        fallbacks=[]
    )

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(conv_handler)

    # Tambahkan handler untuk perintah list events
    dispatcher.add_handler(CommandHandler('events', list_events))


    updater.start_polling()
    updater.idle()

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()