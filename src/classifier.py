import pandas as pd
import re

class LayoutClassifier:
    def __init__(self, df, thresholds):
        self.df = df
        self.thresh = thresholds

    def apply_labels(self):
        labels = []
        # Inisialisasi status state
        is_in_konsideran = False
        is_in_dasar_hukum = False
        is_in_diktum = False
        is_in_pasal = False
        is_in_penutup = False 
        is_in_lampiran = False # Terminal State
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            current_label = "BODY_TEXT"
            
            # 1. PRIORITAS TERTINGGI: NOMOR HALAMAN
            if re.match(r"^-\s*\d+\s*-$", text):
                labels.append("HALAMAN")
                continue
            
            # 2. TRIGGER TERMINAL: LAMPIRAN
            # Sekali menyala, state lain tidak akan bisa aktif lagi
            if re.match(r"^LAMPIRAN$", text, re.IGNORECASE):
                is_in_lampiran = True
                # Reset semua state lain
                is_in_konsideran = is_in_dasar_hukum = is_in_diktum = is_in_pasal = is_in_penutup = False
                current_label = "LAMPIRAN"

            # 3. TRIGGER STATE LAIN (Hanya jika belum masuk Lampiran)
            if not is_in_lampiran:
                # FOOTER METADATA
                if re.match(r"^BERITA\s+NEGARA\s+REPUBLIK\s+INDONESIA", text, re.IGNORECASE):
                    is_in_penutup = False
                    current_label = "FOOTER_METADATA"
                
                # PENUTUP
                elif re.match(r"^(Ditetapkan|Diundangkan)\s+di", text, re.IGNORECASE):
                    is_in_konsideran = is_in_dasar_hukum = is_in_diktum = is_in_pasal = False
                    is_in_penutup = True
                    current_label = "PENUTUP"
                
                # KONSIDERAN
                elif re.match(r"^Menimbang\s*:\s*[a-z]\.", text, re.IGNORECASE):
                    is_in_konsideran, is_in_dasar_hukum, is_in_diktum, is_in_pasal = True, False, False, False
                
                # DASAR HUKUM
                elif re.match(r"^Mengingat\s*:\s*\d+\.", text, re.IGNORECASE):
                    is_in_konsideran, is_in_dasar_hukum, is_in_diktum, is_in_pasal = False, True, False, False
                
                # DIKTUM
                elif "MEMUTUSKAN:" in text:
                    is_in_konsideran, is_in_dasar_hukum, is_in_diktum, is_in_pasal = False, False, True, False
                    current_label = "DIKTUM"
                
                # PASAL
                elif re.match(r"^Pasal\s+\d+", text, re.IGNORECASE):
                    is_in_konsideran, is_in_dasar_hukum, is_in_diktum, is_in_pasal = False, False, False, True
                    current_label = "PASAL"

            # 4. LOGIKA SPASIAL (Hanya jika belum masuk state khusus)
            if current_label == "BODY_TEXT":
                if not is_in_lampiran:
                    if row['center_score'] < self.thresh['center_limit'] and row['is_all_caps']:
                        if not (is_in_penutup or is_in_pasal):
                            current_label = "JUDUL_PERATURAN"
                    
                    elif self.thresh['left_ratio_min'] <= row['left_ratio'] <= self.thresh['left_ratio_max'] and row['is_all_caps']:
                        if not (is_in_diktum or is_in_pasal or is_in_penutup):
                            current_label = "HEADER_LAMPIRAN"

            # 5. PENETAPAN LABEL BERDASARKAN STATE
            if current_label == "BODY_TEXT":
                if is_in_lampiran:
                    current_label = "LAMPIRAN"
                elif is_in_penutup:
                    current_label = "PENUTUP"
                elif is_in_pasal:
                    current_label = "PASAL"
                elif is_in_konsideran:
                    current_label = "KONSIDERAN"
                elif is_in_dasar_hukum:
                    current_label = "DASAR_HUKUM"
                elif is_in_diktum:
                    current_label = "DIKTUM"
            
            labels.append(current_label)
        
        self.df['label'] = labels
        return self.df