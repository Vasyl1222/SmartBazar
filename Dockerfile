# Використовуємо офіційний образ Python як базовий
FROM python:3.9-slim

# Встановлюємо робочу директорію в контейнері
WORKDIR /app

# Копіюємо файл requirements.txt, який містить всі залежності
COPY requirements.txt .

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо решту файлів вашого проекту до контейнера
COPY . .

# Відкриваємо порт, на якому буде працювати додаток (за умовчанням Flask працює на 5000)
EXPOSE 5000

# Команда для запуску Flask додатку
CMD ["flask", "run", "--host=0.0.0.0"]
