import pandas as pd
import re
import yaml
import os

class MasterAggregator:
    def __init__(self, master_df, config_meta="config/meta_mapping.yaml"):
        # Menggunakan df_master yang sudah dilabeli oleh LayoutClassifier
        self.df = master_df
        if os.path.exists(config_meta):
            with open(config_meta, 'r', encoding='utf-8') as f:
                self.META_MAPPING = yaml.safe_load(f)
        else:
            self.META_MAPPING = {}
        
        self.ALL_SAMPLES = []
        for v in self.META_MAPPING.values():
            self.ALL_SAMPLES.extend(v)

    def _clean_text(self, text_list):
        """Pembersihan spasi dan penggabungan teks dari list."""
        text = " ".join([str(t).strip() for t in text_list if str(t).strip()])
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_metadata(self, text):
        """Ekstraksi metadata dari teks JUDUL menggunakan regex."""
        detected_jenis = "TIDAK_TERDETEKSI"
        detected_kategori = "TIDAK_TERDETEKSI"
        
        # Matching Jenis & Kategori
        sorted_samples = sorted(self.ALL_SAMPLES, key=len, reverse=True)
        for s in sorted_samples:
            if s.lower() in text.lower():
                detected_jenis = s
                for k, v in self.META_MAPPING.items():
                    if s in v: detected_kategori = k; break
                break

        # Regex untuk Nomor, Tahun, dan Perihal
        no_match = re.search(r"NOMOR\s+([\d\w/.\-]+)", text, re.IGNORECASE)
        thn_match = re.search(r"TAHUN\s+(\d{4})", text, re.IGNORECASE)
        tentang_match = re.search(r"TENTANG\s+(.*)", text, re.IGNORECASE)

        return {
            "kategori": detected_kategori,
            "jenis": detected_jenis,
            "nomor": no_match.group(1) if no_match else "NONE",
            "tahun": thn_match.group(1) if thn_match else "NONE",
            "tentang": tentang_match.group(1).strip() if tentang_match else "NONE"
        }

    def _parse_points(self, df_unsur, pattern, prefix_to_strip=None):
        """Mengurai teks poin menjadi array of objects (nomor & isi)."""
        points = []
        current_point = None
        
        for _, row in df_unsur.iterrows():
            text = str(row['text']).strip()
            
            # Hapus prefix pemicu di baris awal (misal: 'Menimbang :')
            if prefix_to_strip:
                text = re.sub(rf"^{prefix_to_strip}\s*:\s*", "", text, flags=re.IGNORECASE)
            
            # Cek pola poin (a. atau 1.)
            match = re.match(pattern, text)
            if match:
                if current_point: points.append(current_point)
                current_point = {"nomor": match.group(1), "isi": match.group(2)}
            else:
                if current_point: current_point["isi"] += " " + text
        
        if current_point: points.append(current_point)
        
        # Pembersihan teks akhir untuk tiap poin
        for p in points:
            p['isi'] = re.sub(r'\s+', ' ', p['isi']).strip()
        return points

    def run_all(self):
        """Orkestrator untuk menghasilkan struktur A, B, C, D."""
        return {
            "A_JUDUL": self.process_judul(),
            "B_PEMBUKAAN": self.process_pembukaan(),
            "C_BATANG_TUBUH": self.process_batang_tubuh(),
            "D_PENUTUP": self.process_penutup()
        }

    def process_judul(self):
        """A. JUDUL: Konsolidasi baris sistematika JUDUL."""
        df_j = self.df[self.df['sistematika'] == "JUDUL"]
        full_text = self._clean_text(df_j['text'])
        return {
            "text": full_text,
            "metadata": self._extract_metadata(full_text)
        }

    def process_pembukaan(self):
        """B. PEMBUKAAN: Mengurai 5 unsur termasuk Konsiderans & Dasar Hukum nested."""
        df_p = self.df[self.df['sistematika'] == "PEMBUKAAN"]
        
        # Poin-poin Konsiderans (a. b. c.)
        kon_nested = self._parse_points(df_p[df_p['unsur'] == "KONSIDERANS"], 
                                       r"^([a-z])\.\s+(.*)", prefix_to_strip="Menimbang")
        
        # Poin-poin Dasar Hukum (1. 2. 3.)
        dh_nested = self._parse_points(df_p[df_p['unsur'] == "DASAR HUKUM"], 
                                      r"^(\d+)\.\s+(.*)", prefix_to_strip="Mengingat")
        
        return {
            "frasa_religius": self._clean_text(df_p[df_p['unsur'] == "FRASA RELIGIUS"]['text']),
            "jabatan_pembentuk": self._clean_text(df_p[df_p['unsur'] == "PEMBENTUK PPU"]['text']),
            "konsiderans": kon_nested,
            "dasar_hukum": dh_nested,
            "diktum": self._clean_text(df_p[df_p['unsur'] == "DIKTUM"]['text'])
        }

    def process_batang_tubuh(self):
        """C. BATANG TUBUH: Struktur Hierarki Nested (BAB > BAGIAN > PARAGRAF > PASAL)."""
        df_bt = self.df[self.df['sistematika'] == "BATANG TUBUH"]
        chapters = []
        
        curr_bab, curr_bagian, curr_paragraf, curr_pasal = None, None, None, None

        for _, row in df_bt.iterrows():
            u = str(row['unsur'])
            t = str(row['text'])
            
            # Hierarki 1: BAB
            if u.startswith("BAB"):
                if not curr_bab or curr_bab['bab'] != u:
                    curr_bab = {"bab": u, "judul": t, "kategori": "Materi Pokok", "sections": [], "articles": []}
                    chapters.append(curr_bab)
                    curr_bagian, curr_paragraf, curr_pasal = None, None, None
                else: curr_bab['judul'] += " " + t
            
            # Hierarki 2: BAGIAN
            elif u.startswith("BAGIAN"):
                if not curr_bagian or curr_bagian['bagian'] != u:
                    curr_bagian = {"bagian": u, "judul": t, "paragraphs": [], "articles": []}
                    if curr_bab: curr_bab['sections'].append(curr_bagian)
                    curr_paragraf, curr_pasal = None, None
                else: curr_bagian['judul'] += " " + t

            # Hierarki 3: PARAGRAF
            elif u.startswith("PARAGRAF"):
                if not curr_paragraf or curr_paragraf['paragraf'] != u:
                    curr_paragraf = {"paragraf": u, "judul": t, "articles": []}
                    if curr_bagian: curr_bagian['paragraphs'].append(curr_paragraf)
                    curr_pasal = None
                else: curr_paragraf['judul'] += " " + t

            # Hierarki 4: PASAL
            elif u.startswith("PASAL"):
                if not curr_pasal or curr_pasal['nomor'] != u:
                    curr_pasal = {"nomor": u, "isi": t}
                    # Masukkan ke level terdalam yang tersedia
                    if curr_paragraf: curr_paragraf['articles'].append(curr_pasal)
                    elif curr_bagian: curr_bagian['articles'].append(curr_pasal)
                    elif curr_bab: curr_bab['articles'].append(curr_pasal)
                else: curr_pasal['isi'] += " " + t

        # Pembersihan Teks & Penentuan Kategori BAB
        for c in chapters:
            c['judul'] = self._clean_text([c['judul']])
            if "KETENTUAN UMUM" in c['judul'].upper(): c['kategori'] = "Ketentuan Umum"
            elif "KETENTUAN PIDANA" in c['judul'].upper(): c['kategori'] = "Ketentuan Pidana"
            elif "KETENTUAN PERALIHAN" in c['judul'].upper(): c['kategori'] = "Ketentuan Peralihan"
            elif "KETENTUAN PENUTUP" in c['judul'].upper(): c['kategori'] = "Ketentuan Penutup"
            
        return chapters

    def process_penutup(self):
        """D. PENUTUP: Gabungan teks penutup."""
        df_pen = self.df[self.df['sistematika'] == "PENUTUP"]
        return {"text": self._clean_text(df_pen['text'])}