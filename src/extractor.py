import pdfplumber
from src.utils import parse_pages

class PDFExtractor:
    def __init__(self, file_path, page_cfg="all"):
        self.file_path = file_path
        self.page_cfg = page_cfg

    def extract_raw_data(self):
        raw_lines = []
        with pdfplumber.open(self.file_path) as pdf:
            total_pages = len(pdf.pages)
            target_pages = parse_pages(self.page_cfg, total_pages)
            
            for p_num in target_pages:
                # Index pdfplumber dimulai dari 0
                page = pdf.pages[p_num - 1]
                page_width = float(page.width)
                
                lines = page.extract_text_lines()
                for line in lines:
                    first_char = line["chars"][0]
                    raw_lines.append({
                        "page": p_num,
                        "text": line["text"].strip(),
                        "x0": float(line["x0"]),
                        "x1": float(line["x1"]),
                        "top": float(line["top"]),
                        "bottom": float(line["bottom"]),
                        "page_width": page_width,
                        "font_name": first_char["fontname"],
                        "font_size": float(first_char["size"])
                    })
        return raw_lines