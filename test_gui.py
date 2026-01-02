import sys
import pandas as pd
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QRect

class PDFTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audit Koordinat PPU - Dynamic Loader")
        self.pdf_path = None
        self.csv_path = None
        self.doc = None
        self.current_page = 0
        
        self.init_ui()

    def init_ui(self):
        # 1. Panel Kontrol Atas (Pilih File)
        top_layout = QHBoxLayout()
        self.btn_pdf = QPushButton("1. Pilih PDF")
        self.btn_pdf.clicked.connect(self.select_pdf)
        self.btn_csv = QPushButton("2. Pilih MASTER CSV")
        self.btn_csv.clicked.connect(self.select_csv)
        self.status_label = QLabel("Status: Silakan pilih berkas.")
        
        top_layout.addWidget(self.btn_pdf)
        top_layout.addWidget(self.btn_csv)
        top_layout.addWidget(self.status_label)

        # 2. Panel Navigasi Halaman
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("Sebelumnya")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_prev.setEnabled(False)
        
        self.page_label = QLabel("Halaman: - / -")
        
        self.btn_next = QPushButton("Selanjutnya")
        self.btn_next.clicked.connect(self.next_page)
        self.btn_next.setEnabled(False)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addStretch()

        # 3. Area Tampilan PDF
        self.scroll_area = QScrollArea()
        self.label = QLabel("Pratinjau akan muncul di sini.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.label)
        self.scroll_area.setWidgetResizable(True)

        # Main Layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.scroll_area)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def select_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka PDF", "", "PDF Files (*.pdf)")
        if path:
            self.pdf_path = path
            if self.doc: self.doc.close()
            self.doc = fitz.open(self.pdf_path)
            self.current_page = 0
            self.check_ready()

    def select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka CSV", "", "CSV Files (*.csv)")
        if path:
            self.csv_path = path
            self.check_ready()

    def check_ready(self):
        if self.doc and self.csv_path:
            self.status_label.setText("Status: Berkas Siap.")
            self.update_nav_buttons()
            self.render_overlay()
        elif self.doc:
            self.status_label.setText("Status: PDF Terpilih. Menunggu CSV...")
        elif self.csv_path:
            self.status_label.setText("Status: CSV Terpilih. Menunggu PDF...")

    def update_nav_buttons(self):
        if self.doc:
            total = len(self.doc)
            self.page_label.setText(f"Halaman: {self.current_page + 1} / {total}")
            self.btn_prev.setEnabled(self.current_page > 0)
            self.btn_next.setEnabled(self.current_page < total - 1)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_nav_buttons()
            self.render_overlay()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.update_nav_buttons()
            self.render_overlay()

    def render_overlay(self):
        try:
            # 1. Load Data CSV
            df = pd.read_csv(self.csv_path, sep=';')
            
            # --- PERBAIKAN 1: Filter Halaman (Sangat Penting!) ---
            # Pastikan CSV Anda memiliki kolom 'page' atau 'halaman'. 
            # Jika kolomnya bernama lain, sesuaikan 'page' di bawah ini.
            if 'page' in df.columns:
                df = df[df['page'] == self.current_page + 1] # PyMuPDF mulai dari 0, CSV biasanya dari 1
            
            page = self.doc.load_page(self.current_page)
            zoom = 2
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            pixmap = QPixmap.fromImage(img)

            painter = QPainter(pixmap)
            
            for _, row in df.iterrows():
                try:
                    # Bersihkan desimal
                    x0 = float(str(row['x0']).replace(',', '.'))
                    x1 = float(str(row['x1']).replace(',', '.'))
                    top = float(str(row['top']).replace(',', '.'))
                    bottom = float(str(row['bottom']).replace(',', '.'))

                    lx, ly = int(x0 * zoom), int(top * zoom)
                    lw, lh = int((x1 - x0) * zoom), int((bottom - top) * zoom)

                    text_content = str(row.get('text', '')).upper().strip()
                    unsur_label = str(row.get('unsur', '')).upper().strip()

                    # --- PERBAIKAN 2: Logika Pembeda Visual ---
                    if "PASAL" in unsur_label:
                        # Jika teks baris SAMA dengan label unsur, berarti ini adalah HEADER PASAL
                        if text_content == unsur_label:
                            painter.setPen(QPen(QColor(255, 0, 0), 2)) # Garis merah tebal
                            painter.setBrush(QColor(255, 0, 0, 40))     # Isi merah tipis
                        else:
                            # Ini adalah ISI/AYAT yang berafiliasi ke Pasal tersebut
                            painter.setPen(QPen(QColor(255, 0, 0, 100), 1, Qt.PenStyle.DashLine)) # Garis putus-putus
                            painter.setBrush(QColor(0, 0, 0, 0)) # Transparan total (tanpa isi)
                    
                    elif "BAB" in unsur_label or "BAGIAN" in unsur_label:
                        painter.setPen(QPen(QColor(0, 150, 0), 2))
                        painter.setBrush(QColor(0, 150, 0, 20))
                    else:
                        painter.setPen(QPen(QColor(0, 0, 255, 50), 1))
                        painter.setBrush(QColor(0, 0, 0, 0))

                    painter.drawRect(QRect(lx, ly, lw, lh))
                except: continue

            painter.end()
            self.label.setPixmap(pixmap)
            self.label.adjustSize()
        except Exception as e:
            self.status_label.setText(f"Error Render: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PDFTester()
    viewer.showMaximized()
    sys.exit(app.exec())