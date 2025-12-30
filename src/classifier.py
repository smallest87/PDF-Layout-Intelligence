import pandas as pd
import re
import yaml
import os

class LayoutClassifier:
    def __init__(self, df, thresholds, config_path="config/sistematika_config.yaml"):
        self.df = df
        self.thresh = thresholds
        
        # Memuat daftar pemicu JUDUL dari YAML
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.list_pemicu_judul = config_data.get('pemicu_judul', [])
        else:
            self.list_pemicu_judul = ["PERATURAN", "UNDANG-UNDANG", "KEPUTUSAN", "INSTRUKSI", "QANUN"]

    def apply_sistematika(self):
        """Pelabelan sistematika dengan deteksi HALAMAN dan CATCHWORD."""
        sistematika_list = []
        unsur_list = []
        
        current_state = "BODY_TEXT"
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            
            # 1. PRIORITAS UTAMA: HALAMAN
            if re.match(r"^-\s*\d+\s*-$", text):
                sistematika_list.append("HALAMAN")
                unsur_list.append("")
                continue

            # 2. PRIORITAS UTAMA: CATCHWORD (Teks dengan akhiran tiga titik)
            # Pattern mendeteksi teks yang diakhiri dengan . . . atau ...
            if re.search(r"\.\s*\.\s*\.$", text):
                sistematika_list.append("CATCHWORD")
                unsur_list.append("")
                continue

            # 3. IDENTIFIKASI TRANSISI SISTEMATIKA (Start-to-Stop)
            
            # Titik Awal JUDUL
            is_match_judul = any(text_upper.startswith(pemicu) for pemicu in self.list_pemicu_judul)
            if is_match_judul and row['center_score'] < self.thresh['center_limit']:
                current_state = "JUDUL"
            
            # Titik Awal PEMBUKAAN
            elif "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                current_state = "PEMBUKAAN"
            
            # Titik Awal BATANG TUBUH
            elif re.search(r"^Pasal\s+\d+", text, re.IGNORECASE):
                current_state = "BATANG TUBUH"
            
            # Titik Awal PENUTUP
            elif "AGAR SETIAP ORANG MENGETAHUINYA" in text_upper:
                current_state = "PENUTUP"
            
            # Titik Awal LAMPIRAN
            elif text_upper == "LAMPIRAN":
                current_state = "LAMPIRAN"

            # 4. PENUGASAN NILAI
            sistematika_list.append(current_state)
            unsur_list.append("") 

        self.df['sistematika'] = sistematika_list
        self.df['unsur'] = unsur_list
        return self.df