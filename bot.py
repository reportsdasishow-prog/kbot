import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
import yt_dlp

# Токен берется из переменных окружения Render
API_TOKEN = os.environ.get('BOT_TOKEN')
if not API_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

bot = telebot.TeleBot(API_TOKEN)

DOWNLOAD_DIR = 'downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Класс для обработки проверок доступности от Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_health_check_server():
    # Render автоматически передает порт в переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Веб-сервер запущен на порту {port}")
    server.serve_forever()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне название песни, и я найду её.")

@bot.message_handler(func=lambda message: True)
def search_and_send_audio(message):
    query = message.text
    status_msg = bot.reply_to(message, f"🔍 Ищу и скачиваю: '{query}'...")
    
ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
        'quiet': True,
        # Обход блокировок: заставляем запросы выглядеть как запросы с Android/iOS приложений
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            if not info or 'entries' not in info or len(info['entries']) == 0:
                bot.edit_message_text("Песня не найдена.", chat_id=message.chat.id, message_id=status_msg.message_id)
                return
            
            video_info = info['entries'][0]
            title = video_info.get('title', 'Аудио')
            uploader = video_info.get('uploader', 'Неизвестен')
            
            expected_filename = ydl.prepare_filename(video_info)
            file_path = os.path.splitext(expected_filename)[0] + '.mp3'
            
            if os.path.exists(file_path):
                bot.edit_message_text("🚀 Отправляю файл...", chat_id=message.chat.id, message_id=status_msg.message_id)
                with open(file_path, 'rb') as audio_file:
                    bot.send_audio(
                        message.chat.id, 
                        audio_file, 
                        title=title, 
                        performer=uploader,
                        reply_to_message_id=message.message_id
                    )
                os.remove(file_path)
                bot.delete_message(message.chat.id, status_msg.message_id)
            else:
                bot.edit_message_text("Не удалось обработать аудио.", chat_id=message.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        print(f"Ошибка: {e}")
        bot.edit_message_text("Произошла ошибка при поиске.", chat_id=message.chat.id, message_id=status_msg.message_id)

if __name__ == '__main__':
    # Запуск веб-сервера в фоновом потоке для прохождения Health Check на Render
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    print("Бот запускает polling...")
    bot.infinity_polling()
