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
                self.list_pemicu_pembentuk = config_data.get('pemicu_pembentuk_ppu', [])
        else:
            # Fallback jika file config tidak ditemukan
            self.list_pemicu_judul = ["PERATURAN", "UNDANG-UNDANG", "BUPATI", "GUBERNUR"]
            self.list_pemicu_pembentuk = ["BUPATI", "WALIKOTA", "GUBERNUR", "PRESIDEN", "MENTERI"]

    def apply_sistematika(self):
        """Proses klasifikasi sistematika dan unsur secara komprehensif."""
        sistematika_list = []
        unsur_list = []
        
        # State Sistematika
        current_state = "BODY_TEXT"
        
        # State Internal Unsur (Toggles)
        is_konsiderans_active = False 
        is_dasar_hukum_active = False
        is_diktum_active = False
        
        # State Persistent untuk Batang Tubuh
        active_bt_unsur = "" 
        pending_unsur_title = None 
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            
            # ---------------------------------------------------------
            # 1. PRIORITAS NAVIGASI (Halaman & Catchword)
            # ---------------------------------------------------------
            if re.match(r"^-\s*\d+\s*-$", text):
                sistematika_list.append("HALAMAN")
                unsur_list.append("")
                continue

            if re.search(r"\.\s*\.\s*\.$", text):
                sistematika_list.append("CATCHWORD")
                unsur_list.append("")
                continue

            # ---------------------------------------------------------
            # 2. IDENTIFIKASI TRANSISI SISTEMATIKA (Anchor)
            # ---------------------------------------------------------
            
            # A. JUDUL (Terminal Start State)
            is_match_judul = any(text_upper.startswith(p) for p in self.list_pemicu_judul)
            if current_state in ["BODY_TEXT", "JUDUL"]:
                if is_match_judul and row['center_score'] < self.thresh['center_limit'] and row['is_all_caps']:
                    current_state = "JUDUL"
            
            # B. PEMBUKAAN
            if "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                current_state = "PEMBUKAAN"
            
            # C. BATANG TUBUH (Persistent Start)
            elif re.search(r"^BAB\s+[IVXLCDM]+", text, re.IGNORECASE) or re.search(r"^Pasal\s+\d+", text, re.IGNORECASE):
                current_state = "BATANG TUBUH"
                # Matikan semua toggle pembukaan saat masuk Batang Tubuh
                is_konsiderans_active = False; is_dasar_hukum_active = False; is_diktum_active = False
            
            # D. PENUTUP (Terminal End State)
            elif "AGAR SETIAP ORANG MENGETAHUINYA" in text_upper:
                current_state = "PENUTUP"
                is_konsiderans_active = False; is_dasar_hukum_active = False; is_diktum_active = False
                active_bt_unsur = "" 

            # E. LAMPIRAN
            elif text_upper == "LAMPIRAN":
                current_state = "LAMPIRAN"

            # ---------------------------------------------------------
            # 3. IDENTIFIKASI UNSUR (Berdasarkan Current Sistematika)
            # ---------------------------------------------------------
            final_unsur = ""
            
            # LOGIKA UNSUR: PEMBUKAAN
            if current_state == "PEMBUKAAN":
                if "MENIMBANG :" in text_upper:
                    is_konsiderans_active = True; is_dasar_hukum_active = False; is_diktum_active = False
                elif "MENGINGAT :" in text_upper:
                    is_konsiderans_active = False; is_dasar_hukum_active = True; is_diktum_active = False
                elif "DENGAN PERSETUJUAN BERSAMA" in text_upper:
                    is_konsiderans_active = False; is_dasar_hukum_active = False; is_diktum_active = True

                if is_diktum_active:
                    final_unsur = "DIKTUM"
                elif is_dasar_hukum_active:
                    final_unsur = "DASAR HUKUM"
                elif is_konsiderans_active:
                    final_unsur = "KONSIDERANS"
                elif "DENGAN RAHMAT TUHAN YANG MAHA ESA" in text_upper:
                    final_unsur = "FRASA RELIGIUS"
                else:
                    is_pembentuk = any(text_upper.startswith(k) for k in self.list_pemicu_pembentuk)
                    if is_pembentuk and row['is_all_caps'] and row['center_score'] < self.thresh['center_limit']:
                        final_unsur = "PEMBENTUK PPU"

            # LOGIKA UNSUR: BATANG TUBUH (Persistent Numbering)
            elif current_state == "BATANG TUBUH":
                # Deteksi BAB + Nomor
                match_bab = re.match(r"^(BAB\s+[IVXLCDM]+)$", text_upper)
                if match_bab:
                    active_bt_unsur = match_bab.group(1)
                    pending_unsur_title = active_bt_unsur
                    final_unsur = active_bt_unsur
                
                # Deteksi BAGIAN + Nomor
                elif re.match(r"^BAGIAN\s+KE[A-Z]+$", text_upper):
                    active_bt_unsur = text_upper
                    pending_unsur_title = active_bt_unsur
                    final_unsur = active_bt_unsur
                
                # Deteksi PARAGRAF + Nomor
                elif re.match(r"^PARAGRAF\s+\d+$", text_upper):
                    active_bt_unsur = text_upper
                    pending_unsur_title = active_bt_unsur
                    final_unsur = active_bt_unsur
                
                # Deteksi PASAL + Nomor
                elif re.match(r"^PASAL\s+\d+", text_upper):
                    match_pasal = re.search(r"(PASAL\s+\d+)", text_upper)
                    active_bt_unsur = match_pasal.group(1)
                    pending_unsur_title = None 
                    final_unsur = active_bt_unsur
                
                else:
                    # Penanganan Judul (Baris ke-2) atau Isi Pasal
                    if pending_unsur_title and row['center_score'] < self.thresh['center_limit']:
                        final_unsur = pending_unsur_title
                        pending_unsur_title = None 
                    else:
                        final_unsur = active_bt_unsur

            sistematika_list.append(current_state)
            unsur_list.append(final_unsur)

        # Finalisasi DataFrame
        self.df['sistematika'] = sistematika_list
        self.df['unsur'] = unsur_list
        return self.df