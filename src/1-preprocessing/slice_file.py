import PyPDF2

def slice_pdf(input_path, output_path, start_page, end_page):
    """
    Cắt file PDF từ trang start_page đến end_page (vị trí bắt đầu từ 1).
    """
    with open(input_path, "rb") as infile:
        reader = PyPDF2.PdfReader(infile)
        writer = PyPDF2.PdfWriter()

        for i in range(start_page - 1, end_page):
            if i < len(reader.pages):
                writer.add_page(reader.pages[i])

        with open(output_path, "wb") as outfile:
            writer.write(outfile)

slice_pdf("./data/raw/2018/2018.pdf", "./data/slice_file/2018/101.pdf", 1, 6)
slice_pdf("./data/raw/2018/2018.pdf", "./data/slice_file/2018/102.pdf", 6, 11)
slice_pdf("./data/raw/2018/2018.pdf", "./data/slice_file/2018/103.pdf", 11, 16)
slice_pdf("./data/raw/2018/2018.pdf", "./data/slice_file/2018/104.pdf", 16, 21)

slice_pdf("./data/raw/2019/2019.pdf", "./data/slice_file/2019/101.pdf", 1, 6)
slice_pdf("./data/raw/2019/2019.pdf", "./data/slice_file/2019/102.pdf", 6, 11)
slice_pdf("./data/raw/2019/2019.pdf", "./data/slice_file/2019/103.pdf", 11, 16)
slice_pdf("./data/raw/2019/2019.pdf", "./data/slice_file/2019/104.pdf", 16, 21)

print("Đã cắt file thành công!")