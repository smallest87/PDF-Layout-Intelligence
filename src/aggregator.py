import pandas as pd
import re
import yaml
import os

class MasterAggregator:
    def __init__(self, master_df, config_meta="config/meta_mapping.yaml"):
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
        """Pembersihan teks standar."""
        text = " ".join([str(t).strip() for t in text_list if str(t).strip()])
        return re.sub(r'\s+', ' ', text).strip()

    def run_all(self):
        """Menghasilkan struktur JSON A, B, C, D yang sudah nested."""
        return {
            "A_JUDUL": self.process_judul(),
            "B_PEMBUKAAN": self.process_pembukaan(),
            "C_BATANG_TUBUH": self.process_batang_tubuh(),
            "D_PENUTUP": self.process_penutup()
        }

    def process_judul(self):
        df_j = self.df[self.df['sistematika'] == "JUDUL"]
        full_text = self._clean_text(df_j['text'])
        # Ekstraksi metadata sederhana (Nomor/Tahun)
        no = re.search(r"NOMOR\s+([\d\w/.\-]+)", full_text, re.IGNORECASE)
        th = re.search(r"TAHUN\s+(\d{4})", full_text, re.IGNORECASE)
        return {
            "text": full_text,
            "metadata": {"nomor": no.group(1) if no else "NONE", "tahun": th.group(1) if th else "NONE"}
        }

    def process_pembukaan(self):
        df_p = self.df[self.df['sistematika'] == "PEMBUKAAN"]
        mapping = {"FRASA RELIGIUS": "frasa_religius", "PEMBENTUK PPU": "jabatan_pembentuk", 
                   "KONSIDERANS": "konsiderans", "DASAR HUKUM": "dasar_hukum", "DIKTUM": "diktum"}
        return {val: self._clean_text(df_p[df_p['unsur'] == key]['text']) for key, val in mapping.items()}

    def process_batang_tubuh(self):
        """C. BATANG TUBUH: Implementasi Struktur Nested (BAB > BAGIAN > PARAGRAF > PASAL)."""
        df_bt = self.df[self.df['sistematika'] == "BATANG TUBUH"]
        chapters = []
        
        curr_bab = None
        curr_bagian = None
        curr_paragraf = None
        curr_pasal = None

        for _, row in df_bt.iterrows():
            u = str(row['unsur'])
            t = str(row['text'])
            
            # 1. Level: BAB
            if u.startswith("BAB"):
                if not curr_bab or curr_bab['bab'] != u:
                    curr_bab = {"bab": u, "judul": t, "kategori": "Materi Pokok", "sections": [], "articles": []}
                    chapters.append(curr_bab)
                    curr_bagian, curr_paragraf, curr_pasal = None, None, None
                else: curr_bab['judul'] += " " + t
            
            # 2. Level: BAGIAN (Child of BAB)
            elif u.startswith("BAGIAN"):
                if not curr_bagian or curr_bagian['bagian'] != u:
                    curr_bagian = {"bagian": u, "judul": t, "paragraphs": [], "articles": []}
                    if curr_bab: curr_bab['sections'].append(curr_bagian)
                    curr_paragraf, curr_pasal = None, None
                else: curr_bagian['judul'] += " " + t

            # 3. Level: PARAGRAF (Child of BAGIAN)
            elif u.startswith("PARAGRAF"):
                if not curr_paragraf or curr_paragraf['paragraf'] != u:
                    curr_paragraf = {"paragraf": u, "judul": t, "articles": []}
                    if curr_bagian: curr_bagian['paragraphs'].append(curr_paragraf)
                    curr_pasal = None
                else: curr_paragraf['judul'] += " " + t

            # 4. Level: PASAL (Bisa di bawah Paragraf, Bagian, atau langsung BAB)
            elif u.startswith("PASAL"):
                if not curr_pasal or curr_pasal['nomor'] != u:
                    curr_pasal = {"nomor": u, "isi": t}
                    if curr_paragraf: curr_paragraf['articles'].append(curr_pasal)
                    elif curr_bagian: curr_bagian['articles'].append(curr_pasal)
                    elif curr_bab: curr_bab['articles'].append(curr_pasal)
                else: curr_pasal['isi'] += " " + t

        # Final Cleaning & Bab Categorization
        for c in chapters:
            c['judul'] = self._clean_text([c['judul']])
            if "KETENTUAN UMUM" in c['judul'].upper(): c['kategori'] = "Ketentuan Umum"
            elif "KETENTUAN PIDANA" in c['judul'].upper(): c['kategori'] = "Ketentuan Pidana"
            elif "KETENTUAN PERALIHAN" in c['judul'].upper(): c['kategori'] = "Ketentuan Peralihan"
            elif "KETENTUAN PENUTUP" in c['judul'].upper(): c['kategori'] = "Ketentuan Penutup"
            
        return chapters

    def process_penutup(self):
        df_pen = self.df[self.df['sistematika'] == "PENUTUP"]
        return {"text": self._clean_text(df_pen['text'])}