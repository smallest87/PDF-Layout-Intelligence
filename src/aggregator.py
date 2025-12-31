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
        """Pembersihan agresif untuk nomor halaman dan spasi liar."""
        text = " ".join([str(t).strip() for t in text_list if str(t).strip()])
        # Hapus angka halaman yang berdiri sendiri (digit terisolasi)
        text = re.sub(r'(?<=\s)\d+(?=\s)', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _parse_rincian(self, text):
        """Mengurai rincian dengan validasi batas kata untuk mencegah false positive."""
        # Batasan: Poin harus diawali spasi atau awal baris agar tidak memotong kata (seperti Malang.)
        pattern = r"(?:^|\s)(\d+\.|[a-z]\.)\s+"
        
        if not re.search(pattern, text):
            return text

        # Gunakan split dengan memastikan poin bukan bagian dari kata
        parts = re.split(pattern, text)
        
        res = {
            "teks_pembuka": parts[0].strip(),
            "rincian": []
        }

        # Iterasi: parts[i] adalah nomor poin, parts[i+1] adalah isinya
        for i in range(1, len(parts), 2):
            no_rincian = parts[i].strip().replace(".", "")
            isi_rincian = parts[i+1].strip() if i+1 < len(parts) else ""
            if isi_rincian:
                res["rincian"].append({
                    "nomor": no_rincian,
                    "isi": re.sub(r'\s+', ' ', isi_rincian).strip()
                })
        return res

    def _parse_ayat(self, text):
        """Parsing ayat dengan Sequential Validation."""
        matches = list(re.finditer(r"\((\d+)\)", text))
        
        # Jika tidak ada urutan ayat (1) yang valid, proses sebagai rincian biasa
        if not any(int(m.group(1)) == 1 for m in matches):
            return self._parse_rincian(text)

        ayat_list = []
        last_pos, expected_ayat = 0, 1
        
        for match in matches:
            ayat_num = int(match.group(1))
            if ayat_num == expected_ayat:
                segment_text = text[last_pos:match.start()].strip()
                if segment_text:
                    if not ayat_list:
                        ayat_list.append({"ayat": "header", "teks": segment_text})
                    else:
                        ayat_list[-1]["teks"] = self._parse_rincian(segment_text)
                
                ayat_list.append({"ayat": str(ayat_num), "teks": ""})
                last_pos, expected_ayat = match.end(), expected_ayat + 1

        if last_pos < len(text):
            final_segment = text[last_pos:].strip()
            if final_segment and ayat_list:
                ayat_list[-1]["teks"] = self._parse_rincian(final_segment)

        return ayat_list

    def run_all(self):
        return {
            "A_JUDUL": self.process_judul(),
            "B_PEMBUKAAN": self.process_pembukaan(),
            "C_BATANG_TUBUH": self.process_batang_tubuh(),
            "D_PENUTUP": self.process_penutup()
        }

    def process_judul(self):
        df_j = self.df[self.df['sistematika'] == "JUDUL"]
        full_text = self._clean_text(df_j['text'])
        no = re.search(r"NOMOR\s+([\d\w/.\-]+)", full_text, re.IGNORECASE)
        th = re.search(r"TAHUN\s+(\d{4})", full_text, re.IGNORECASE)
        return {
            "text": full_text,
            "metadata": {"nomor": no.group(1) if no else "NONE", "tahun": th.group(1) if th else "NONE"}
        }

    def process_pembukaan(self):
        df_p = self.df[self.df['sistematika'] == "PEMBUKAAN"]
        kon_raw = self._clean_text(df_p[df_p['unsur'] == "KONSIDERANS"]['text'])
        dh_raw = self._clean_text(df_p[df_p['unsur'] == "DASAR HUKUM"]['text'])
        
        # Penguraian poin untuk konsiderans dan dasar hukum
        kon_data = self._parse_rincian(kon_raw)
        dh_data = self._parse_rincian(dh_raw)
        
        return {
            "frasa_religius": self._clean_text(df_p[df_p['unsur'] == "FRASA RELIGIUS"]['text']),
            "jabatan_pembentuk": self._clean_text(df_p[df_p['unsur'] == "PEMBENTUK PPU"]['text']),
            "konsiderans": kon_data.get("rincian", []) if isinstance(kon_data, dict) else [],
            "dasar_hukum": dh_data.get("rincian", []) if isinstance(dh_data, dict) else [],
            "diktum": self._clean_text(df_p[df_p['unsur'] == "DIKTUM"]['text'])
        }

    def process_batang_tubuh(self):
        df_bt = self.df[self.df['sistematika'] == "BATANG TUBUH"]
        chapters = []
        curr_bab, curr_bagian, curr_paragraf, curr_pasal = None, None, None, None

        for _, row in df_bt.iterrows():
            u, t = str(row['unsur']), str(row['text'])
            if u.startswith("BAB"):
                if not curr_bab or curr_bab['bab'] != u:
                    curr_bab = {"bab": u, "judul": t, "kategori": "Materi Pokok", "sections": [], "pasal": []}
                    chapters.append(curr_bab)
                    curr_bagian = curr_paragraf = curr_pasal = None
                else: curr_bab['judul'] += " " + t
            elif u.startswith("BAGIAN"):
                if not curr_bagian or curr_bagian['bagian'] != u:
                    curr_bagian = {"bagian": u, "judul": t, "paragraphs": [], "pasal": []}
                    if curr_bab: curr_bab['sections'].append(curr_bagian)
                    curr_paragraf = curr_pasal = None
                else: curr_bagian['judul'] += " " + t
            elif u.startswith("PARAGRAF"):
                if not curr_paragraf or curr_paragraf['paragraf'] != u:
                    curr_paragraf = {"paragraf": u, "judul": t, "pasal": []}
                    if curr_bagian: curr_bagian['paragraphs'].append(curr_paragraf)
                    curr_pasal = None
                else: curr_paragraf['judul'] += " " + t
            elif u.startswith("PASAL"):
                if not curr_pasal or curr_pasal.get('nomor_raw') != u:
                    p_num = re.search(r"\d+", u).group() if re.search(r"\d+", u) else u
                    curr_pasal = {"nomor": p_num, "isi": t, "nomor_raw": u}
                    if curr_paragraf: curr_paragraf['pasal'].append(curr_pasal)
                    elif curr_bagian: curr_bagian['pasal'].append(curr_pasal)
                    elif curr_bab: curr_bab['pasal'].append(curr_pasal)
                else: curr_pasal['isi'] += " " + t

        for c in chapters:
            c['judul'] = self._clean_text([c['judul']])
            def clean_list(p_list):
                for p in p_list:
                    p['isi'] = self._clean_text([p['isi']])
                    # Pembersihan ketat "Pasal X" di awal baris
                    p['isi'] = re.sub(rf"^\s*Pasal\s+{p['nomor']}\s*", "", p['isi'], flags=re.IGNORECASE).strip()
                    p['isi'] = self._parse_ayat(p['isi'])
                    if 'nomor_raw' in p: del p['nomor_raw']
            
            clean_list(c['pasal'])
            for s in c['sections']:
                s['judul'] = self._clean_text([s['judul']]); clean_list(s['pasal'])
                for pg in s['paragraphs']:
                    pg['judul'] = self._clean_text([pg['judul']]); clean_list(pg['pasal'])
        return chapters

    def process_penutup(self):
        df_pen = self.df[self.df['sistematika'] == "PENUTUP"]
        return {"text": self._clean_text(df_pen['text'])}