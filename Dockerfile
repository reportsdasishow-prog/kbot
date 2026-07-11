FROM python:3.12-slim

# Устанавливаем ffmpeg и nodejs (в качестве JS-рантайма для yt-dlp)
RUN apt-get update && apt-get install -y ffmpeg nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
