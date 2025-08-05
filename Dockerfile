# 使用一個較不精簡的 Python 基礎映像，更穩定的版本
FROM python:3.10-buster

# 設定工作目錄
WORKDIR /app

# 確保 apt-get 數據庫是最新的
# 安裝所有必要的系統依賴，特別是針對 OpenCV (libGL.so.1) 和 Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    wget \
    # OpenCV 相關依賴：確保 libGL.so.1 及其他相關庫被找到
    libgl1 \
    libgl1-mesa-glx \
    libglx-mesa0 \
    libglu1-mesa \
    libegl1-mesa \
    mesa-utils \
    libglvnd-dev \
    # 常用 X11 和圖像相關庫 (OpenCV 可能間接依賴)
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libgdk-pixbuf2.0-0 \
    libsm6 \
    libice6 \
    libxkbcommon0 \
    libxi6 \
    libxrandr2 \
    libxfixes3 \
    libxcursor1 \
    libxdamage1 \
    libxinerama1 \
    libxcomposite1 \
    libnss3 \
    libasound2 \
    libgbm1 \
    libdbus-1-3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    ffmpeg \
    # 清理 apt 緩存以減小映像大小
    && rm -rf /var/lib/apt/lists/* \
    # 重新配置動態連結庫
    && ldconfig

# **關鍵步驟：確保 libGL.so.1 的路徑在運行時可用**
# 顯式設置 LD_LIBRARY_PATH，指向常見的共享庫路徑
ENV LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu/:/usr/lib/:${LD_LIBRARY_PATH}"
# 創建一個符號連結作為備用方案，如果 LD_LIBRARY_PATH 不夠
RUN ln -s /usr/lib/x86_64-linux-gnu/libGL.so.1 /usr/lib/libGL.so.1 || true \
    && ldconfig # 再次運行 ldconfig 確保連結生效

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
