import pandas as pd
import re
import yaml
import os

class LayoutClassifier:
    def __init__(self, df, thresholds, config_path="config/sistematika_config.yaml"):
        self.df = df
        self.thresh = thresholds
        
        # Memuat konfigurasi pemicu dari YAML
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                self.list_pemicu_judul = config_data.get('pemicu_judul', [])
                self.list_pemicu_pembentuk = config_data.get('pemicu_pembentuk_ppu', [])
        else:
            self.list_pemicu_judul = ["PERATURAN", "UNDANG-UNDANG", "BUPATI", "GUBERNUR"]
            self.list_pemicu_pembentuk = ["BUPATI", "WALIKOTA", "GUBERNUR", "PRESIDEN", "MENTERI"]

    def apply_sistematika(self):
        """Klasifikasi sistematika dengan Stop Signal dan deteksi Pasal yang diperketat."""
        sistematika_list = []
        unsur_list = []
        indices_to_keep = [] 
        
        current_state = "BODY_TEXT"
        is_konsiderans_active = is_dasar_hukum_active = is_diktum_active = False
        active_bt_unsur = "" 
        pending_unsur_title = None 
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            
            # ---------------------------------------------------------
            # 0. STOP SIGNALS (Penjelasan atau Lampiran)
            # ---------------------------------------------------------
            # Syarat: Strict Match (awal s/d akhir baris) DAN huruf kapital semua
            is_stop_pattern = re.match(r"^PENJELASAN(\s+ATAS)?$", text_upper) or \
                              re.match(r"^LAMPIRAN(\s+[IVXLCDM]+)?$", text_upper)
            
            if is_stop_pattern and row['is_all_caps']:
                break # Berhenti memproses halaman selanjutnya
            
            indices_to_keep.append(index)

            # ---------------------------------------------------------
            # 1. PRIORITAS NAVIGASI
            # ---------------------------------------------------------
            if re.match(r"^-\s*\d+\s*-$", text):
                sistematika_list.append("HALAMAN"); unsur_list.append(""); continue
            if re.match(r"^\d+$", text):
                sistematika_list.append("HALAMAN"); unsur_list.append(""); continue
            if re.search(r"\.\s*\.\s*\.$", text):
                sistematika_list.append("CATCHWORD"); unsur_list.append(""); continue

            # ---------------------------------------------------------
            # 2. TRANSISI SISTEMATIKA (Anchor)
            # ---------------------------------------------------------
            if current_state in ["BODY_TEXT", "JUDUL"]:
                if any(text_upper.startswith(p) for p in self.list_pemicu_judul) and \
                   row['center_score'] < self.thresh['center_limit'] and row['is_all_caps']:
                    current_state = "JUDUL"
            
            if "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                current_state = "PEMBUKAAN"
            
            # REVISI: Pasal harus mandiri tanpa teks referensi lain di belakangnya
            elif re.search(r"^BAB\s+[IVXLCDM]+", text, re.IGNORECASE) or re.search(r"^Pasal\s+\d+$", text, re.IGNORECASE):
                current_state = "BATANG TUBUH"
                is_konsiderans_active = is_dasar_hukum_active = is_diktum_active = False
            
            elif "AGAR SETIAP ORANG MENGETAHUINYA" in text_upper:
                current_state = "PENUTUP"
                is_konsiderans_active = is_dasar_hukum_active = is_diktum_active = False
                active_bt_unsur = "" 

            # ---------------------------------------------------------
            # 3. IDENTIFIKASI UNSUR
            # ---------------------------------------------------------
            final_unsur = ""
            if current_state == "PEMBUKAAN":
                if "MENIMBANG :" in text_upper: is_konsiderans_active = True
                elif "MENGINGAT :" in text_upper: is_dasar_hukum_active = True
                elif "DENGAN PERSETUJUAN BERSAMA" in text_upper: is_diktum_active = True

                if is_diktum_active: final_unsur = "DIKTUM"
                elif is_dasar_hukum_active: final_unsur = "DASAR HUKUM"
                elif is_konsiderans_active: final_unsur = "KONSIDERANS"
                elif "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper: final_unsur = "FRASA RELIGIUS"
                else:
                    if any(text_upper.startswith(k) for k in self.list_pemicu_pembentuk) and row['is_all_caps']:
                        final_unsur = "PEMBENTUK PPU"

            elif current_state == "BATANG TUBUH":
                if re.match(r"^(BAB\s+[IVXLCDM]+)$", text_upper) or \
                   re.match(r"^BAGIAN\s+KE[A-Z]+$", text_upper) or \
                   re.match(r"^PARAGRAF\s+\d+$", text_upper):
                    active_bt_unsur = text_upper; pending_unsur_title = active_bt_unsur; final_unsur = active_bt_unsur
                # REVISI: Strict Match PASAL
                elif re.match(r"^PASAL\s+\d+$", text_upper):
                    active_bt_unsur = text_upper; pending_unsur_title = None; final_unsur = active_bt_unsur
                else:
                    if pending_unsur_title and row['center_score'] < self.thresh['center_limit']:
                        final_unsur = pending_unsur_title; pending_unsur_title = None 
                    else: final_unsur = active_bt_unsur

            sistematika_list.append(current_state); unsur_list.append(final_unsur)

        # Hanya kembalikan data sebelum stop signal
        final_df = self.df.loc[indices_to_keep].copy()
        final_df['sistematika'] = sistematika_list
        final_df['unsur'] = unsur_list
        return final_df