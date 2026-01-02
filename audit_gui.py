import sys
import pandas as pd
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QRect

class AuditGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PPU Audit System - Editor & Delete Mode")
        self.pdf_path = None
        self.csv_path = None
        self.doc = None
        self.df = None
        self.current_page = 0
        self.selected_row_index = -1
        self._is_loading = False 
        
        self.init_ui()

    def init_ui(self):
        # 1. Panel Kontrol Atas
        top_layout = QHBoxLayout()
        self.btn_pdf = QPushButton("Load PDF")
        self.btn_pdf.clicked.connect(self.select_pdf)
        
        self.btn_csv = QPushButton("Load CSV")
        self.btn_csv.clicked.connect(self.select_csv)
        
        # Tombol Hapus Baris
        self.btn_delete = QPushButton("Delete Selected Row")
        self.btn_delete.setStyleSheet("background-color: #ff4d4d; color: white; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_selected_row)
        
        self.status_label = QLabel("Status: Ready")
        
        top_layout.addWidget(self.btn_pdf)
        top_layout.addWidget(self.btn_csv)
        top_layout.addWidget(self.btn_delete)
        top_layout.addStretch()
        top_layout.addWidget(self.status_label)

        # 2. Main Body
        self.main_h_layout = QHBoxLayout()

        # Sidebar Tabel
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Text", "Unsur", "Sistematika", "x0", "x1", "top", "bottom"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        self.table.currentCellChanged.connect(self.on_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)
        
        self.table.setFixedWidth(600)

        # Viewer PDF
        self.scroll_area = QScrollArea()
        self.pdf_label = QLabel("Load berkas...")
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setWidget(self.pdf_label)
        self.scroll_area.setWidgetResizable(True)

        self.main_h_layout.addWidget(self.table)
        self.main_h_layout.addWidget(self.scroll_area)

        container = QWidget()
        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addLayout(self.main_h_layout)
        container.setLayout(layout)
        self.setCentralWidget(container)

    # --- FUNGSI PENGHAPUSAN ---
    def delete_selected_row(self):
        """Menghapus baris terpilih dari tabel, DataFrame, dan CSV."""
        row = self.table.currentRow()
        
        if row < 0:
            QMessageBox.warning(self, "Peringatan", "Pilih baris yang ingin dihapus terlebih dahulu!")
            return
            
        # Konfirmasi penghapusan
        reply = QMessageBox.question(self, 'Konfirmasi Hapus', 
                                     f"Apakah Anda yakin ingin menghapus baris {row + 1}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self._is_loading = True # Kunci agar itemChanged tidak trigger
            
            # 1. Hapus dari DataFrame internal
            self.df = self.df.drop(self.df.index[row]).reset_index(drop=True)
            
            # 2. Hapus dari UI Table
            self.table.removeRow(row)
            
            # 3. Simpan perubahan ke CSV
            self.df.to_csv(self.csv_path, index=False, sep=';')
            
            self._is_loading = False
            self.status_label.setText(f"Status: Baris {row + 1} berhasil dihapus.")
            
            # 4. Refresh Preview
            self.render_overlay()

    # --- LOGIKA PENDUKUNG ---
    def select_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka PDF", "", "PDF Files (*.pdf)")
        if path:
            self.pdf_path = path
            if self.doc: self.doc.close()
            self.doc = fitz.open(self.pdf_path)
            self.try_render()

    def select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka CSV", "", "CSV Files (*.csv)")
        if path:
            self.csv_path = path
            self.df = pd.read_csv(self.csv_path, sep=';')
            self.load_table_data()
            self.try_render()

    def load_table_data(self):
        self._is_loading = True
        self.table.setRowCount(len(self.df))
        cols = ["text", "unsur", "sistematika", "x0", "x1", "top", "bottom"]
        for i, row in self.df.iterrows():
            for j, col_name in enumerate(cols):
                self.table.setItem(i, j, QTableWidgetItem(str(row.get(col_name, ''))))
        self._is_loading = False

    def on_item_changed(self, item):
        if self._is_loading or self.df is None: return
        row, col = item.row(), item.column()
        col_names = ["text", "unsur", "sistematika", "x0", "x1", "top", "bottom"]
        self.df.at[row, col_names[col]] = item.text()
        self.df.to_csv(self.csv_path, index=False, sep=';')
        self.render_overlay()

    def on_selection_changed(self, current_row, current_col, prev_row, prev_col):
        if current_row < 0 or self.df is None: return
        self.selected_row_index = current_row
        if 'page' in self.df.columns:
            self.current_page = int(self.df.iloc[current_row]['page']) - 1
        self.render_overlay()

    def try_render(self):
        if self.doc and self.csv_path: self.render_overlay()

    def render_overlay(self):
        try:
            page = self.doc.load_page(self.current_page)
            zoom = (self.scroll_area.width() - 50) / page.rect.width
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, 
                         QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img)

            painter = QPainter(pixmap)
            page_filter = self.current_page + 1
            mask = self.df['page'] == page_filter if 'page' in self.df.columns else [True]*len(self.df)
            visible_df = self.df[mask]

            target_x, target_y = 0, 0
            for idx, row in visible_df.iterrows():
                try:
                    x0, x1 = float(str(row['x0']).replace(',','.')), float(str(row['x1']).replace(',','.'))
                    top, bottom = float(str(row['top']).replace(',','.')), float(str(row['bottom']).replace(',','.'))
                    rx, ry = int(x0 * zoom), int(top * zoom)
                    if idx == self.selected_row_index:
                        painter.setPen(QPen(QColor(255, 255, 0), 3))
                        painter.setBrush(QColor(255, 255, 0, 100))
                        target_x, target_y = rx, ry
                    else:
                        painter.setPen(QPen(QColor(0, 0, 255, 40), 1))
                        painter.setBrush(QColor(0, 0, 0, 0))
                    painter.drawRect(QRect(rx, ry, int((x1 - x0) * zoom), int((bottom - top) * zoom)))
                except: continue
            painter.end()
            self.pdf_label.setPixmap(pixmap)
            if target_y > 0: self.scroll_area.ensureVisible(target_x, target_y, 50, 300)
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuditGUI()
    window.showMaximized()
    sys.exit(app.exec())