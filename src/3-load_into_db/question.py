import os
import re
import json
import glob
import pandas as pd
from sqlalchemy import create_engine, text

# --- Cấu hình ---
DB_CONFIG = "mysql+pymysql://root:admin@127.0.0.1:3306/exam_db"
engine = create_engine(DB_CONFIG)

def load_all_results(base_path):
    """Quét và đọc tất cả các file result.csv trong thư mục processed."""
    results_map = {}
    # Tìm tất cả file csv có tên result.csv (hoặc .cdv nếu có)
    csv_files = glob.glob(os.path.join(base_path, "**/result.csv"), recursive=True)
    csv_files += glob.glob(os.path.join(base_path, "**/result.cdv"), recursive=True)
    
    if not csv_files:
        print("  [?] Không tìm thấy bất kỳ file result.csv nào.")
        return results_map

    print(f"--- Đã tìm thấy {len(csv_files)} file CSV đáp án. ---")
    for csv_path in csv_files:
        try:
            # Lấy năm từ tên thư mục cha (ví dụ: data/processed/2018/result.csv)
            year = os.path.basename(os.path.dirname(csv_path))
            df_res = pd.read_csv(csv_path)
            
            # Chuẩn hóa tên cột
            df_res.columns = [c.lower().strip() for c in df_res.columns]
            
            # Lưu vào map với key là (năm, mã_đề, số_câu)
            for _, row in df_res.iterrows():
                key = (str(year), str(row['ma_de']), int(row['cau_hoi']))
                results_map[key] = str(row['dap_an']).strip()
        except Exception as e:
            print(f"  [!] Lỗi khi đọc file CSV {csv_path}: {e}")
            
    return results_map

def parse_questions_from_md(file_path, paper_id, year, code, results_map):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = content.replace('\r\n', '\n')
        
        # Regex bắt khối câu hỏi
        q_pattern = r"(Câu\s+\d+[\s:.]+.*?)(?=Câu\s+\d+[\s:.]|$)"
        q_blocks = re.findall(q_pattern, content, re.DOTALL | re.IGNORECASE)
        
        parsed_questions = []
        for block in q_blocks:
            num_match = re.search(r"Câu\s+(\d+)", block, re.IGNORECASE)
            if not num_match: continue
            q_num = int(num_match.group(1))

            # Tách đề bài và options
            opt_start_match = re.search(r"\n\s*A\.|(?<=\s)A\.", block)
            if opt_start_match:
                q_content_raw = block[:opt_start_match.start()]
                options_part = block[opt_start_match.start():]
            else:
                q_content_raw = block
                options_part = ""

            q_content = re.sub(r"^Câu\s+\d+[\s:.]+", "", q_content_raw).strip()

            options_dict = {}
            opt_pattern = r"([A-D])\.\s*(.*?)(?=[A-D]\.|$|\n\n)"
            options_matches = re.findall(opt_pattern, options_part, re.DOTALL)
            options_dict = {label.strip(): value.strip() for label, value in options_matches}

            images = re.findall(r"!\[.*?\]\((.*?)\)", block)

            # Tra cứu đáp án từ results_map
            correct_answer = results_map.get((str(year), str(code), q_num))

            parsed_questions.append({
                "paper_id": paper_id,
                "question_number": q_num,
                "question_content": q_content,
                "options": json.dumps(options_dict, ensure_ascii=False) if options_dict else None,
                "category": 'Đại số',
                "image_urls": json.dumps(images) if images else None,
                "correct_answer": correct_answer,
                "AI_answer": None,
                "difficulty_level": None
            })
        return parsed_questions
    except Exception as e:
        print(f"  [!] Lỗi: {e}")
        return []

def main():
    # 1. Khởi tạo đường dẫn và nạp đáp án trước
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.abspath(os.path.join(current_dir, "../../data/processed"))
    
    results_map = load_all_results(base_path)

    # 2. Lấy thông tin các đề thi đã nạp trong DB
    with engine.connect() as conn:
        query = text("SELECT id, code, academic_year FROM exam_papers")
        existing_papers = conn.execute(query).fetchall()
    
    paper_map = {(str(p.academic_year), str(p.code)): p.id for p in existing_papers}

    # 3. Tìm tất cả file .md
    file_list = glob.glob(os.path.join(base_path, "**/*.md"), recursive=True)

    print(f"--- Tìm thấy {len(file_list)} file Markdown. Bắt lời xử lý... ---")

    total_inserted = 0
    for file_path in file_list:
        path_parts = os.path.normpath(file_path).split(os.sep)
        year = path_parts[-3]
        code = path_parts[-2]

        paper_id = paper_map.get((year, code))

        if paper_id:
            print(f"[*] Đang xử lý Đề {code} - Năm {year} (ID: {paper_id})")
            questions = parse_questions_from_md(file_path, paper_id, year, code, results_map)
            
            if questions:
                df = pd.DataFrame(questions)
                try:
                    df.to_sql('questions', con=engine, if_exists='append', index=False)
                    total_inserted += len(questions)
                    print(f"  [+] Đã nạp {len(questions)} câu.")
                except Exception as e:
                    print(f"  [!] Lỗi nạp DB cho đề {code}: {e}")
        else:
            print(f"  [?] Bỏ qua: Đề {code}/{year} chưa có trong bảng exam_papers.")

    print(f"\n--- Hoàn tất! Tổng cộng đã nạp {total_inserted} câu hỏi vào MySQL. ---")

if __name__ == "__main__":
    main()