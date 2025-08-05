# 使用一個較不精簡的 Python 基礎映像
FROM python:3.10-buster

# 設定工作目錄
WORKDIR /app

# 確保 apt-get 數據庫是最新的，並且安裝必要的系統依賴
# tesseract-ocr: Tesseract OCR 引擎本身 (包含tesseract執行檔)
# libgl1-mesa-glx: 提供 libGL.so.1，解決圖形相關錯誤
# 其他 OpenCV 相關的通用圖形庫
# poppler-utils: img2table 處理 PDF 時需要的工具
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
# 注意：TESSDATA_PREFIX 通常指向 tessdata 資料夾的**父目錄**
# 我們將其放在 /usr/share/tesseract-ocr/tessdata/ 下
RUN mkdir -p /usr/share/tesseract-ocr/tessdata/ && \
    wget https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/chi_tra.traineddata \
         -P /usr/share/tesseract-ocr/tessdata/

# 複製您的 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製您的 Streamlit 應用程式檔案
COPY . .

# **關鍵修改：調整 TESSDATA_PREFIX**
# TesseractOCR 會在 TESSDATA_PREFIX/tessdata/ 中尋找語言包
# 但 chi_tra.traineddata 已經直接放在 /usr/share/tesseract-ocr/tessdata/
# 因此 TESSDATA_PREFIX 應該設定為 /usr/share/tesseract-ocr/
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/

# 由於 tesseract-ocr 套件安裝後，tesseract 執行檔通常在 /usr/bin/，
# 而 /usr/bin/ 預設就在 PATH 中，所以通常不需要額外設定 PATH。
# 但為了確保萬無一失，可以明確指出。
# ENV PATH="/usr/bin:${PATH}" # 這行通常不需要，因為 /usr/bin 已在預設PATH中

# 啟動 Streamlit 應用程式
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]
