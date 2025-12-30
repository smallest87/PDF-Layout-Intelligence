import pandas as pd
import re
import yaml
import os

class LayoutClassifier:
    def __init__(self, df, thresholds, config_path="config/sistematika_config.yaml"):
        self.df = df
        self.thresh = thresholds
        
        # Memuat daftar pemicu dari YAML
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.list_pemicu_judul = config_data.get('pemicu_judul', [])
        else:
            self.list_pemicu_judul = ["PERATURAN", "UNDANG-UNDANG", "BUPATI", "GUBERNUR"]

    def apply_sistematika(self):
        """Mewadahi keberagaman JUDUL sesuai UU 12/2011 termasuk Nama Jabatan."""
        sistematika_list = []
        unsur_list = []
        current_state = "BODY_TEXT"
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            
            # 1. Navigasi Halaman & Catchword
            if re.match(r"^-\s*\d+\s*-$", text):
                sistematika_list.append("HALAMAN"); unsur_list.append(""); continue
            if re.search(r"\.\s*\.\s*\.$", text):
                sistematika_list.append("CATCHWORD"); unsur_list.append(""); continue

            # 2. Identifikasi JUDUL (Mendukung Nama Jabatan sebagai baris pertama)
            # Mengecek apakah baris diawali oleh pemicu (BUPATI, MENTERI, dll)
            is_match_judul = any(text_upper.startswith(pemicu) for pemicu in self.list_pemicu_judul)
            
            # Syarat: Berada di awal (BODY_TEXT/JUDUL), Rata Tengah, dan All-Caps
            if current_state in ["BODY_TEXT", "JUDUL"]:
                if is_match_judul and row['center_score'] < self.thresh['center_limit'] and row['is_all_caps']:
                    current_state = "JUDUL"
            
            # 3. Transisi State
            if "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                current_state = "PEMBUKAAN"
            elif re.search(r"^BAB\s+[IVXLCDM]+", text, re.IGNORECASE) or re.search(r"^Pasal\s+\d+", text, re.IGNORECASE):
                current_state = "BATANG TUBUH"
            elif "AGAR SETIAP ORANG MENGETAHUINYA" in text_upper:
                current_state = "PENUTUP"

            sistematika_list.append(current_state)
            unsur_list.append("") 

        self.df['sistematika'] = sistematika_list
        self.df['unsur'] = unsur_list
        return self.df