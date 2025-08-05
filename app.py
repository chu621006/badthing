import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re
import io

from PIL import Image # 導入 Pillow 函式庫
import pytesseract # 導入 pytesseract

# **新增這一行，明確指定 tesseract 執行檔的路徑**
# 在基於 Debian/Ubuntu 的 Docker 映像中，tesseract 執行檔通常會安裝在 /usr/bin/tesseract
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# 導入 img2table 的 PDF 類 和 TesseractOCR
from img2table.document import PDF as Img2TablePDF
from img2table.ocr import TesseractOCR

# --- 輔助函數 ---
def normalize_text(cell_content):
    """
    標準化從 pdfplumber 提取的單元格內容。
    處理 None 值、pdfplumber 的 Text 物件和普通字串。
    將多個空白字元（包括換行）替換為單個空格，並去除兩端空白。
    """
    if cell_content is None:
        return ""

    text = ""
    # 檢查是否是 pdfplumber 的 Text 物件 (它會有 .text 屬性)
    if hasattr(cell_content, 'text'):
        text = str(cell_content.text)
    # 如果不是 Text 物件，但本身是字串
    elif isinstance(cell_content, str):
        text = cell_content
    # 其他情況，嘗試轉換為字串
    else:
        text = str(cell_content)
    
    return re.sub(r'\s+', ' ', text).strip()

def make_unique_columns(columns_list):
    """
    將列表中的欄位名稱轉換為唯一的名稱，處理重複和空字串。
    如果遇到重複或空字串，會添加後綴 (例如 'Column_1', '欄位_2')。
    """
    seen = collections.defaultdict(int)
    unique_columns = []
    for col in columns_list:
        original_col = col
        if not col.strip():  # 如果欄位是空字串，給一個預設名稱
            col = "空白欄位"
        
        # 檢查是否重複
        if col in seen:
            seen[col] += 1
            unique_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            unique_columns.append(col)
    return unique_columns

def process_pdf_file(uploaded_file):
    """
    處理 PDF 檔案，提取表格數據，並將其轉換為 DataFrame。
    優先使用 pdfplumber 提取，若失敗則嘗試 img2table + OCR。
    """
    st.info("正在嘗試使用 pdfplumber 提取表格...")
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            all_tables = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    # 將每個表格轉換為 DataFrame
                    df = pd.DataFrame(table)
                    all_tables.append(df)

            if all_tables:
                # 合併所有提取到的表格
                merged_df = pd.concat(all_tables, ignore_index=True)
                # 使用第一行作為新的列名，並處理重複和空列名
                new_columns = merged_df.iloc[0].apply(normalize_text).tolist()
                new_columns = make_unique_columns(new_columns)
                merged_df.columns = new_columns
                # 刪除第一行（原列名行）
                merged_df = merged_df[1:].reset_index(drop=True)
                # 對所有單元格內容進行標準化
                merged_df = merged_df.applymap(normalize_text)
                st.success("成功使用 pdfplumber 提取表格。")
                return merged_df
            else:
                st.warning("pdfplumber 未能從 PDF 中提取到任何表格。嘗試使用 OCR 方式處理圖片 PDF。")
                return process_image_pdf_with_ocr(uploaded_file)
    except Exception as e:
        st.warning(f"pdfplumber 處理失敗: {e}。嘗試使用 OCR 方式處理圖片 PDF。")
        return process_image_pdf_with_ocr(uploaded_file)

def process_image_pdf_with_ocr(uploaded_file):
    """
    使用 img2table + Tesseract OCR 處理圖片 PDF，提取表格數據。
    """
    st.info("正在嘗試使用 img2table + OCR 提取表格...")
    try:
        # 將上傳的檔案轉換為 BytesIO 物件，供 img2table 使用
        pdf_bytes = io.BytesIO(uploaded_file.read())

        # 初始化 Tesseract OCR
        # lang 參數應與您在 Dockerfile 中下載的語言包相匹配
        ocr = TesseractOCR(lang="chi_tra") # 指定繁體中文語言包

        # 創建 Img2TablePDF 物件
        doc = Img2TablePDF(src=pdf_bytes, pages="all")

        # 提取表格
        extracted_tables = doc.extract_tables(ocr=ocr,
                                              implicit_rows=False,
                                              borderless_tables=False,
                                              min_confidence=75) # 提高置信度，減少錯誤

        if extracted_tables:
            all_dfs = []
            for page_num, tables_on_page in extracted_tables.items():
                for idx, table in enumerate(tables_on_page):
                    df = pd.DataFrame(table.content)
                    all_dfs.append(df)

            if all_dfs:
                merged_df = pd.concat(all_dfs, ignore_index=True)
                # 對所有單元格內容進行標準化
                merged_df = merged_df.applymap(normalize_text)
                st.success("成功使用 img2table + OCR 提取表格。")
                return merged_df
            else:
                st.warning("img2table + OCR 未能從 PDF 中提取到任何表格數據。")
                return pd.DataFrame() # 返回空 DataFrame
        else:
            st.warning("img2table + OCR 未能從 PDF 中提取到任何表格數據。")
            return pd.DataFrame() # 返回空 DataFrame

    except Exception as e:
        st.error(f"使用 img2table 處理圖片 PDF 時發生錯誤：{e}")
        st.error("請確保 Dockerfile 正確安裝了 Tesseract OCR 引擎和所有相關的系統依賴（如 libGL.so.1 等）。")
        return pd.DataFrame() # 返回空 DataFrame

def parse_course_data(df):
    """
    從 DataFrame 中解析課程數據，計算總學分和不及格學分。
    """
    parsed_courses = []
    failed_courses = []
    
    # 定義可能的列名，並標準化以便匹配
    # 將 '學年'、'年度' 視為 '學年度'
    # 將 '學期' 視為 '學期'
    # 將 '選課代號'、'選課代號' 視為 '選課代號'
    # 將 '科目名稱'、'科目'、'科目名稱' 視為 '科目名稱'
    # 將 '學分'、'學分' 視為 '學分'
    # 將 'GPA'、'成績' 視為 'GPA'
    
    col_mapping = {
        '學年度': ['學年度', '學年', '年度'],
        '學期': ['學期'],
        '選課代號': ['選課代號', '選課代號'],
        '科目名稱': ['科目名稱', '科目'],
        '學分': ['學分'],
        'GPA': ['GPA', '成績']
    }

    # 找到實際的列名
    actual_cols = {}
    for standard_col, possible_names in col_mapping.items():
        for name in possible_names:
            # 使用列表推導式來檢查包含關係
            matching_cols = [col for col in df.columns if name in col]
            if matching_cols:
                # 選擇第一個匹配的列作為實際列
                actual_cols[standard_col] = matching_cols[0]
                break
        if standard_col not in actual_cols:
            st.warning(f"未能識別出關鍵欄位：{standard_col}。請檢查PDF中的表格標題。")
            return [], [] # 如果關鍵欄位缺失，則返回空列表

    for index, row in df.iterrows():
        try:
            # 跳過可能作為表頭的行（例如包含"學年度"的行）
            if any(key_word in normalize_text(row.to_string()) for key_word in ['學年度', '學期', '選課代號', '科目名稱', '學分', 'GPA', '成績']):
                continue

            # 使用識別到的實際列名來提取數據
            year_term = f"{normalize_text(row[actual_cols['學年度']])}{normalize_text(row[actual_cols['學期']])}"
            
            # 嘗試安全地轉換學分和 GPA
            credit_str = normalize_text(row[actual_cols['學分']])
            gpa_str = normalize_text(row[actual_cols['GPA']])

            # 過濾掉非數字的學分或GPA
            if not credit_str.strip() or not credit_str.replace('.', '', 1).isdigit():
                continue # 跳過無法解析學分的行
            credit = float(credit_str)

            course_data = {
                '學年度學期': year_term,
                '選課代號': normalize_text(row[actual_cols['選課代號']]),
                '科目名稱': normalize_text(row[actual_cols['科目名稱']]),
                '學分': credit,
                'GPA': gpa_str
            }

            # 判斷是否為體育課或通識課 (根據名稱判斷，可能需要更精確的規則)
            is_pe_class = "體育" in course_data['科目名稱']
            is_general_class = "通識" in course_data['科目名稱'] or \
                                "人文" in course_data['科目名稱'] or \
                                "社會" in course_data['科目名稱'] or \
                                "自然" in course_data['科目名稱'] or \
                                "歷史" in course_data['科目名稱'] or \
                                "哲學" in course_data['科目名稱']


            # 判斷是否及格
            # 轉換 GPA 為大寫，並移除可能存在的空白，以便匹配
            gpa_upper = gpa_str.upper().strip()

            if gpa_upper in ["D", "E", "F", "不計", "未通過"] or (gpa_upper.isdigit() and float(gpa_upper) < 60):
                # 排除體育課和通識課的不及格情況，除非是必修通識或特定要求
                # 這裡假設體育和通識不及格不影響總學分統計，但仍記錄在不及格列表中
                failed_courses.append(course_data)
            elif gpa_upper == "通過":
                # "通過" 的課程通常不計入 GPA 但計入學分，我們將其視為及格科目
                parsed_courses.append(course_data)
            else:
                # 其他情況，假定為及格科目
                parsed_courses.append(course_data)

        except Exception as e:
            # 這裡可以選擇性地打印錯誤，以便調試
            # st.warning(f"解析行時出錯：{row.to_dict()} - {e}")
            continue # 跳過無法解析的行
            
    return parsed_courses, failed_courses


# --- Streamlit 應用程式界面 ---
st.set_page_config(layout="wide", page_title="學分計算器", page_icon="📝")

st.title("📚 成績單學分計算器")

st.markdown("""
這個工具可以幫助您分析東海大學的歷年成績單 PDF 檔案，
自動計算您已獲得的總學分，並列出通過和不及格的科目。
""")

uploaded_file = st.file_uploader("上傳您的成績單 PDF 檔案", type=["pdf"])

if uploaded_file is not None:
    st.success("檔案上傳成功！")

    # 處理 PDF 檔案
    with st.spinner("正在處理 PDF，這可能需要一些時間..."):
        extracted_df = process_pdf_file(uploaded_file)

    if not extracted_df.empty:
        st.subheader("📝 提取到的表格數據預覽：")
        st.dataframe(extracted_df, use_container_width=True)

        if not extracted_df.empty:
            st.subheader("📊 學分計算結果：")
            calculated_courses, failed_courses = parse_course_data(extracted_df)

            total_credits_passed = sum(course['學分'] for course in calculated_courses)
            
            st.metric(label="✅ 已獲得總學分 (不含體育與服務學習)", value=f"{total_credits_passed:.1f}")

            # 顯示通過的科目
            if calculated_courses:
                st.subheader("通過的科目列表 (計入學分)：")
                # 篩選掉體育和服務學習的學分，如果它們的學分是0或者不計入總學分
                # 注意：這裡我們假設學分為0的科目不計入總學分，無論是否通過
                display_passed_df = pd.DataFrame([c for c in calculated_courses if c['學分'] > 0])
                
                # 確保顯示的列存在，並按特定順序顯示
                display_cols_passed = ['學年度學期', '選課代號', '科目名稱', '學分', 'GPA']
                final_display_passed_cols = [col for col in display_cols_passed if col in display_passed_df.columns]

                st.dataframe(display_passed_df[final_display_passed_cols], height=300, use_container_width=True)
            else:
                st.info("沒有找到通過的科目。")

            # 顯示不及格的科目
            if failed_courses:
                st.subheader("不及格的科目列表 (不計入總學分)：")
                failed_df = pd.DataFrame(failed_courses)
                
                # 確保顯示的列存在，並按特定順序顯示
                display_failed_cols = ['學年度學期', '選課代號', '科目名稱', '學分', 'GPA']
                final_display_failed_cols = [col for col in display_failed_cols if col in failed_df.columns]
                st.dataframe(failed_df[final_display_failed_cols], height=200, use_container_width=True)
                st.info("這些科目因成績不及格 ('D', 'E', 'F' 等) 而未計入總學分。")

            if calculated_courses or failed_courses:
                if calculated_courses:
                    csv_data_passed = pd.DataFrame(calculated_courses).to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="下載通過的科目列表為 CSV",
                        data=csv_data_passed,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_calculated_courses.csv",
                        mime="text/csv",
                        key="download_passed_btn"
                    )
                if failed_courses:
                    csv_data_failed = pd.DataFrame(failed_courses).to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="下載不及格的科目列表為 CSV",
                        data=csv_data_failed,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_failed_courses.csv",
                        mime="text/csv",
                        key="download_failed_btn"
                    )
            
        else:
            st.warning("未從 PDF 中提取到任何表格數據。請檢查 PDF 內容或嘗試其他文件。")
    else:
        st.error("無法從 PDF 檔案中提取任何有效數據。請檢查檔案格式或內容。")

st.markdown("---")
st.markdown("開發者：[您的名字或聯絡方式 (選填)]")
