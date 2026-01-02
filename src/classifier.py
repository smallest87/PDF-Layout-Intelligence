import pandas as pd
import re
import tomllib
import os

class LayoutClassifier:
    def __init__(self, df, thresholds, config_path="config/sistematika_config.toml"):
        """Inisialisasi klasifikasi dengan rujukan TOML yang humanis."""
        self.df = df
        self.thresh = thresholds
        
        if os.path.exists(config_path):
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
                self.list_p_pembentuk = config.get('rules', {}).get('pemicu_pembentuk_ppu', [])
                self.kw_sist = config.get('sistematika', {})
                self.kw_judul = config.get('unsur_judul', {})
                self.kw_pembukaan = config.get('unsur_pembukaan', {})
                self.kw_bt = config.get('unsur_batang_tubuh', {})
        else:
            raise FileNotFoundError(f"File konfigurasi {config_path} tidak ditemukan!")

    def classify_sistematika(self):
        """Fitur Opsi 6: Menentukan wilayah sistematika utama."""
        sistematika_list = []
        current_state = "JUDUL"
        found_closing_pembukaan = False
        opening_complete = False
        found_closing_bt = False
        bt_is_finished = False 

        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            
            if re.match(r"^-\s*\d+\s*-$", text) or re.match(r"^\d+$", text):
                sistematika_list.append("HALAMAN"); continue
            if re.search(r"\.\s*\.\s*\.$", text):
                sistematika_list.append("CATCHWORD"); continue

            if current_state == "JUDUL" and self.kw_sist.get('opening_trigger_PEMBUKAAN') in text_upper:
                current_state = "PEMBUKAAN"

            if current_state == "PEMBUKAAN":
                if not opening_complete:
                    if self.kw_sist.get('closing_trigger_PEMBUKAAN') in text_upper:
                        found_closing_pembukaan = True
                    if found_closing_pembukaan and text.endswith(".") and row.get('is_all_caps', False):
                        opening_complete = True
                
                for p_key in self.kw_bt.get('bt_priority', []):
                    if re.search(self.kw_bt.get(p_key, ""), text, re.IGNORECASE):
                        current_state = "BATANG TUBUH"
                        opening_complete = True; break

            if current_state == "BATANG TUBUH":
                if bt_is_finished: current_state = "PENUTUP"
                else:
                    trigger = self.kw_sist.get('closing_trigger_BATANG_TUBUH')
                    if trigger and re.search(trigger, text_upper): found_closing_bt = True
                    if found_closing_bt and text.endswith("."): bt_is_finished = True 

            if current_state == "PENUTUP" or self.kw_sist.get('opening_trigger_PENUTUP') in text_upper:
                current_state = "PENUTUP"

            sistematika_list.append(current_state)
        self.df['sistematika'] = sistematika_list
        return self.df

    def classify_unsur(self):
        """Fitur Opsi 7: Implementasi Sticky Pasal pada BATANG TUBUH."""
        if 'sistematika' not in self.df.columns:
            return self.df
            
        unsur_list = []
        # Flag kontrol sub-wilayah Pembukaan
        is_kon = is_dh = is_pd = is_dik = False
        
        # Variabel penahan identitas (Sticky Variables)
        active_pasal_label = ""
        active_header_label = "" # Untuk BUKU/BAB/BAGIAN
        
        kw_j = self.kw_judul
        kw_p = self.kw_pembukaan
        kw_bt = self.kw_bt

        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            text_upper = text.upper()
            sist = row['sistematika']
            final_unsur = ""

            # --- 1. BLOK JUDUL ---
            if sist == "JUDUL":
                if re.match(kw_j.get('sifat_berkas', ""), text_upper): final_unsur = "SIFAT BERKAS"
                elif any(k == text_upper for k in kw_j.get('jabatan_pembentuk', [])): final_unsur = "JABATAN PEMBENTUK"
                elif re.match(kw_j.get('yurisdiksi', ""), text_upper): final_unsur = "WILAYAH YURISDIKSI"
                elif re.match(kw_j.get('jenis_peraturan', ""), text_upper): final_unsur = "JENIS PERATURAN"
                elif re.match(kw_j.get('nomor_tahun', ""), text_upper): final_unsur = "NOMOR DAN TAHUN"
                elif re.match(kw_j.get('kata_penghubung', ""), text_upper): final_unsur = "KATA PENGHUBUNG"
                else: final_unsur = "NAMA PERATURAN"

            # --- 2. BLOK PEMBUKAAN ---
            elif sist == "PEMBUKAAN":
                if any(k in text_upper for k in kw_p.get('pola_konsiderans', [])): is_kon, is_dh, is_pd, is_dik = True, False, False, False
                elif any(k in text_upper for k in kw_p.get('pola_dasar_hukum', [])): is_kon, is_dh, is_pd, is_dik = False, True, False, False
                elif kw_p.get('pola_pra_diktum', "").upper() in text_upper: is_kon, is_dh, is_pd, is_dik = False, False, True, False
                elif kw_p.get('pola_diktum_memutuskan', "").upper() in text_upper or \
                     kw_p.get('pola_diktum_menetapkan', "").upper() in text_upper: is_kon, is_dh, is_pd, is_dik = False, False, False, True

                if is_dik: final_unsur = "DIKTUM"
                elif is_pd: final_unsur = "PERSETUJUAN BERSAMA"
                elif is_dh: final_unsur = "DASAR HUKUM"
                elif is_kon: final_unsur = "KONSIDERANS"
                elif self.kw_sist.get('opening_trigger_PEMBUKAAN') in text_upper: final_unsur = "FRASA RELIGIUS"
                else: final_unsur = "JABATAN PEMBENTUK"

            # --- 3. BLOK BATANG TUBUH (LOGIKA STICKY PASAL) ---
            elif sist == "BATANG TUBUH":
                # A. Cek apakah baris ini adalah Header Tinggi (BUKU, BAB, BAGIAN, PARAGRAF)
                is_high_header = False
                for key in ['buku', 'bab', 'bagian', 'paragraf']:
                    pattern = kw_bt.get(key)
                    if pattern and re.match(pattern, text_upper):
                        active_header_label = text_upper
                        active_pasal_label = "" # Reset pasal jika masuk Bab/Bagian baru
                        final_unsur = active_header_label
                        is_high_header = True
                        break
                
                # B. Cek apakah baris ini adalah PASAL
                if not is_high_header:
                    pasal_pattern = kw_bt.get('pasal')
                    if pasal_pattern and re.match(pasal_pattern, text_upper):
                        active_pasal_label = text_upper
                        final_unsur = active_pasal_label
                    else:
                        # C. Jika baris isi (Ayat/Rincian/Teks), gunakan identitas yang sedang aktif
                        # Prioritaskan Pasal, jika belum ada gunakan Header (Bab/Bagian)
                        final_unsur = active_pasal_label if active_pasal_label else active_header_label
            
            unsur_list.append(final_unsur)
            
        self.df['unsur'] = unsur_list
        return self.df

    def apply_sistematika(self):
        """Menjalankan full klasifikasi."""
        self.df = self.classify_sistematika()
        self.df = self.classify_unsur()
        return self.df