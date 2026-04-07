FROM python:3.10-slim

WORKDIR /app

# 安裝 rclone 與必要依賴
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    rclone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "main.py"]
