import os
import telebot
from telebot import types
import yt_dlp

# Подтягиваем токен из переменных окружения Render
TOKEN = os.getenv("BOT_TOKEN")

# Проверка, что переменная окружения вообще задана
if not TOKEN:
    raise ValueError("Ошибка: Переменная окружения BOT_TOKEN не установлена!")

bot = telebot.TeleBot(TOKEN, timeout=60)

# Директория для временного сохранения скачанных треков
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

@bot.callback_query_handler(func=lambda call: call.data.startswith('download_'))
def handle_download(call):
    video_id = call.data.replace('download_', '')
    
    file_id = video_id
    track_title = "Audio Track"
    uploader = "YouTube Bot"

    downloading_msg = bot.send_message(call.message.chat.id, "⏳ Скачиваю и обрабатываю трек...")
    file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s"),
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'nocheckcertificate': True,
        'geo_bypass': True,
        'keepvideo': False,
    }

    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
    
    try:
        track_url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([track_url])
            
            if os.path.exists(file_path):
                bot.edit_message_text(
                    "🚀 Отправляю трек в чат...", 
                    chat_id=call.message.chat.id, 
                    message_id=downloading_msg.message_id
                )
                
                with open(file_path, 'rb') as audio_file:
                    reply_id = call.message.reply_to_message.message_id if call.message.reply_to_message else None
                    
                    bot.send_audio(
                        call.message.chat.id, 
                        audio_file, 
                        title=track_title, 
                        performer=uploader,
                        reply_to_message_id=reply_id
                    )
                
                os.remove(file_path)
                bot.delete_message(call.message.chat.id, downloading_msg.message_id)
            else:
                bot.edit_message_text(
                    "Ошибка обработки файла.", 
                    chat_id=call.message.chat.id, 
                    message_id=downloading_msg.message_id
                )
    
    except Exception as e:
        print(f"Ошибка при скачивании трека с YouTube: {e}")
        bot.edit_message_text(
            "Не удалось скачать этот трек из-за ограничений YouTube.", 
            chat_id=call.message.chat.id, 
            message_id=downloading_msg.message_id
        )
        
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    print("Бот успешно запущен...")
    bot.infinity_polling()