import PyPDF2

def slice_pdf(input_path, output_path, start_page, end_page):
    """
    Cắt file PDF từ trang start_page đến end_page (vị trí bắt đầu từ 1).
    """
    with open(input_path, "rb") as infile:
        reader = PyPDF2.PdfReader(infile)
        writer = PyPDF2.PdfWriter()

        # Lưu ý: PyPDF2 đếm trang từ 0, nên cần trừ đi 1
        for i in range(start_page - 1, end_page):
            if i < len(reader.pages):
                writer.add_page(reader.pages[i])

        with open(output_path, "wb") as outfile:
            writer.write(outfile)

# Ví dụ: Lấy từ trang 1 đến trang 5
slice_pdf("./data/raw/2021/2021.pdf", "./data/slice_file/2021/101.pdf", 1, 6)

print("Đã cắt file thành công!")