import os
import threading
import uuid
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# Токен берется из переменных окружения Render
API_TOKEN = os.environ.get('BOT_TOKEN')
if not API_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

bot = telebot.TeleBot(API_TOKEN)

DOWNLOAD_DIR = 'downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Кэш для хранения результатов поиска (ограничен 100 запросами для экономии памяти)
SEARCH_CACHE = OrderedDict()
MAX_CACHE_SIZE = 100
ITEMS_PER_PAGE = 8

# Класс для обработки проверок доступности от Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Веб-сервер запущен на порту {port}")
    server.serve_forever()

# Форматирование секунд в читаемый вид (например, 125 -> 2:05)
def format_duration(seconds):
    if not seconds:
        return "--:--"
    try:
        seconds = int(seconds)
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    except:
        return "--:--"

# Генерация клавиатуры для определенной страницы результатов поиска
def generate_search_keyboard(search_id, page=1):
    search_data = SEARCH_CACHE.get(search_id)
    if not search_data:
        return None
    
    results = search_data['results']
    total_items = len(results)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    markup = InlineKeyboardMarkup()
    
    # Индексы элементов для текущей страницы
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
    
    # Кнопки с треками
    for i in range(start_idx, end_idx):
        item = results[i]
        duration = format_duration(item.get('duration'))
        title = item.get('title', 'Без названия')
        
        # Ограничиваем длину названия на кнопке для красоты
        if len(title) > 45:
            title = title[:42] + "..."
        
        button_text = f"{duration} {title}"
        # В callback_data передаем уникальный ID видео
        markup.add(InlineKeyboardButton(text=button_text, callback_data=f"dl_{item['id']}"))
        
    # Строка навигации (пагинация)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="<<", callback_data=f"p_{search_id}_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{page} / {total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text=">>", callback_data=f"p_{search_id}_{page+1}"))
        
    markup.row(*nav_buttons)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне название песни, и я подготовлю список треков.")

@bot.message_handler(func=lambda message: True)
def search_songs(message):
    query = message.text
    status_msg = bot.reply_to(message, f"🔍 Ищу треки по запросу: '{query}'...")
    
    # Быстрый поиск без скачивания медиафайлов
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ищем до 24 результатов (хватит на 3 страницы по 8 элементов)
            info = ydl.extract_info(f"ytsearch24:{query}", download=False)
            
            if not info or 'entries' not in info or len(info['entries']) == 0:
                bot.edit_message_text("К сожалению, ничего не найдено.", chat_id=message.chat.id, message_id=status_msg.message_id)
                return
            
            # Сохраняем результаты поиска в кэш
            search_id = str(uuid.uuid4())[:8]
            SEARCH_CACHE[search_id] = {
                'query': query,
                'results': info['entries']
            }
            
            # Очистка старого кэша при переполнении
            if len(SEARCH_CACHE) > MAX_CACHE_SIZE:
                SEARCH_CACHE.popitem(last=False)
                
            markup = generate_search_keyboard(search_id, page=1)
            if markup:
                bot.edit_message_text(
                    text=f"Аудиозаписи по запросу «{query}»", 
                    chat_id=message.chat.id, 
                    message_id=status_msg.message_id,
                    reply_markup=markup
                )
            else:
                bot.edit_message_text("Ошибка при генерации списка.", chat_id=message.chat.id, message_id=status_msg.message_id)
                
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        bot.edit_message_text("Произошла ошибка при поиске. Попробуйте еще раз.", chat_id=message.chat.id, message_id=status_msg.message_id)

# Обработчик нажатий на инлайн-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = call.data
    
    if data == "ignore":
        bot.answer_callback_query(call.id)
        return
        
    # Обработка перелистывания (p_searchid_page)
    if data.startswith("p_"):
        parts = data.split("_")
        if len(parts) == 3:
            search_id = parts[1]
            page = int(parts[2])
            
            markup = generate_search_keyboard(search_id, page=page)
            if markup:
                search_data = SEARCH_CACHE.get(search_id)
                query = search_data['query'] if search_data else "поиск"
                bot.edit_message_text(
                    text=f"Аудиозаписи по запросу «{query}»",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=markup
                )
            else:
                bot.answer_callback_query(call.id, "Результаты поиска устарели. Сделайте новый запрос.")
        bot.answer_callback_query(call.id)
        return

    # Обработка скачивания конкретного трека (dl_videoid)
    if data.startswith("dl_"):
        video_id = data.replace("dl_", "")
        bot.answer_callback_query(call.id, "Запускаю скачивание...")
        
        # Временное сообщение о загрузке
        downloading_msg = bot.send_message(call.message.chat.id, "⏳ Скачиваю выбранный трек, пожалуйста, подождите...")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            # Сохраняем временно под ID, чтобы избежать проблем с символами в путях
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'{video_id}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }
        
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Аудио')
                uploader = info.get('uploader', 'Неизвестен')
                
                file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
                
                if os.path.exists(file_path):
                    bot.edit_message_text("🚀 Отправляю аудио в чат...", chat_id=call.message.chat.id, message_id=downloading_msg.message_id)
                    with open(file_path, 'rb') as audio_file:
                        bot.send_audio(
                            call.message.chat.id, 
                            audio_file, 
                            title=title, 
                            performer=uploader,
                            # Ответ на сообщение пользователя, если оно доступно
                            reply_to_message_id=call.message.reply_to_message.message_id if call.message.reply_to_message else None
                        )
                    # Чистим за собой
                    os.remove(file_path)
                    bot.delete_message(call.message.chat.id, downloading_msg.message_id)
                else:
                    bot.edit_message_text("Ошибка: не удалось подготовить аудиофайл.", chat_id=call.message.chat.id, message_id=downloading_msg.message_id)
        
        except Exception as e:
            print(f"Ошибка при скачивании трека {video_id}: {e}")
            bot.edit_message_text("Не удалось скачать этот трек. Попробуйте другой из списка.", chat_id=call.message.chat.id, message_id=downloading_msg.message_id)