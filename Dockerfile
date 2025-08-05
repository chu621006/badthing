# 使用一個較不精簡的 Python 基礎映像
FROM python:3.10-buster

# 設定工作目錄
WORKDIR /app

# 確保 apt-get 數據庫是最新的，並且安裝必要的系統依賴
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

# 設定 Tesseract 語言數據檔案的路徑。
# Tesseract OCR 會在 TESSDATA_PREFIX 指向的目錄下尋找一個名為 tessdata 的子目錄，然後在其內部尋找語言包。
# 由於我們將 chi_tra.traineddata 直接放在 /usr/share/tesseract-ocr/tessdata/，
# 所以 TESSDATA_PREFIX 應該設定為 /usr/share/tesseract-ocr/
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/

# **關鍵修改：明確將 /usr/bin 加入 PATH 環境變數**
# 確保 tesseract 執行檔（通常安裝在 /usr/bin/）在應用程式運行時可被找到。
ENV PATH="/usr/bin:${PATH}" # <--- 在這裡新增這一行

# 啟動 Streamlit 應用程式
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]
