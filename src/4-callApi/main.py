import os
import json
import time
import logging
import re
from typing import Dict, List, Any
import pandas as pd

from google import genai
from google.genai import types # Thêm để xử lý ảnh
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- 1. CẤU HÌNH ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_CONFIG = "mysql+pymysql://root:admin@127.0.0.1:3306/exam_db"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class MathSolverAI:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})
        self.model_id = self._detect_model()

    def _detect_model(self) -> str:
        try:
            available_models = [m.name for m in self.client.models.list()]
            for m in available_models:
                if "gemini-2.5-flash" in m: return m
            return available_models[0]
        except: return "gemini-2.5-flash"

    def _create_prompt(self, content: str, options: str, has_images: bool) -> str:
        img_instruction = " (Có đính kèm ảnh minh họa, hãy phân tích kỹ hình vẽ)" if has_images else ""
        return f"""
        Bạn là chuyên gia giải đề Toán THPT Quốc gia. Giải câu hỏi sau và trả về JSON.{img_instruction}
        Câu hỏi: {content}
        Các lựa chọn: {options}

        YÊU CẦU ĐỊNH DẠNG JSON (BẮT BUỘC):
        {{
            "correct_answer": "A",
            "answer_explanation": "Giải chi tiết...",
            "difficulty_level": "Dễ/Trung bình/Khó",
            "category": "Hình học/Đại số"
        }}
        LƯU Ý QUAN TRỌNG: 
        1. Trong chuỗi JSON, tất cả dấu gạch chéo ngược (\\\\) của LaTeX PHẢI được viết thành kép (\\\\\\\\). 
           Ví dụ: "\\\\\\\\frac{{1}}{{2}}" thay vì "\\\\frac{{1}}{{2}}".
        2. Chỉ trả về duy nhất khối JSON, không thêm văn bản giải thích ngoài khối JSON.
        """

    def _robust_parse_json(self, text: str) -> Dict[str, Any]:
        # 1. Tìm trong block markdown ```json ... ```
        block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if block_match:
            json_str = block_match.group(1).strip()
        else:
            # 2. Tìm khối bắt đầu bằng {"correct_answer" hoặc {'correct_answer'
            start_match = re.search(r'\{\s*["\']correct_answer["\']', text)
            if start_match:
                start_idx = start_match.start()
                end_idx = text.rfind('}')
                json_str = text[start_idx:end_idx+1]
            else:
                # 3. Fallback (có rủi ro matched nhầm {} của LaTeX)
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if not json_match:
                    logging.error(f"AI Response contains no JSON block: {text}")
                    raise ValueError("Không tìm thấy khối JSON trong phản hồi.")
                json_str = json_match.group()

        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logging.warning(f"   [!] JSON ban đầu lỗi, đang cố gắng sửa... ({e})")
            
            # Thử sửa các dấu gạch chéo ngược LaTeX chưa được escape
            # Tìm các dấu \ không phải là escape hợp lệ trong JSON và thay bằng \\
            fixed_json = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', json_str)
            
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                # Nếu vẫn lỗi, thử thay thế dấu nháy đơn bằng dấu nháy kép cho các keys và values
                # Đây là trường hợp AI hay mắc lỗi 'key': 'value'
                try:
                    # Thay ' thành " xung quanh tên key: 'key': -> "key":
                    fixed_json = re.sub(r"\'(\w+)\'\s*:", r'"\1":', fixed_json)
                    # Thay ' thành " cho string values: : 'value' -> : "value"
                    fixed_json = re.sub(r":\s*\'(.*?)\'", r': "\1"', fixed_json)
                    return json.loads(fixed_json)
                except Exception:
                    logging.error(f"   [!] Không thể sửa JSON. Nội dung AI trả về:\n{text}")
                    raise

    def analyze(self, content: str, options: str, image_parts: List[Any] = None, max_retries: int = 3) -> Dict[str, Any]:
        prompt_text = self._create_prompt(content, options, bool(image_parts))
        
        contents = [prompt_text]
        if image_parts:
            contents.extend(image_parts)

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id, 
                    contents=contents
                )
                
                if response.text:
                    result = self._robust_parse_json(response.text)
                    result['prompt'] = prompt_text
                    return result
                return {"error": "Empty response"}

            except Exception as e:
                err_msg = str(e)
                # Kiểm tra lỗi giới hạn hạn ngạch (Rate Limit) hoặc model quá tải (503)
                is_retryable = any(x in err_msg for x in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "high demand"])
                
                if is_retryable:
                    # Mặc định chờ 60s, nếu là 503/UNAVAILABLE thì chờ lâu hơn
                    wait_time = 60
                    if "503" in err_msg or "UNAVAILABLE" in err_msg:
                        wait_time = 120 * (attempt + 1)
                    
                    # Cố gắng lấy thời gian chờ cụ thể từ thông báo lỗi nếu có
                    match = re.search(r"retry in (\d+\.?\d*)s", err_msg)
                    if match:
                        wait_time = float(match.group(1)) + 2
                    
                    logging.warning(f"   [!] AI đang bận hoặc lỗi ({err_msg}). Chờ {wait_time}s (Lần {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    return {"error": err_msg}
        
        return {"error": f"Thất bại sau {max_retries} lần thử lại do giới hạn API."}

class DatabaseManager:
    def __init__(self, connection_str: str):
        self.engine = create_engine(connection_str)

    def get_unsolved_questions(self, batch_size) -> List[Dict]:
        """Lấy những câu chưa có đáp án, kèm thông tin mã đề và ảnh."""
        query = text("""
            SELECT q.id, q.question_number, q.question_content, q.options, q.image_urls,
                   p.academic_year, p.code
            FROM questions q
            JOIN exam_papers p ON q.paper_id = p.id
            WHERE q.AI_answer IS NULL 
            LIMIT :limit
        """)
        # Ghi chú: Nếu muốn test 1 câu cụ thể, có thể đổi WHERE thành: WHERE q.id = 3
        with self.engine.connect() as conn:
            result = conn.execute(query, {"limit": batch_size})
            return [dict(row._mapping) for row in result.fetchall()]

    def update_question(self, q_id: int, data: Dict):
        """Đẩy kết quả AI vào DB."""
        sql = text("""
            UPDATE questions 
            SET AI_answer = :ans,
                prompt = :prm,
                answer_explanation = :expl,
                difficulty_level = :diff,
                category = :cat
            WHERE id = :qid
        """)
        try:
            with self.engine.begin() as conn:
                conn.execute(sql, {
                    "ans": data.get('correct_answer'),
                    "prm": data.get('prompt'),
                    "expl": data.get('answer_explanation'),
                    "diff": data.get('difficulty_level'),
                    "cat": data.get('category', 'Đại số'),
                    "qid": q_id
                })
            logging.info(f"   Successfully updated ID: {q_id}")
        except Exception as e:
            logging.error(f"   Failed to update ID {q_id}: {e}")

# --- MAIN FLOW ---
def main():
    db = DatabaseManager(DB_CONFIG)
    ai = MathSolverAI(GEMINI_API_KEY)

    logging.info("--- BẮT ĐẦU XỬ LÝ TOÀN BỘ BẢNG CÂU HỎI ---")

    while True:
        # Lấy một đợt 10 câu chưa giải
        questions = db.get_unsolved_questions(batch_size=10)
        
        if not questions:
            logging.info("--- CHÚC MỪNG! Tất cả câu hỏi đã được giải hoàn tất. ---")
            break

        logging.info(f"==> Đang xử lý đợt mới ({len(questions)} câu)...")

        for q in questions:
            logging.info(f"[*] Đang xử lý Câu {q['question_number']} (ID: {q['id']})")
            
            # Xử lý ảnh nếu đề bài có ảnh
            image_parts = []
            if q.get('image_urls'):
                try:
                    img_names = json.loads(q['image_urls'])
                    for img_name in img_names:
                        img_path = os.path.abspath(os.path.join(
                            os.path.dirname(__file__), 
                            "../../data/processed", 
                            str(q['academic_year']), 
                            str(q['code']), 
                            img_name
                        ))
                        
                        if os.path.exists(img_path):
                            with open(img_path, 'rb') as f:
                                img_data = f.read()
                            image_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))
                            logging.info(f"   + Đã đính kèm ảnh: {img_name}")
                        else:
                            logging.warning(f"   [!] File ảnh không tồn tại: {img_path}")
                except Exception as e:
                    logging.error(f"   [!] Lỗi khi xử lý danh sách ảnh: {e}")

            # Gọi AI
            analysis = ai.analyze(q['question_content'], q['options'], image_parts)
            
            if "error" not in analysis:
                db.update_question(q['id'], analysis)
            else:
                logging.error(f"   AI Error: {analysis['error']}")

            # Nghỉ nhẹ tránh rate limit
            time.sleep(10)

if __name__ == "__main__":
    main()