import base64
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def _convert_to_pdf(docx_path, pdf_path):
    try:
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                os.path.dirname(pdf_path),
                docx_path,
            ],
            capture_output=True,
            timeout=60,
        )
        generated = os.path.join(
            os.path.dirname(pdf_path),
            os.path.splitext(os.path.basename(docx_path))[0] + ".pdf",
        )
        if os.path.isfile(generated) and generated != pdf_path:
            os.rename(generated, pdf_path)
    except Exception as exc:
        logger.warning("Failed to convert DOCX to PDF: %s", exc)


def _pdf_page_count(pdf_path):
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":")[1].strip())
    except Exception:
        pass
    return 0


def _pdf_page_to_png(pdf_path, page_num, output_path):
    try:
        subprocess.run(
            [
                "pdftoppm",
                "-f", str(page_num),
                "-l", str(page_num),
                "-r", "120",
                "-png",
                "-singlefile",
                pdf_path,
                os.path.splitext(output_path)[0],
            ],
            capture_output=True,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("Failed to convert PDF page %d to PNG: %s", page_num, exc)


def extract_page_images(docx_path, max_pages=3):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "document.pdf")
        _convert_to_pdf(docx_path, pdf_path)
        if not os.path.isfile(pdf_path):
            return []

        total_pages = _pdf_page_count(pdf_path)
        num_pages = min(max_pages, total_pages)
        if num_pages == 0:
            return []

        images = []
        for page_num in range(1, num_pages + 1):
            png_path = os.path.join(tmpdir, f"page-{page_num}.png")
            _pdf_page_to_png(pdf_path, page_num, png_path)
            if os.path.isfile(png_path):
                with open(png_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                images.append(b64)
                logger.info("Vision: page %d image %d bytes base64", page_num, len(b64))

        if images:
            logger.info("Vision: %d page images extracted", len(images))
        return images
