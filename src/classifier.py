import pandas as pd
import re

class LayoutClassifier:
    def __init__(self, df, thresholds):
        self.df = df
        self.thresh = thresholds
        # Definisi Pemicu State (Entry Points)
        self.state_triggers = {
            'KONSIDERAN': r"^Menimbang\s*:\s*[a-z]\.",
            'DASAR_HUKUM': r"^Mengingat\s*:\s*\d+\.",
            'DIKTUM': r"MEMUTUSKAN:",
            'PASAL': r"^Pasal\s+\d+",
            'PENUTUP': r"^(Ditetapkan|Diundangkan)\s+di",
            'LAMPIRAN': r"^LAMPIRAN$"
        }

    def apply_labels(self):
        labels = []
        current_state = "BODY_TEXT"
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            
            # 1. CEK PRIORITAS UTAMA (Label yang tidak memutus alur blok)
            if re.match(r"^-\s*\d+\s*-$", text):
                labels.append("HALAMAN")
                continue

            # 2. DETEKSI PERUBAHAN STATE (Titik Awal Baru)
            # Kita mencari apakah baris ini adalah "Entry Point" untuk blok selanjutnya
            new_state_found = False
            for state, pattern in self.state_triggers.items():
                if re.search(pattern, text, re.IGNORECASE):
                    # Jika ditemukan pemicu baru, ganti state aktif
                    current_state = state
                    new_state_found = True
                    # Jika Lampiran ditemukan, ini adalah terminal state (tidak bisa berubah lagi)
                    if state == 'LAMPIRAN':
                        break 
            
            # 3. DETEKSI BATAS AKHIR KHUSUS (Exit Points)
            if current_state == "PENUTUP" and re.match(r"^BERITA\s+NEGARA", text, re.IGNORECASE):
                current_state = "FOOTER_METADATA"

            # 4. LOGIKA SPASIAL (Hanya berlaku untuk BODY_TEXT)
            # Ini untuk menangani JUDUL_PERATURAN atau HEADER_LAMPIRAN yang ada sebelum blok hukum dimulai
            final_label = current_state
            if current_state == "BODY_TEXT":
                if row['center_score'] < self.thresh['center_limit'] and row['is_all_caps']:
                    final_label = "JUDUL_PERATURAN"
                elif self.thresh['left_ratio_min'] <= row['left_ratio'] <= self.thresh['left_ratio_max'] and row['is_all_caps']:
                    final_label = "HEADER_LAMPIRAN"

            labels.append(final_label)
        
        self.df['label'] = labels
        return self.df