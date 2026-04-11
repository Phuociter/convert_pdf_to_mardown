import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

# Cấu hình trang
st.set_page_config(page_title="Math Question Analytics", layout="wide")

st.title("📊 Hệ thống Phân tích Dữ liệu Câu hỏi")
st.markdown("Trực quan hóa chỉ số từ bảng `questions` (Paper ID: 2)")

# 1. Kết nối cơ sở dữ liệu thật
@st.cache_data(ttl=60)
def load_data():
    # Tạo kết nối đến database
    engine = create_engine("mysql+pymysql://root:admin@127.0.0.1:3306/exam_db")
    
    query = """
        SELECT 
            question_number, 
            difficulty_level, 
            category, 
            correct_answer, 
            AI_answer,
            question_content,
            answer_explanation,
            prompt
        FROM questions 
        WHERE AI_answer IS NOT NULL
    """
    
    # Đọc dữ liệu vào DataFrame
    df = pd.read_sql(query, engine)
    
    # Làm sạch dữ liệu để biểu đồ không bị lỗi
    df['difficulty_level'] = df['difficulty_level'].fillna('Chưa phân loại')
    df['category'] = df['category'].fillna('Chưa phân loại')
    
    # Tính toán cột check đúng/sai
    df['is_correct'] = df['correct_answer'] == df['AI_answer']
    df['is_correct_str'] = df['is_correct'].map({True: 'Đúng', False: 'Sai'})
    return df

df = load_data()

# --- PHẦN TỔNG QUAN (METRICS) ---
col1, col2, col3, col4 = st.columns(4)

total_questions = len(df)
accuracy = (df['is_correct'].sum() / total_questions * 100) if total_questions > 0 else 0

col1.metric("Tổng số câu đã giải", total_questions)
col2.metric("Số câu Đại số", len(df[df['category'] == 'Đại số']))
col3.metric("Số câu Hình học", len(df[df['category'] == 'Hình học']))
col4.metric("Độ chính xác AI", f"{accuracy:.1f}%")

st.divider()

# --- PHẦN VISUALIZATION ---
row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader("🎯 Phân bố Độ khó")
    # Sắp xếp thứ tự độ khó cho biểu đồ
    diff_order = ['Dễ', 'Trung bình', 'Khó', 'Rất khó']
    fig_diff = px.histogram(df, x='difficulty_level', 
                            color='difficulty_level',
                            category_orders={"difficulty_level": diff_order},
                            color_discrete_map={'Dễ': '#2ecc71', 'Trung bình': '#f1c40f', 'Khó': '#e67e22', 'Rất khó': '#e74c3c'})
    st.plotly_chart(fig_diff, use_container_width=True)

with row2_col2:
    st.subheader("📚 Tỷ lệ Chủ đề (Category)")
    fig_cat = px.pie(df, names='category', hole=0.4, 
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_cat, use_container_width=True)

st.divider()

row3_col1, row3_col2 = st.columns([2, 1])

with row3_col1:
    st.subheader("🤖 So sánh Đáp án: Thực tế vs AI")
    # Tạo bảng heatmap hoặc so sánh
    comparison_df = df.groupby(['correct_answer', 'AI_answer']).size().reset_index(name='count')
    fig_comp = px.scatter(comparison_df, x='correct_answer', y='AI_answer', 
                          size='count', text='count',
                          labels={'correct_answer': 'Đáp án đúng', 'AI_answer': 'AI trả lời'},
                          title="Ma trận tương quan đáp án")
    st.plotly_chart(fig_comp, use_container_width=True)

with row3_col2:
    st.subheader("✅ Trạng thái trả lời")
    
    # Tính toán số lượng Đúng/Sai bằng pandas groupy để hỗ trợ pd 3.0+
    status_df = df.groupby('is_correct_str').size().reset_index(name='count')
    
    fig_status = px.bar(status_df, 
                        x='is_correct_str', y='count',
                        color='is_correct_str',
                        labels={'is_correct_str': 'Kết quả', 'count': 'Số lượng'},
                        color_discrete_map={'Đúng': '#2ecc71', 'Sai': '#e74c3c'})
    st.plotly_chart(fig_status, use_container_width=True)

# --- PHẦN CHI TIẾT ---
st.subheader("📋 Danh sách chi tiết câu hỏi")

# Cấu hình hiển thị bảng cho đẹp
st.dataframe(
    df, 
    use_container_width=True,
    column_config={
        "question_number": "Câu",
        "difficulty_level": "Độ khó",
        "category": "Chủ đề",
        "correct_answer": "Đáp án",
        "AI_answer": "AI trả lời",
        "is_correct_str": "Kết quả",
        "question_content": st.column_config.TextColumn("Nội dung câu hỏi", width="medium"),
        "answer_explanation": st.column_config.TextColumn("Giải thích của AI", width="large"),
        "prompt": st.column_config.TextColumn("Prompt gửi AI", width="small"),
        "is_correct": None # Ẩn cột boolean gốc
    },
    hide_index=True
)