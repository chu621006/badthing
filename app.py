import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re
import io

from PIL import Image
import pytesseract

# **明確指定 tesseract 執行檔的路徑**
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# 導入 img2table 的 PDF 類 和 TesseractOCR
from img2table.document import PDF as Img2TablePDF
from img2table.ocr import TesseractOCR

# --- 輔助函數 ---
def normalize_text(cell_content):
    """
    標準化從提取的單元格內容。
    處理 None 值、pdfplumber 的 Text 物件和普通字串。
    將多個空白字元（包括換行）替換為單個空格，並去除兩端空白。
    """
    if cell_content is None:
        return ""

    text = ""
    if hasattr(cell_content, 'text'):
        text = str(cell_content.text)
    elif isinstance(cell_content, str):
        text = cell_content
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
        
        if col in seen:
            seen[col] += 1
            unique_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            unique_columns.append(col)
    return unique_columns

# **修改後的 process_pdf_file 函數：直接調用 img2table**
def process_pdf_file(uploaded_file):
    """
    直接使用 img2table + OCR 處理 PDF 檔案，提取表格數據。
    """
    st.info("直接使用 img2table + OCR 提取表格 (適用於圖片型或無邊界表格)...")
    try:
        df = process_image_pdf_with_ocr(uploaded_file)
        if df.empty:
            st.warning("img2table + OCR 未能從 PDF 中提取到任何有效表格數據。")
        return df
    except Exception as e:
        st.error(f"處理 PDF 時發生錯誤：{e}")
        st.error("請確保 Tesseract OCR 引擎及所有相關依賴已正確安裝。")
        return pd.DataFrame()

def process_image_pdf_with_ocr(uploaded_file):
    """
    使用 img2table + Tesseract OCR 處理圖片 PDF，提取表格數據。
    """
    st.info("正在使用 img2table + OCR 提取表格...")
    try:
        pdf_bytes = io.BytesIO(uploaded_file.read())

        ocr = TesseractOCR(lang="chi_tra")

        doc = Img2TablePDF(src=pdf_bytes, pages="all")

        # 這裡可以調整 img2table 的參數來提高識別率
        # implicit_rows: 如果表格沒有明確行，是否嘗試識別隱含行
        # borderless_tables: 是否嘗試識別無邊界表格 (對您這種PDF很重要)
        extracted_tables = doc.extract_tables(ocr=ocr,
                                              implicit_rows=True, # <--- 嘗試設為 True
                                              borderless_tables=True, # <--- 設為 True，對於無邊界表格很重要
                                              min_confidence=70) # <--- 可以適當降低或保持，看效果

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

                # **改進列名處理：再次統一處理，並假設第一行是列名**
                if not merged_df.empty:
                    # 嘗試將第一行作為列名
                    header = merged_df.iloc[0].tolist()
                    header = [normalize_text(h) for h in header] # 再次標準化表頭
                    header = make_unique_columns(header) # 確保列名唯一
                    
                    if len(header) == merged_df.shape[1]: # 檢查列數是否匹配
                        merged_df.columns = header
                        merged_df = merged_df[1:].reset_index(drop=True) # 移除表頭行
                    else:
                        st.warning("提取到的列數與表頭不匹配，可能導致列名錯誤。")
                        # 如果不匹配，就保留原來的數字列名，讓使用者檢查
                
                st.success("成功使用 img2table + OCR 提取表格。")
                return merged_df
            else:
                st.warning("img2table + OCR 未能從 PDF 中提取到任何表格數據。")
                return pd.DataFrame()
        else:
            st.warning("img2table + OCR 未能從 PDF 中提取到任何表格數據。")
            return pd.DataFrame()

    except Exception as e:
        st.error(f"使用 img2table 處理圖片 PDF 時發生錯誤：{e}")
        st.error("請確保 Dockerfile 正確安裝了 Tesseract OCR 引擎和所有相關的系統依賴（如 libGL.so.1 等）。")
        return pd.DataFrame()

def parse_course_data(df):
    """
    從 DataFrame 中解析課程數據，計算總學分和不及格學分。
    """
    parsed_courses = []
    failed_courses = []
    
    # 定義可能的列名，並標準化以便匹配
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
        # 對可能的名稱進行更靈活的匹配 (例如 "學 年 度" 也能匹配 "學年度")
        for name in possible_names:
            matching_cols = [col for col in df.columns if normalize_text(name).replace(' ', '') in normalize_text(col).replace(' ', '')]
            if matching_cols:
                actual_cols[standard_col] = matching_cols[0]
                break
        if standard_col not in actual_cols:
            st.warning(f"未能識別出關鍵欄位：{standard_col}。請檢查PDF中的表格標題。")
            return [], [] # 如果關鍵欄位缺失，則返回空列表

    for index, row in df.iterrows():
        try:
            # 跳過可能作為表頭的行（例如包含"學年度"的行，這在 img2table 處理後可能仍然存在）
            # 這裡的判斷可能需要更精確，如果第一行已經被移除，則不需要
            # 但為了健壯性，可以保留
            if any(key_word in normalize_text(row.to_string()) for key_word in ['學年度', '學期', '選課代號', '科目名稱', '學分', 'GPA', '成績']):
                # 判斷是否為實際數據行，這裡可能需要更精確的邏輯
                # 簡單判斷：如果某行在學年度或學分位置是空的，可能是無效行
                if not normalize_text(row[actual_cols['學年度']]).strip() or \
                   not normalize_text(row[actual_cols['學分']]).strip():
                    continue

            year_term = f"{normalize_text(row[actual_cols['學年度']])}{normalize_text(row[actual_cols['學期']])}"
            
            credit_str = normalize_text(row[actual_cols['學分']])
            gpa_str = normalize_text(row[actual_cols['GPA']])

            if not credit_str.strip() or not credit_str.replace('.', '', 1).isdigit():
                continue
            credit = float(credit_str)

            course_data = {
                '學年度學期': year_term,
                '選課代號': normalize_text(row[actual_cols['選課代號']]),
                '科目名稱': normalize_text(row[actual_cols['科目名稱']]),
                '學分': credit,
                'GPA': gpa_str
            }

            is_pe_class = "體育" in course_data['科目名稱']
            is_general_class = "通識" in course_data['科目名稱'] or \
                                "人文" in course_data['科目名稱'] or \
                                "社會" in course_data['科目名稱'] or \
                                "自然" in course_data['科目名稱'] or \
                                "歷史" in course_data['科目名稱'] or \
                                "哲學" in course_data['科目名稱']

            gpa_upper = gpa_str.upper().strip()

            if gpa_upper in ["D", "E", "F", "不計", "未通過"] or (gpa_upper.isdigit() and float(gpa_upper) < 60):
                failed_courses.append(course_data)
            elif gpa_upper == "通過":
                parsed_courses.append(course_data)
            else:
                parsed_courses.append(course_data)

        except KeyError as ke:
            st.warning(f"缺少關鍵列：{ke}。請檢查提取的表格是否包含所有必要的標題。")
            return [], [] # 如果列名匹配失敗，直接返回空
        except Exception as e:
            #st.warning(f"解析行時出錯：{row.to_dict()} - {e}")
            continue
            
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

            if calculated_courses:
                st.subheader("通過的科目列表 (計入學分)：")
                display_passed_df = pd.DataFrame([c for c in calculated_courses if c['學分'] > 0])
                
                display_cols_passed = ['學年度學期', '選課代號', '科目名稱', '學分', 'GPA']
                final_display_passed_cols = [col for col in display_cols_passed if col in display_passed_df.columns]

                st.dataframe(display_passed_df[final_display_passed_cols], height=300, use_container_width=True)
            else:
                st.info("沒有找到通過的科目。")

            if failed_courses:
                st.subheader("不及格的科目列表 (不計入總學分)：")
                failed_df = pd.DataFrame(failed_courses)
                
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
