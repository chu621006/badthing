# 使用一個較不精簡的 Python 基礎映像
FROM python:3.10-buster

# 設定工作目錄
WORKDIR /app

# 確保 apt-get 數據庫是最新的，並且安裝必要的系統依賴
# 針對 libGL.so.1 錯誤，安裝最核心的 OpenGL 和 V4L 相關庫
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    wget \
    # 核心 OpenCV 依賴：通常解決 libGL.so.1 問題
    libopengl0 \     # <<--- 關鍵：這個庫通常能解決 libGL.so.1 依賴問題
    libv4l-0 \       # <<--- 常用於多媒體和影像處理
    # 其他常見的 Streamlit 和 Python 應用程式依賴
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxext6 \
    libsm6 \
    libxrender1 \
    libfontconfig1 \
    libgdk-pixbuf2.0-0 \
    # 清理 apt 緩存以減小映像大小
    && rm -rf /var/lib/apt/lists/* \
    # 重新配置動態連結庫
    && ldconfig

# **確保 libGL.so.1 的路徑在運行時可用 (保留)**
ENV LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu/:/usr/lib/:${LD_LIBRARY_PATH}"
RUN ln -s /usr/lib/x86_64-linux-gnu/libGL.so.1 /usr/lib/libGL.so.1 || true \
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
RUN echo "Current LD_LIBRARY_PATH in Docker build: $LD_LIBRARY_PATH"
RUN find /usr -name "libGL.so.1*" # 查找 libGL.so.1 的所有實際位置
RUN which tesseract || echo "tesseract not found by 'which' command"
RUN tesseract --version || echo "tesseract --version failed"

# 設定 Tesseract 語言數據檔案的路徑。
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/

# 確保 tesseract 執行檔（通常安裝在 /usr/bin/）在應用程式運行時可被找到。
ENV PATH="/usr/bin:${PATH}"

# 啟動 Streamlit 應用程式
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]
