import os
import re
import glob
import pandas as pd
from sqlalchemy import create_engine

# --- Cấu hình kết nối ---
DB_CONFIG = {
    "user": "root",
    "password": "admin",
    "host": "localhost",
    "port": "3306",
    "database": "exam_db"
}

def extract_exam_info(file_path):
    """Trích xuất thông tin mã đề và năm từ nội dung file Markdown."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Tìm năm thi
        year_match = re.search(r"NĂM\s+(\d{4})", content)
        exam_year = year_match.group(1) if year_match else "2025"

        # Tìm mã đề (Xử lý các lỗi chính tả MÃ/MÂ và ký tự lạ)
        code_pattern = r"M[ÃÂ]\s+ĐỀ(?:\s+THI)?[:\s-]*(\d{3})"
        code_match = re.search(code_pattern, content, re.IGNORECASE)
        paper_code = code_match.group(1) if code_match else "Unknown"

        return {
            "code": paper_code,
            "academic_year": exam_year,
            "total_questions": 50 # Giá trị mặc định cho đề THPT
        }
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def load_to_mysql(df):
    """Kết nối và nạp DataFrame vào MySQL."""
    try:
        # Tạo connection engine
        conn_str = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(conn_str)

        # Nạp dữ liệu vào bảng exam_papers
        # if_exists='append': Thêm dữ liệu mới vào bảng đã có
        df.to_sql('exam_papers', con=engine, if_exists='append', index=False)
        print("Successfully loaded data to MySQL.")
    except Exception as e:
        print(f"Failed to load data to DB: {e}")

def main():
    # Xác định đường dẫn file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.abspath(os.path.join(current_dir, "../../data/processed"))
    file_list = glob.glob(os.path.join(base_path, "**/*.md"), recursive=True)

    print(f"Found {len(file_list)} markdown files.")

    # Xử lý danh sách file
    extracted_data = []
    for file in file_list:
        info = extract_exam_info(file)
        if info and info["code"] != "Unknown":
            extracted_data.append(info)

    if not extracted_data:
        print("No valid data extracted. Exiting...")
        return

    # Chuyển thành DataFrame và xóa trùng lặp mã đề trước khi load
    df = pd.DataFrame(extracted_data)
    
    print(df)
    load_to_mysql(df)

if __name__ == "__main__":
    main()