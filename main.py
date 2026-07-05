import telebot
from telebot import types
import sqlite3
import random
import textwrap
import time
import threading
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import schedule

TOKEN = '8223206380:AAGFhzNk1s-qq0rAt1mkSYeMvlDUnre1rlM'
bot = telebot.TeleBot(TOKEN)
DB_FILE = 'bot_database.db'

# --- БД ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users_scores (user_id INTEGER PRIMARY KEY, score INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, likes INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (user_id INTEGER PRIMARY KEY, referrer_id INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- Функции ---
def create_meme_image(text, filename="meme_temp.png"):
    img = Image.new('RGB', (800, 600), color=(20, 20, 30))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, 760, 560], radius=30, fill=(40, 40, 60), outline=(100, 100, 255), width=3)
    try: font = ImageFont.truetype("arial.ttf", 28)
    except: font = ImageFont.load_default()
    d.text((80, 100), textwrap.fill(text, width=40), fill=(255, 255, 255), font=font)
    img.save(filename)
    return filename

def get_real_meme():
    try:
        res = requests.get("https://baneks.ru/random", timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        return soup.find('article').text.strip()
    except: return "Мем сейчас прячется!"

# --- Обработка ---
@bot.message_handler(commands=['start'])
def start(message):
    # Реферальная логика
    args = message.text.split()
    if len(args) > 1:
        referrer_id = args[1]
        if str(message.chat.id) != referrer_id:
            conn = sqlite3.connect(DB_FILE)
            if not conn.execute('SELECT 1 FROM referrals WHERE user_id = ?', (message.chat.id,)).fetchone():
                conn.execute('INSERT INTO referrals (user_id, referrer_id) VALUES (?, ?)', (message.chat.id, referrer_id))
                conn.execute('UPDATE users_scores SET score = score + 20 WHERE user_id = ?', (referrer_id,))
                conn.commit()
                bot.send_message(referrer_id, "🎉 По твоей ссылке зашел новый друг! +20 очков!")
            conn.close()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎭 Хочу мем!", "📊 Топ", "👤 Профиль", "🎁 Бонус", "⏰ Напоминалка")
    bot.send_message(message.chat.id, "Привет! Ты в Мем-Империи.", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text == "🎭 Хочу мем!":
        text = get_real_meme()
        img_path = create_meme_image(text, f"meme_{message.chat.id}.png")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👍 Лайк", callback_data="like"))
        with open(img_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, reply_markup=markup)
            
    elif message.text == "📊 Топ":
        conn = sqlite3.connect(DB_FILE)
        data = conn.execute('SELECT user_id, score FROM users_scores ORDER BY score DESC LIMIT 5').fetchall()
        conn.close()
        text = "🏆 Топ игроков:\n" + "\n".join([f"{i+1}. ID {uid}: {score}" for i, (uid, score) in enumerate(data)])
        bot.send_message(message.chat.id, text)
        
    elif message.text == "👤 Профиль":
        conn = sqlite3.connect(DB_FILE)
        s = conn.execute('SELECT score FROM users_scores WHERE user_id = ?', (message.chat.id,)).fetchone()
        l = conn.execute('SELECT likes FROM user_stats WHERE user_id = ?', (message.chat.id,)).fetchone()
        conn.close()
        # Генерируем реф ссылку
        ref_link = f"https://t.me/{(bot.get_me().username)}?start={message.chat.id}"
        msg = f"👤 Профиль:\n💰 Очков: {s[0] if s else 0}\n👍 Лайков: {l[0] if l else 0}\n\n🔗 Реф. ссылка:\n{ref_link}"
        bot.send_message(message.chat.id, msg)

    elif message.text == "🎁 Бонус":
        conn = sqlite3.connect(DB_FILE)
        conn.execute('INSERT OR IGNORE INTO users_scores (user_id) VALUES (?)', (message.chat.id,))
        conn.execute('UPDATE users_scores SET score = score + 10 WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🎁 +10 очков за ежедневный бонус!")

    elif message.text == "⏰ Напоминалка":
        conn = sqlite3.connect(DB_FILE)
        if conn.execute('SELECT 1 FROM subscriptions WHERE user_id = ?', (message.chat.id,)).fetchone():
            conn.execute('DELETE FROM subscriptions WHERE user_id = ?', (message.chat.id,))
            bot.send_message(message.chat.id, "🔕 Уведомления выключены.")
        else:
            conn.execute('INSERT INTO subscriptions VALUES (?)', (message.chat.id,))
            bot.send_message(message.chat.id, "🔔 Напоминалка включена!")
        conn.commit()
        conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "like")
def handle_like(call):
    conn = sqlite3.connect(DB_FILE)
    conn.execute('INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)', (call.message.chat.id,))
    conn.execute('UPDATE user_stats SET likes = likes + 1 WHERE user_id = ?', (call.message.chat.id,))
    conn.execute('INSERT OR IGNORE INTO users_scores (user_id) VALUES (?)', (call.message.chat.id,))
    conn.execute('UPDATE users_scores SET score = score + 5 WHERE user_id = ?', (call.message.chat.id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Лайк поставлен! +5 очков.")

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()