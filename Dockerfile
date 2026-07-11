FROM python:3.10-slim

# Установка системного пакета ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Команда для запуска бота
CMD ["python", "bot.py"]
