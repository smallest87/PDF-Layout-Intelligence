import sys
import fitz  # PyMuPDF
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QScrollArea
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QRect

class PDFOverlayViewer(QMainWindow):
    def __init__(self, pdf_path, coordinates):
        super().__init__()
        self.setWindowTitle("PDF Metadata Layer Viewer")
        self.pdf_path = pdf_path
        # 'coordinates' adalah list of dict berisi x0, x1, top, bottom dari CSV Anda
        self.coordinates = coordinates 
        
        self.scroll_area = QScrollArea()
        self.label = QLabel()
        self.scroll_area.setWidget(self.label)
        self.setCentralWidget(self.scroll_area)
        
        self.render_page(0) # Tampilkan halaman pertama

    def render_page(self, page_num):
        doc = fitz.open(self.pdf_path)
        page = doc.load_page(page_num)
        
        # Render halaman ke gambar (PixMap)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Zoom 2x agar tajam
        fmt = QImage.Format.Format_RGBA8888
        img = QImage(pix.samples, pix.width, pix.height, pix.pitched, fmt)
        pixmap = QPixmap.fromImage(img)

        # Skala koordinat: Hitung rasio antara ukuran PDF asli vs ukuran Render
        scale_x = pix.width / page.rect.width
        scale_y = pix.height / page.rect.height

        # Gambar layer koordinat di atas pixmap
        painter = QPainter(pixmap)
        pen = QPen(QColor(255, 0, 0, 127)) # Warna merah transparan
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 0, 50)) # Fill kuning transparan

        for coord in self.coordinates:
            # Transformasi koordinat PDF ke koordinat layar
            x = int(float(coord['x0']) * scale_x)
            y = int(float(coord['top']) * scale_y)
            w = int((float(coord['x1']) - float(coord['x0'])) * scale_x)
            h = int((float(coord['bottom']) - float(coord['top'])) * scale_y)
            
            painter.drawRect(QRect(x, y, w, h))
        
        painter.end()
        self.label.setPixmap(pixmap)
        doc.close()

# Contoh Penggunaan:
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Dummy koordinat (seharusnya ambil dari 0. MASTER.csv Anda)
    sample_coords = [
        {'x0': 181.08, 'x1': 537.228, 'top': 788.92, 'bottom': 806.42}
    ]
    
    viewer = PDFOverlayViewer("dokumen.pdf", sample_coords)
    viewer.showMaximized()
    sys.exit(app.exec())