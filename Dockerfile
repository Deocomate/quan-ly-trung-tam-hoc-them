FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Ho_Chi_Minh

WORKDIR /app

# Cho phép Debian cài các gói non-free (chứa font Microsoft)
RUN echo "deb http://deb.debian.org/debian bookworm contrib non-free" > /etc/apt/sources.list.d/contrib.list

RUN apt-get update && \
    # Tự động đồng ý điều khoản cài đặt font của Microsoft
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libglib2.0-0 \
    shared-mime-info \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    ttf-mscorefonts-installer \
    fontconfig \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Cập nhật lại cache font cho Linux
RUN fc-cache -f -v

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/database /app/static/assets

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
