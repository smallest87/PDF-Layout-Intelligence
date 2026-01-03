import sys
import csv
import json
import os
import pandas as pd
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QScrollArea, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QGridLayout, QInputDialog, QCheckBox)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QRect

# --- WIDGET RULER DENGAN OFFSET DINAMIS ---
class RulerWidget(QWidget):
    def __init__(self, orientation, parent_gui):
        super().__init__()
        self.orientation = orientation
        self.parent_gui = parent_gui
        self.zoom = 1.0
        self.offset = 0
        self.setMouseTracking(True)

    def update_ruler(self, zoom, offset):
        """Update skala penggaris berdasarkan zoom dan posisi scroll."""
        self.zoom = zoom
        self.offset = offset
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setFont(QFont("Arial", 7))
        
        is_horz = self.orientation == Qt.Orientation.Horizontal
        start_val = int(self.offset / self.zoom)
        end_val = start_val + int((self.width() if is_horz else self.height()) / self.zoom) + 5
        
        for i in range(start_val, end_val):
            if i % 10 == 0:
                pos = int(i * self.zoom) - self.offset
                if i % 50 == 0:
                    if is_horz:
                        painter.drawLine(pos, 0, pos, 20)
                        painter.drawText(pos + 2, 10, str(i))
                    else:
                        painter.drawLine(0, pos, 20, pos)
                        painter.drawText(2, pos - 2, str(i))
                else:
                    if is_horz: painter.drawLine(pos, 15, pos, 20)
                    else: painter.drawLine(15, pos, 20, pos)

    def mousePressEvent(self, event):
        """Memicu pembuatan guide saat klik/drag dari ruler."""
        g_type = 'v' if self.orientation == Qt.Orientation.Vertical else 'h'
        click_pos = event.pos().y() if g_type == 'h' else event.pos().x()
        pos_pts = (click_pos + self.offset) / self.zoom
        self.parent_gui.start_new_guide(g_type, pos_pts)

class AuditGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PPU Audit System - Professional Suite")
        self.pdf_path, self.csv_path = None, None
        self.doc, self.df = None, None
        self.current_page = 0
        self.selected_row_index = -1
        self.zoom_factor = 1.3
        self._is_loading = False
        self._is_paginating = False
        self.show_ocr_layer = True # Status Layer 5 (Teks Merah)
        
        # Persistence Guides
        self.v_guides = [] 
        self.h_guides_dict = {} 
        self.active_drag = None 

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. Top Bar
        top_bar = QHBoxLayout()
        self.btn_pdf = QPushButton("Load PDF")
        self.btn_pdf.clicked.connect(self.select_pdf)
        self.btn_csv = QPushButton("Load CSV")
        self.btn_csv.clicked.connect(self.select_csv)
        self.status_label = QLabel("Status: Ready")
        top_bar.addWidget(self.btn_pdf)
        top_bar.addWidget(self.btn_csv)
        top_bar.addStretch()
        top_bar.addWidget(self.status_label)
        main_layout.addLayout(top_bar)

        # 2. Body Layout
        body_layout = QHBoxLayout()
        
        # Sidebar Tabel
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["text", "unsur", "sistematika", "x0", "x1", "top", "bottom"])
        self.table.setFixedWidth(450)
        self.table.currentCellChanged.connect(self.on_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)
        body_layout.addWidget(self.table)

        # PDF Panel (Rulers + Preview + Nav Controls)
        pdf_panel = QVBoxLayout()
        
        pdf_grid = QGridLayout()
        self.h_ruler = RulerWidget(Qt.Orientation.Horizontal, self)
        self.v_ruler = RulerWidget(Qt.Orientation.Vertical, self)
        self.h_ruler.setFixedHeight(25)
        self.v_ruler.setFixedWidth(25)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.sync_rulers)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.sync_rulers)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.handle_scroll_pagination)

        self.pdf_container = QWidget()
        self.pdf_cont_layout = QVBoxLayout(self.pdf_container)
        self.pdf_cont_layout.setContentsMargins(0, 0, 0, 0)
        self.pdf_label = QLabel("Preview")
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.pdf_label.setMouseTracking(True)
        self.pdf_label.mousePressEvent = self.on_pdf_mouse_press
        self.pdf_label.mouseMoveEvent = self.on_pdf_mouse_move
        self.pdf_label.mouseReleaseEvent = self.on_pdf_mouse_release
        self.pdf_label.mouseDoubleClickEvent = self.on_pdf_mouse_double_click
        
        self.pdf_cont_layout.addWidget(self.pdf_label)
        self.scroll_area.setWidget(self.pdf_container)

        pdf_grid.addWidget(QWidget(), 0, 0)
        pdf_grid.addWidget(self.h_ruler, 0, 1)
        pdf_grid.addWidget(self.v_ruler, 1, 0)
        pdf_grid.addWidget(self.scroll_area, 1, 1)
        pdf_panel.addLayout(pdf_grid)

        # Panel Navigasi & Toggle di Bawah Preview
        self.nav_control = QHBoxLayout()
        self.check_ocr = QCheckBox("Show OCR Text Layer")
        self.check_ocr.setChecked(True)
        self.check_ocr.stateChanged.connect(self.toggle_ocr_layer)
        
        self.nav_control.addWidget(self.check_ocr)
        self.nav_control.addSpacing(30)
        
        nav_btns = [
            ("Zoom In (+)", self.zoom_in), ("Zoom Out (-)", self.zoom_out),
            ("Fit Page", self.zoom_fit), ("Prev Page", self.prev_page),
            ("Next Page", self.next_page), ("Delete Row", self.delete_selected_row)
        ]
        for text, func in nav_btns:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.nav_control.addWidget(btn)
        
        self.nav_control.addStretch()
        pdf_panel.addLayout(self.nav_control)
        
        container_right = QWidget()
        container_right.setLayout(pdf_panel)
        body_layout.addWidget(container_right)
        main_layout.addLayout(body_layout)

    # --- LOGIKA TOGGLE & SYNC ---
    def toggle_ocr_layer(self, state):
        self.show_ocr_layer = (state == Qt.CheckState.Checked.value)
        self.render_overlay()

    def sync_table_to_page(self):
        """Otomatis pindah ke baris pertama halaman di tabel."""
        if self.df is None or self._is_loading: return
        target_pg = self.current_page + 1
        matches = self.df[self.df['page'] == target_pg].index
        if not matches.empty:
            self._is_loading = True
            self.table.setCurrentCell(matches[0], 0)
            self.selected_row_index = matches[0]
            self._is_loading = False

    def handle_scroll_pagination(self, value):
        """Trigger ganti halaman saat scroll mentok."""
        if not self.doc or self._is_paginating: return
        v_bar = self.scroll_area.verticalScrollBar()
        if v_bar.maximum() > 0 and value >= v_bar.maximum():
            if self.current_page < len(self.doc) - 1:
                self._is_paginating = True
                self.current_page += 1
                self.render_overlay()
                self.sync_table_to_page()
                v_bar.setValue(0)
                self._is_paginating = False
        elif value <= 0 and self.current_page > 0:
            self._is_paginating = True
            self.current_page -= 1
            self.render_overlay()
            self.sync_table_to_page()
            v_bar.setValue(v_bar.maximum())
            self._is_paginating = False

    # --- GUIDES & PERSISTENCE ---
    def get_guides_path(self):
        return self.pdf_path + ".guides.json" if self.pdf_path else None

    def save_guides(self):
        path = self.get_guides_path()
        if path:
            with open(path, 'w') as f:
                json.dump({"v_guides": self.v_guides, "h_guides_dict": self.h_guides_dict}, f)

    def load_guides(self):
        path = self.get_guides_path()
        if path and os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.v_guides = data.get("v_guides", [])
                    raw_h = data.get("h_guides_dict", {})
                    self.h_guides_dict = {int(k): v for k, v in raw_h.items()}
            except: pass

    def on_pdf_mouse_double_click(self, event):
        """Input manual koordinat via double-click."""
        curr_h = self.h_guides_dict.get(self.current_page, [])
        for i, pts in enumerate(curr_h):
            if abs(event.pos().y() - (pts * self.zoom_factor)) < 15:
                self.show_edit_dialog('h', i, pts); return
        for i, pts in enumerate(self.v_guides):
            if abs(event.pos().x() - (pts * self.zoom_factor)) < 15:
                self.show_edit_dialog('v', i, pts); return

    def show_edit_dialog(self, g_type, index, current_val):
        label = "Posisi Y (Horizontal):" if g_type == 'h' else "Posisi X (Vertical):"
        val, ok = QInputDialog.getDouble(self, "Edit Koordinat", label, current_val, 0, 5000, 2)
        if ok:
            if g_type == 'h': self.h_guides_dict[self.current_page][index] = val
            else: self.v_guides[index] = val
            self.save_guides(); self.render_overlay()

    # --- RENDERER & SYNC ---
    def sync_rulers(self):
        self.h_ruler.update_ruler(self.zoom_factor, self.scroll_area.horizontalScrollBar().value())
        self.v_ruler.update_ruler(self.zoom_factor, self.scroll_area.verticalScrollBar().value())

    def render_overlay(self):
        if not self.doc: return
        try:
            page = self.doc.load_page(self.current_page)
            zoom = self.zoom_factor
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            # Format stride untuk fix pitched error
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            pixmap = QPixmap.fromImage(img)
            
            self.pdf_label.setFixedSize(pix.width, pix.height)
            self.pdf_container.setFixedSize(pix.width, pix.height)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            target_x, target_y = 0, 0
            if self.df is not None:
                mask = self.df['page'] == self.current_page + 1 if 'page' in self.df.columns else [True]*len(self.df)
                for idx, row in self.df[mask].iterrows():
                    try:
                        x0, x1 = float(str(row['x0']).replace(',','.')), float(str(row['x1']).replace(',','.'))
                        top, bottom = float(str(row['top']).replace(',','.')), float(str(row['bottom']).replace(',','.'))
                        rx, ry = int(x0*zoom), int(top*zoom)
                        # Render Box
                        if idx == self.selected_row_index:
                            painter.setPen(QPen(QColor(255, 255, 0), 2))
                            painter.setBrush(QColor(255, 255, 0, 80))
                            target_x, target_y = rx, ry
                        else:
                            painter.setPen(QPen(QColor(0, 0, 255, 50), 1))
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRect(QRect(rx, ry, int((x1-x0)*zoom), int((bottom-top)*zoom)))
                        
                        # Layer 5: Ghost Text
                        if self.show_ocr_layer:
                            painter.setPen(QPen(QColor(255, 0, 0, 150)))
                            painter.setFont(QFont("Arial", int(8 * zoom)))
                            painter.drawText(rx, ry, str(row['text']))
                    except: continue

            painter.setPen(QPen(QColor(0, 255, 255), 1, Qt.PenStyle.DashLine))
            for pts in self.v_guides:
                sx = int(pts * zoom)
                painter.drawLine(sx, 0, sx, pix.height)
            for pts in self.h_guides_dict.get(self.current_page, []):
                sy = int(pts * zoom)
                painter.drawLine(0, sy, pix.width, sy)
            painter.end()
            self.pdf_label.setPixmap(pixmap)
            self.sync_rulers()
            if target_y > 0 and not self._is_paginating: 
                self.scroll_area.ensureVisible(int(target_x), int(target_y), 50, 250)
            self.status_label.setText(f"Halaman: {self.current_page + 1}")
        except Exception as e: print(f"Render Error: {e}")

    # --- ZOOM & FILE HANDLING ---
    def zoom_in(self): self.zoom_factor += 0.2; self.render_overlay()
    def zoom_out(self): self.zoom_factor = max(0.2, self.zoom_factor - 0.2); self.render_overlay()
    def zoom_fit(self):
        if self.doc:
            page = self.doc.load_page(self.current_page)
            self.zoom_factor = (self.scroll_area.viewport().width() - 30) / page.rect.width
            self.render_overlay()

    def prev_page(self):
        if self.current_page > 0: 
            self.current_page -= 1
            self.render_overlay()
            self.sync_table_to_page()

    def next_page(self):
        if self.doc and self.current_page < len(self.doc)-1: 
            self.current_page += 1
            self.render_overlay()
            self.sync_table_to_page()

    def select_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka PDF", "", "PDF Files (*.pdf)")
        if path:
            self.pdf_path = path
            if self.doc: 
                self.doc.close() # Perbaikan: Pindahkan ke baris baru
            self.doc = fitz.open(self.pdf_path)
            self.load_guides()
            self.render_overlay()

    def select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Buka CSV", "", "CSV Files (*.csv)")
        if path:
            self.csv_path = path
            self.df = pd.read_csv(self.csv_path, sep=';')
            self.load_table_data()
            self.render_overlay()

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
        self.df.at[item.row(), ["text", "unsur", "sistematika", "x0", "x1", "top", "bottom"][item.column()]] = item.text()
        # Uniform Quoting
        self.df.to_csv(self.csv_path, index=False, sep=';', quoting=csv.QUOTE_ALL, quotechar='"')
        self.render_overlay()

    def delete_selected_row(self):
        row = self.table.currentRow()
        if row >= 0 and QMessageBox.question(self, 'Hapus', f"Hapus baris {row+1}?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._is_loading = True
            self.df = self.df.drop(self.df.index[row]).reset_index(drop=True)
            self.table.removeRow(row)
            self.df.to_csv(self.csv_path, index=False, sep=';', quoting=csv.QUOTE_ALL, quotechar='"')
            self._is_loading = False
            self.render_overlay()

    def on_selection_changed(self, curr_row, curr_col, prev_row, prev_col):
        if curr_row < 0 or self.df is None or self._is_loading: return
        self.selected_row_index = curr_row
        if 'page' in self.df.columns:
            new_pg = int(self.df.iloc[curr_row]['page']) - 1
            if new_pg != self.current_page: 
                self.current_page = new_pg
                self.render_overlay()

    # --- MOUSE DRAG GUIDES ---
    def start_new_guide(self, g_type, pos_pts):
        if g_type == 'v':
            self.v_guides.append(pos_pts)
            self.active_drag = {'type': 'v', 'index': len(self.v_guides)-1}
        else:
            if self.current_page not in self.h_guides_dict: 
                self.h_guides_dict[self.current_page] = []
            self.h_guides_dict[self.current_page].append(pos_pts)
            self.active_drag = {'type': 'h', 'index': len(self.h_guides_dict[self.current_page])-1}
        self.save_guides()
        self.render_overlay()

    def on_pdf_mouse_press(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        curr_h = self.h_guides_dict.get(self.current_page, [])
        for i, pts in enumerate(curr_h):
            if abs(event.pos().y() - (pts * self.zoom_factor)) < 15: 
                self.active_drag = {'type': 'h', 'index': i}
                return
        for i, pts in enumerate(self.v_guides):
            if abs(event.pos().x() - (pts * self.zoom_factor)) < 15: 
                self.active_drag = {'type': 'v', 'index': i}
                return

    def on_pdf_mouse_move(self, event):
        if self.active_drag:
            new_pts = (event.pos().y() if self.active_drag['type'] == 'h' else event.pos().x()) / self.zoom_factor
            if self.active_drag['type'] == 'h': 
                self.h_guides_dict[self.current_page][self.active_drag['index']] = new_pts
            else: 
                self.v_guides[self.active_drag['index']] = new_pts
            self.render_overlay()

    def on_pdf_mouse_release(self, event):
        if self.active_drag: self.save_guides()
        self.active_drag = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuditGUI()
    window.showMaximized()
    sys.exit(app.exec())