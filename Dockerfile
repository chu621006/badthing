# 使用一個較不精簡的 Python 基礎映像 (從 slim-buster 改為 buster)
FROM python:3.10-buster # <--- 這裡更改了！

# 設定工作目錄
WORKDIR /app

# 確保 apt-get 數據庫是最新的，並且安裝必要的系統依賴
# tesseract-ocr: Tesseract OCR 引擎本身
# libgl1-mesa-glx: 提供 libGL.so.1，解決圖形相關錯誤 (重點修復)
# 其他 OpenCV 相關的通用圖形庫 (libglib2.0-0, libsm6, libxext6, libxrender1, libfontconfig1, libgdk-pixbuf2.0-0)
# python3.10-dev: 確保 Python 開發相關頭文件齊全
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
    # 清理 APT 緩存，減少映像大小
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig # <--- 新增了這個命令，確保動態鏈接庫被正確刷新

# 下載並安裝繁體中文語言包 (chi_tra.traineddata)
# 這是從 Tesseract OCR 官方 GitHub 倉庫下載語言包，避免 apt-get 無法定位的問題
RUN mkdir -p /usr/share/tesseract-ocr/4.00/tessdata/ && \
    wget https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/chi_tra.traineddata \
         -P /usr/share/tesseract-ocr/4.00/tessdata/

# 複製您的 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製您的 Streamlit 應用程式檔案
COPY . .

# 設定 Tesseract 語言數據檔案的路徑。這是非常關鍵的。
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# 啟動 Streamlit 應用程式
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]
