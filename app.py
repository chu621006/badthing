import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re
import io

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
        if not col or col.isspace(): # 如果欄位是空字串或只有空格
            col = "Unnamed_Column"
        
        if seen[col] > 0:
            unique_col = f"{col}_{seen[col]}"
            while unique_col in unique_columns: # 避免生成再次重複的名稱
                seen[col] += 1
                unique_col = f"{col}_{seen[col]}"
            unique_columns.append(unique_col)
        else:
            unique_columns.append(col)
        seen[original_col] += 1 # 這裡使用原始名稱來計數，確保原名稱在唯一化前也能被計數
        
    return unique_columns

def is_gpa_valid(gpa_str):
    """檢查 GPA 欄位是否為有效值 (字母或數字，排除 '通過' 等非分數類型)"""
    if not isinstance(gpa_str, str):
        return False
    # 過濾掉 '通過', '抵免', '必修', '選修' 等非實際GPA成績
    return bool(re.match(r'^[A-Ea-eDFdfC]{1}[+-]?$|^[0-9.]+$', gpa_str)) and gpa_str not in ["通過", "抵免", "必修", "選修", "通過"]

# --- 主函數：處理 PDF 檔案 ---
def process_pdf_file(uploaded_file):
    all_grades_data = []
    
    # 判斷 PDF 是否為圖片型
    st.info("正在嘗試使用 pdfplumber 提取文本和表格...")
    is_image_pdf = False
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            if not any(page.extract_text() for page in pdf.pages):
                is_image_pdf = True
    except Exception as e:
        st.warning(f"pdfplumber 處理錯誤，可能是圖片型 PDF：{e}")
        is_image_pdf = True # 如果 pdfplumber 失敗，則視為圖片型 PDF

    if is_image_pdf:
        st.info("檢測到圖片型 PDF 或非標準 PDF 格式，嘗試使用 img2table 進行 OCR 處理...")
        return process_image_pdf_with_ocr(uploaded_file)
    else:
        st.info("檢測到可選取文字的 PDF，使用 pdfplumber 提取表格。")
        return process_text_pdf_with_pdfplumber(uploaded_file)

def process_text_pdf_with_pdfplumber(uploaded_file):
    all_grades_data_dfs = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    header = [normalize_text(cell) for cell in table[0]] if table else []
                    
                    # 嘗試清理或映射標頭
                    cleaned_header = []
                    for h in header:
                        if "學年" in h and "度" in h:
                            cleaned_header.append("學年度")
                        elif "學期" in h:
                            cleaned_header.append("學期")
                        elif "科目名稱" in h:
                            cleaned_header.append("科目名稱")
                        elif "學分" in h:
                            cleaned_header.append("學分")
                        elif "GPA" in h:
                            cleaned_header.append("GPA")
                        else:
                            cleaned_header.append(h)
                    
                    unique_header = make_unique_columns(cleaned_header)

                    if not unique_header:
                        continue

                    data = []
                    for row in table[1:]: # 從第二行開始是數據
                        row_data = [normalize_text(cell) for cell in row]
                        # 確保行數據長度與標頭匹配，不足補空字串
                        if len(row_data) < len(unique_header):
                            row_data.extend([''] * (len(unique_header) - len(row_data)))
                        # 如果行數據長度超過標頭，則截斷
                        elif len(row_data) > len(unique_header):
                            row_data = row_data[:len(unique_header)]
                        data.append(row_data)
                    
                    if data:
                        df = pd.DataFrame(data, columns=unique_header)
                        all_grades_data_dfs.append(df)
        
        return pd.concat(all_grades_data_dfs, ignore_index=True) if all_grades_data_dfs else pd.DataFrame()

    except Exception as e:
        st.error(f"使用 pdfplumber 提取表格時發生錯誤: {e}")
        return pd.DataFrame()

def process_image_pdf_with_ocr(uploaded_file):
    all_grades_data_dfs = []
    
    try:
        # 使用 img2table 處理圖片型 PDF
        # 注意：這裡的 TesseractOCR 會自動尋找 TESSDATA_PREFIX 環境變數
        ocr = TesseractOCR(lang="chi_tra") # 指定繁體中文語言包
        
        # 將 uploaded_file 轉換為 BytesIO 物件，供 img2table 使用
        pdf_bytes = io.BytesIO(uploaded_file.getvalue())
        
        # 創建 Img2TablePDF 物件
        doc = Img2TablePDF(src=pdf_bytes)
        
        # 從文檔中提取表格
        extracted_tables = doc.extract_tables(ocr=ocr, implicit_lines=False, borderless_tables=False)

        if not extracted_tables:
            st.warning("img2table 未能從圖片型 PDF 中提取到任何表格數據。")
            return pd.DataFrame()

        for page_idx, tables_on_page in extracted_tables.items():
            for table_idx, table in enumerate(tables_on_page):
                # img2table 返回的 table.df 已經是 DataFrame
                df = table.df
                
                # 對於 img2table 提取的 DataFrame，也進行列名標準化和數據清理
                if not df.empty:
                    # 如果 img2table 導出的 DataFrame 有默認數字列名，嘗試查找並重命名
                    # 否則，保持 img2table 偵測到的列名
                    header = [normalize_text(col) for col in df.columns]
                    
                    # 嘗試映射常見的成績單列名
                    cleaned_header = []
                    for h in header:
                        if "學年" in h and "度" in h:
                            cleaned_header.append("學年度")
                        elif "學期" in h:
                            cleaned_header.append("學期")
                        elif "科目名稱" in h:
                            cleaned_header.append("科目名稱")
                        elif "學分" in h:
                            cleaned_header.append("學分")
                        elif "GPA" in h:
                            cleaned_header.append("GPA")
                        else:
                            cleaned_header.append(h)
                    
                    df.columns = make_unique_columns(cleaned_header)
                    
                    # 對每個單元格的數據進行標準化
                    df = df.applymap(normalize_text)
                    all_grades_data_dfs.append(df)

        return pd.concat(all_grades_data_dfs, ignore_index=True) if all_grades_data_dfs else pd.DataFrame()

    except Exception as e:
        st.error(f"使用 img2table 處理圖片 PDF 時發生錯誤：{e}")
        st.info("請確保 Dockerfile 正確安裝了 Tesseract OCR 引擎和所有相關的系統依賴（如 libGL.so.1 等）。")
        return pd.DataFrame()


# --- Streamlit 應用介面 ---
st.set_page_config(layout="wide")
st.title("成績單學分計算器 🎓")
st.markdown("---")

uploaded_file = st.file_uploader("請上傳您的 PDF 成績單檔案", type="pdf")

if uploaded_file is not None:
    st.success("檔案上傳成功！")

    with st.spinner("正在處理 PDF，這可能需要一些時間..."):
        # 根據 PDF 類型選擇處理方式
        extracted_df = process_pdf_file(uploaded_file)

    if not extracted_df.empty:
        st.subheader("提取到的原始表格數據:")
        st.dataframe(extracted_df, height=300, use_container_width=True)

        st.subheader("數據清洗與學分計算結果:")
        
        # 嘗試識別關鍵欄位，優先使用標準名稱
        col_mapping = {
            '學年度': ['學年度', '學年', 'Academic Year'],
            '學期': ['學期', '期', 'Semester'],
            '科目名稱': ['科目名稱', '科目', 'Course Name'],
            '學分': ['學分', 'Credit'],
            'GPA': ['GPA', '成績', 'Grade']
        }

        found_cols = {}
        for standard_col, possible_names in col_mapping.items():
            for name in possible_names:
                if name in extracted_df.columns:
                    found_cols[standard_col] = name
                    break
            
            # 如果標準列名沒有找到，嘗試從 Make_unique_columns 中找帶後綴的
            if standard_col not in found_cols:
                for col_name_in_df in extracted_df.columns:
                    if col_name_in_df.startswith(standard_col) and (standard_col not in found_cols):
                         found_cols[standard_col] = col_name_in_df
                         break
        
        # 檢查是否所有必要欄位都找到
        required_cols = ["學年度", "學期", "科目名稱", "學分", "GPA"]
        
        if not all(col in found_cols for col in required_cols):
            st.warning("未能自動識別所有必要的成績單欄位 (學年度, 學期, 科目名稱, 學分, GPA)。")
            st.info("請檢查上傳的 PDF 格式，或手動指定欄位名稱。")
            
            # 讓用戶手動選擇欄位
            st.subheader("手動指定欄位：")
            selected_year_col = st.selectbox("請選擇 '學年度' 欄位：", [''] + list(extracted_df.columns))
            selected_semester_col = st.selectbox("請選擇 '學期' 欄位：", [''] + list(extracted_df.columns))
            selected_course_name_col = st.selectbox("請選擇 '科目名稱' 欄位：", [''] + list(extracted_df.columns))
            selected_credit_col = st.selectbox("請選擇 '學分' 欄位：", [''] + list(extracted_df.columns))
            selected_gpa_col = st.selectbox("請選擇 'GPA' / '成績' 欄位：", [''] + list(extracted_df.columns))

            if st.button("確認手動選擇"):
                # 更新 found_cols
                if selected_year_col: found_cols["學年度"] = selected_year_col
                if selected_semester_col: found_cols["學期"] = selected_semester_col
                if selected_course_name_col: found_cols["科目名稱"] = selected_course_name_col
                if selected_credit_col: found_cols["學分"] = selected_credit_col
                if selected_gpa_col: found_cols["GPA"] = selected_gpa_col
                st.experimental_rerun() # 重新運行以應用選擇

            if not all(col in found_cols for col in required_cols):
                st.error("仍然缺少必要的欄位，無法進行學分計算。請確保所有關鍵欄位都已正確指定。")
                st.stop() # 停止執行，直到欄位被正確選定
        
        # 重新命名 DataFrame 欄位以標準化
        renamed_df = extracted_df.rename(columns={v: k for k, v in found_cols.items()})

        # 過濾掉包含非成績數據的行 (如只有標題的行)
        # 篩選條件：'學分' 必須是數字，'GPA' 必須是有效的成績格式
        initial_filtered_df = renamed_df[
            pd.to_numeric(renamed_df['學分'], errors='coerce').notna() &
            renamed_df['GPA'].apply(is_gpa_valid)
        ].copy() # 使用 .copy() 避免 SettingWithCopyWarning

        # 確保學分是數值類型
        initial_filtered_df['學分'] = pd.to_numeric(initial_filtered_df['學分'], errors='coerce')

        # 過濾掉學分為0的科目 (通常是體育或軍訓)
        filtered_df = initial_filtered_df[initial_filtered_df['學分'] > 0].copy()

        # 過濾不及格科目 (通常為 D, E, F 等，或特定的低於60的數字)
        passed_grades_df = filtered_df[~filtered_df['GPA'].isin(['D', 'd', 'E', 'e', 'F', 'f'])].copy()

        # 提取不及格的科目
        failed_grades_df = filtered_df[filtered_df['GPA'].isin(['D', 'd', 'E', 'e', 'F', 'f'])].copy()

        # 計算通過的總學分
        total_credits = passed_grades_df['學分'].sum()
        st.success(f"✔️ 通過且計入總學分的總學分：**{total_credits}** 學分")

        # 顯示通過的科目列表
        st.subheader("通過且計入總學分的科目列表：")
        if not passed_grades_df.empty:
            display_cols = ['學年度', '學期', '科目名稱', '學分', 'GPA']
            final_display_cols = [col for col in display_cols if col in passed_grades_df.columns]
            st.dataframe(passed_grades_df[final_display_cols], height=300, use_container_width=True)
            st.info("這些科目已計入總學分。")
            calculated_courses = passed_grades_df[final_display_cols].to_dict('records')
        else:
            st.warning("沒有找到通過且計入總學分的科目。")
            calculated_courses = []

        # 顯示不及格科目列表 (如果有)
        st.subheader("未計入總學分的不及格科目列表：")
        if not failed_grades_df.empty:
            display_failed_cols = ['學年度', '學期', '科目名稱', '學分', 'GPA']
            final_display_failed_cols = [col for col in display_failed_cols if col in failed_grades_df.columns]
            st.dataframe(failed_grades_df[final_display_failed_cols], height=200, use_container_width=True)
            st.info("這些科目因成績不及格 ('D', 'E', 'F' 等) 而未計入總學分。") # 更新訊息
            failed_courses = failed_grades_df[final_display_failed_cols].to_dict('records')
        else:
            st.info("沒有找到不及格的科目。")
            failed_courses = []

        # 提供下載選項 
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
        st.warning("未從 PDF 中提取到任何表格數據。請檢查 PDF 內容或嘗試其他格式。")