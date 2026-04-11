import os
import re
import json
import glob
import pandas as pd
from sqlalchemy import create_engine, text

# --- Cấu hình ---
DB_CONFIG = "mysql+pymysql://root:admin@127.0.0.1:3306/exam_db"
engine = create_engine(DB_CONFIG)

def parse_questions_from_md(file_path, paper_id):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Chuẩn hóa nội dung: Xóa dấu cách thừa, chuẩn hóa dấu xuống dòng
        content = content.replace('\r\n', '\n')
        
        # 2. Regex mới: 
        # - Chấp nhận cả "Câu 1:" và "Câu 1."
        # - (?i) để không phân biệt chữ hoa chữ thường
        # - Dùng thực thể lười (.*?) để bắt nội dung
        q_pattern = r"(Câu\s+\d+[\s:.]+.*?)(?=Câu\s+\d+[\s:.]|$)"
        q_blocks = re.findall(q_pattern, content, re.DOTALL | re.IGNORECASE)
        
        parsed_questions = []
        for block in q_blocks:
            # Lấy số câu chính xác hơn
            num_match = re.search(r"Câu\s+(\d+)", block, re.IGNORECASE)
            if not num_match: continue
            q_num = int(num_match.group(1))

            # Tách nội dung và options (Xử lý trường hợp A. B. C. D. dính liền hoặc xuống dòng)
            # Regex này tìm chữ cái [A-D] đứng sau là dấu chấm và khoảng trắng
            parts = re.split(r"\n\s*([A-D]\.)|(?<=\s)([A-D]\.)", block)
            # Lọc bỏ các phần None do split sinh ra
            parts = [p for p in parts if p is not None]
            
            q_content_raw = parts[0]
            q_content = re.sub(r"Câu\s+\d+[\s:.]+", "", q_content_raw).strip()

            options_dict = {}
            # Logic bắt cặp label và value từ mảng parts
            # (Phần này cần cẩn thận vì split split theo 2 pattern)
            # Cách an toàn hơn để lấy Options:
            opt_pattern = r"([A-D])\.\s*(.*?)(?=[A-D]\.|$|\n\n)"
            options_matches = re.findall(opt_pattern, block, re.DOTALL)
            options_dict = {label.strip(): value.strip() for label, value in options_matches}

            images = re.findall(r"!\[.*?\]\((.*?)\)", block)

            parsed_questions.append({
                "paper_id": paper_id,
                "question_number": q_num,
                "question_content": q_content,
                "options": json.dumps(options_dict, ensure_ascii=False) if options_dict else None,
                "image_urls": json.dumps(images) if images else None,
                "correct_answer": None,
                "difficulty_level": None
            })
        return parsed_questions
    except Exception as e:
        print(f"  [!] Lỗi: {e}")
        return []

def main():
    # 1. Lấy thông tin các đề thi đã nạp trong DB để ánh xạ ID
    with engine.connect() as conn:
        query = text("SELECT id, code, academic_year FROM exam_papers")
        existing_papers = conn.execute(query).fetchall()
    
    # Tạo dictionary để tra cứu nhanh: {(năm, mã_đề): id}
    paper_map = {(str(p.academic_year), str(p.code)): p.id for p in existing_papers}

    # 2. Tìm tất cả file .md trong thư mục processed
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.abspath(os.path.join(current_dir, "../../data/processed"))
    file_list = glob.glob(os.path.join(base_path, "**/*.md"), recursive=True)

    print(f"--- Tìm thấy {len(file_list)} file Markdown. Bắt đầu xử lý... ---")

    total_inserted = 0
    for file_path in file_list:
        # Trích xuất Năm và Mã đề từ đường dẫn file để tra cứu paper_id
        # Cấu trúc: .../processed/2018/101/101.md
        path_parts = os.path.normpath(file_path).split(os.sep)
        year = path_parts[-3]
        code = path_parts[-2]

        paper_id = paper_map.get((year, code))

        if paper_id:
            print(f"[*] Đang xử lý Đề {code} - Năm {year} (ID: {paper_id})")
            questions = parse_questions_from_md(file_path, paper_id)
            
            if questions:
                df = pd.DataFrame(questions)
                try:
                    # Nạp vào DB, bỏ qua nếu trùng (do Unique Key)
                    df.to_sql('questions', con=engine, if_exists='append', index=False)
                    total_inserted += len(questions)
                    print(f"  [+] Đã nạp {len(questions)} câu.")
                except Exception as e:
                    print(f"  [!] Lỗi nạp DB cho đề {code}: Trùng dữ liệu hoặc lỗi SQL.")
        else:
            print(f"  [?] Bỏ qua: Đề {code}/{year} chưa có trong bảng exam_papers.")

    print(f"\n--- Hoàn tất! Tổng cộng đã nạp {total_inserted} câu hỏi vào MySQL. ---")

if __name__ == "__main__":
    main()