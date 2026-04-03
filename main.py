import uuid
import shutil
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict 
from marker.output import save_output

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

logger.info("⏳ Đang khởi tạo AI Engine (Marker v1.10.2)...")
try:
    model_artifacts = create_model_dict()  # ← sửa dòng gọi hàm
    converter = PdfConverter(artifact_dict=model_artifacts)
    logger.info("✅ AI Engine đã sẵn sàng!")
except Exception as e:
    logger.error(f"❌ Lỗi khởi tạo: {e}")
    converter = None


@app.get("/")
async def read_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"message": "Thiếu file static/index.html"})


@app.post("/convert")
async def convert_pdf(file: UploadFile = File(...)):
    if not converter:
        return JSONResponse(status_code=500, content={"status": "error", "message": "AI Engine chưa sẵn sàng"})

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Chỉ chấp nhận file PDF"})

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        return JSONResponse(status_code=413, content={"status": "error", "message": "File quá lớn (tối đa 50MB)"})

    original_stem = Path(file.filename).stem or "output"
    safe_stem = "".join(c for c in original_stem if c.isalnum() or c in "-_") or "output"
    temp_path = BASE_DIR / f"temp_{uuid.uuid4().hex}_{safe_stem}.pdf"
    temp_path.write_bytes(contents)

    try:
        logger.info(f"🚀 Đang xử lý: {file.filename}")

        # ✅ Gọi trực tiếp, KHÔNG dùng asyncio.to_thread
        rendered = converter(str(temp_path))

        subfolder = safe_stem
        save_output(rendered, str(OUTPUT_DIR), subfolder)

        return {
            "status": "success",
            "file": f"{subfolder}.md",
            "downloadUrl": f"/download/{subfolder}/{subfolder}.md",
        }
    except Exception as e:
        logger.error(f"❌ Lỗi xử lý: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        if temp_path.exists():
            temp_path.unlink()


@app.get("/download/{subfolder}/{filename}")
async def download(subfolder: str, filename: str):
    file_path = (OUTPUT_DIR / subfolder / filename).resolve()

    # Chống path traversal
    if not str(file_path).startswith(str(OUTPUT_DIR.resolve())):
        return JSONResponse(status_code=400, content={"message": "Đường dẫn không hợp lệ"})

    if file_path.exists():
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"message": "File không tìm thấy"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)