# 使用一個較不精簡的 Python 基礎映像
FROM python:3.10-buster

# 設定工作目錄
WORKDIR /app

# 確保 apt-get 數據庫是最新的，並且安裝必要的系統依賴
# 添加更全面的 OpenGL 相關函式庫
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libgdk-pixbuf2.0-0 \
    python3.10-dev \
    poppler-utils \
    mesa-utils \        # <-- 新增
    libglvnd-dev \      # <-- 新增
    libegl1-mesa \      # <-- 新增
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig

# 下載並安裝繁體中文語言包 (chi_tra.traineddata)
RUN mkdir -p /usr/share/tesseract-ocr/tessdata/ && \
    wget https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/chi_tra.traineddata \
         -P /usr/share/tesseract-ocr/tessdata/

# 複製您的 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製您的 Streamlit 應用程式檔案
COPY . .

# 診斷命令 (用於調試，之後若成功可移除)
RUN echo "Current PATH in Docker build: $PATH"
RUN which tesseract || echo "tesseract not found by 'which' command"
RUN tesseract --version || echo "tesseract --version failed"

# 設定 Tesseract 語言數據檔案的路徑。
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/

# 確保 tesseract 執行檔（通常安裝在 /usr/bin/）在應用程式運行時可被找到。
ENV PATH="/usr/bin:${PATH}"

# 啟動 Streamlit 應用程式
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]
