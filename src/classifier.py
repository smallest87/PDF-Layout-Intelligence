import pandas as pd
import re
import yaml
import os

class LayoutClassifier:
    def __init__(self, df, thresholds, config_path="config/sistematika_config.yaml"):
        self.df = df
        self.thresh = thresholds
        
        # Memuat konfigurasi dari YAML
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.list_pemicu_judul = config_data.get('pemicu_judul', [])
                self.list_pemicu_pembentuk = config_data.get('pemicu_pembentuk_ppu', []) # Load keyword dinamis
        else:
            self.list_pemicu_judul = ["PERATURAN", "UNDANG-UNDANG"]
            self.list_pemicu_pembentuk = ["BUPATI", "WALIKOTA", "GUBERNUR"]

    def apply_sistematika(self):
        """Identifikasi sistematika dan unsur PEMBENTUK PPU secara dinamis."""
        sistematika_list = []
        unsur_list = []
        current_state = "BODY_TEXT"
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            
            # 1. Prioritas Navigasi (Halaman & Catchword)
            if re.match(r"^-\s*\d+\s*-$", text):
                sistematika_list.append("HALAMAN"); unsur_list.append(""); continue
            if re.search(r"\.\s*\.\s*\.$", text):
                sistematika_list.append("CATCHWORD"); unsur_list.append(""); continue

            # 2. Identifikasi Sistematika Utama
            is_match_judul = any(text_upper.startswith(p) for p in self.list_pemicu_judul)
            if current_state in ["BODY_TEXT", "JUDUL"]:
                if is_match_judul and row['center_score'] < self.thresh['center_limit'] and row['is_all_caps']:
                    current_state = "JUDUL"
            
            if "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                current_state = "PEMBUKAAN"
            elif re.search(r"^BAB\s+[IVXLCDM]+", text, re.IGNORECASE) or re.search(r"^Pasal\s+\d+", text, re.IGNORECASE):
                current_state = "BATANG TUBUH"
            elif "AGAR SETIAP ORANG MENGETAHUINYA" in text_upper:
                current_state = "PENUTUP"

            # 3. Identifikasi Unsur di dalam PEMBUKAAN
            final_unsur = ""
            if current_state == "PEMBUKAAN":
                # Unsur 1: FRASA RELIGIUS
                if "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                    final_unsur = "FRASA RELIGIUS"
                
                # Unsur 2: PEMBENTUK PPU (Berdasarkan keyword YAML + Spasial)
                else:
                    is_pembentuk = any(text_upper.startswith(k) for k in self.list_pemicu_pembentuk)
                    if is_pembentuk and row['is_all_caps'] and row['center_score'] < self.thresh['center_limit']:
                        final_unsur = "PEMBENTUK PPU"

            sistematika_list.append(current_state)
            unsur_list.append(final_unsur)

        self.df['sistematika'] = sistematika_list
        self.df['unsur'] = unsur_list
        return self.df