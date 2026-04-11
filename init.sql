CREATE DATABASE IF NOT EXISTS exam_db;
USE exam_db;

CREATE TABLE IF NOT EXISTS exam_papers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL,
    academic_year VARCHAR(20) DEFAULT '2025',
    total_questions INT DEFAULT 50,
    UNIQUE KEY `unique_paper_year` (code, academic_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paper_id INT,
    question_number INT,
    question_content TEXT NOT NULL,
    options JSON,
    correct_answer CHAR(1),
    prompt TEXT,
    answer_explanation TEXT,
    difficulty_level VARCHAR(50),
    image_urls JSON, -- Thêm để lưu link ảnh đồ thị/hình học
    FOREIGN KEY (paper_id) REFERENCES exam_papers(id) ON DELETE CASCADE,
    UNIQUE KEY `unique_question_per_paper` (paper_id, question_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;