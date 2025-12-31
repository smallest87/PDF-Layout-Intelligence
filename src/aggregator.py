import pandas as pd
import re
import yaml
import os

class MasterAggregator:
    def __init__(self, master_df, config_meta="config/meta_mapping.yaml"):
        # Sumber data tunggal dari MASTER.csv yang telah dilabeli
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
        """Pembersihan teks standar. Proteksi terhadap angka penting (Nomor/Tahun)."""
        text = " ".join([str(t).strip() for t in text_list if str(t).strip()])
        # Hanya membersihkan spasi ganda, tidak menghapus angka terisolasi agar Nomor/Tahun aman
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_metadata(self, text):
        """Ekstraksi metadata JUDUL dengan regex yang diprioritaskan pada angka."""
        detected_jenis = "TIDAK_TERDETEKSI"
        detected_kategori = "TIDAK_TERDETEKSI"
        sorted_samples = sorted(self.ALL_SAMPLES, key=len, reverse=True)
        for s in sorted_samples:
            if s.lower() in text.lower():
                detected_jenis = s
                for k, v in self.META_MAPPING.items():
                    if s in v: detected_kategori = k; break
                break

        # Regex yang lebih ketat untuk menangkap angka NOMOR dan TAHUN
        no_match = re.search(r"NOMOR\s+([\d/.\-]+)", text, re.IGNORECASE)
        thn_match = re.search(r"TAHUN\s+(\d{4})", text, re.IGNORECASE)
        tentang_match = re.search(r"TENTANG\s+(.*)", text, re.IGNORECASE)

        return {
            "kategori": detected_kategori,
            "jenis": detected_jenis,
            "nomor": no_match.group(1) if no_match else "NONE",
            "tahun": thn_match.group(1) if thn_match else "NONE",
            "tentang": tentang_match.group(1).strip() if tentang_match else "NONE"
        }

    def _parse_rincian(self, text):
        """Mengurai rincian (1. atau a.) menggunakan key 'teks'."""
        # Batasan: Poin harus diawali spasi atau awal baris agar tidak memotong kata
        pattern = r"(?:^|\s)(\d+\.|[a-z]\.)\s+"
        if not re.search(pattern, text):
            return text

        parts = re.split(pattern, text)
        res = {
            "teks_pembuka": parts[0].strip(),
            "rincian": []
        }

        for i in range(1, len(parts), 2):
            no_rincian = parts[i].strip().replace(".", "")
            isi_rincian = parts[i+1].strip() if i+1 < len(parts) else ""
            if isi_rincian:
                res["rincian"].append({
                    "nomor": no_rincian,
                    "teks": re.sub(r'\s+', ' ', isi_rincian).strip()
                })
        return res

    def _parse_ayat(self, text):
        """Mengurai ayat ke dalam struktur nested {teks_pembuka, ayat: []}."""
        matches = list(re.finditer(r"\((\d+)\)", text))
        
        if not any(int(m.group(1)) == 1 for m in matches):
            return self._parse_rincian(text)

        ayat_results = []
        last_pos, expected_ayat = 0, 1
        header_text = ""

        for match in matches:
            ayat_num = int(match.group(1))
            if ayat_num == expected_ayat:
                segment = text[last_pos:match.start()].strip()
                if expected_ayat == 1:
                    header_text = segment
                else:
                    if ayat_results:
                        ayat_results[-1]["teks"] = self._parse_rincian(segment)
                
                ayat_results.append({"ayat": str(ayat_num), "teks": ""})
                last_pos, expected_ayat = match.end(), expected_ayat + 1

        if last_pos < len(text) and ayat_results:
            ayat_results[-1]["teks"] = self._parse_rincian(text[last_pos:].strip())

        return {
            "teks_pembuka": header_text,
            "ayat": ayat_results
        }

    def run_all(self):
        """Menghasilkan struktur JSON A, B, C, D secara lengkap."""
        return {
            "A_JUDUL": self.process_judul(),
            "B_PEMBUKAAN": self.process_pembukaan(),
            "C_BATANG_TUBUH": self.process_batang_tubuh(),
            "D_PENUTUP": self.process_penutup()
        }

    def process_judul(self):
        """A. JUDUL: Konsolidasi teks dan metadata."""
        df_j = self.df[self.df['sistematika'] == "JUDUL"]
        full_text = self._clean_text(df_j['text'])
        return {
            "teks": full_text,
            "metadata": self._extract_metadata(full_text)
        }

    def process_pembukaan(self):
        """B. PEMBUKAAN: Mengurai unsur pembukaan dengan key 'teks'."""
        df_p = self.df[self.df['sistematika'] == "PEMBUKAAN"]
        kon_raw = self._clean_text(df_p[df_p['unsur'] == "KONSIDERANS"]['text'])
        dh_raw = self._clean_text(df_p[df_p['unsur'] == "DASAR HUKUM"]['text'])
        
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
        """C. BATANG TUBUH: Struktur Hierarki Nested dengan judul bersih."""
        df_bt = self.df[self.df['sistematika'] == "BATANG TUBUH"]
        chapters = []
        curr_bab, curr_bagian, curr_paragraf, curr_pasal = None, None, None, None

        for _, row in df_bt.iterrows():
            u, t = str(row['unsur']), str(row['text'])
            if u.startswith("BAB"):
                if not curr_bab or curr_bab['bab'] != u:
                    curr_bab = {"bab": u, "judul": t, "kategori": "Materi Pokok", "sections": [], "pasal": []}
                    chapters.append(curr_bab); curr_bagian = curr_paragraf = curr_pasal = None
                else: curr_bab['judul'] += " " + t
            elif u.startswith("BAGIAN"):
                if not curr_bagian or curr_bagian['bagian'] != u:
                    curr_bagian = {"bagian": u, "judul": t, "paragraphs": [], "pasal": []}
                    if curr_bab: curr_bab['sections'].append(curr_bagian); curr_paragraf = curr_pasal = None
                else: curr_bagian['judul'] += " " + t
            elif u.startswith("PARAGRAF"):
                if not curr_paragraf or curr_paragraf['paragraf'] != u:
                    curr_paragraf = {"paragraf": u, "judul": t, "pasal": []}
                    if curr_bagian: curr_bagian['paragraphs'].append(curr_paragraf); curr_pasal = None
                else: curr_paragraf['judul'] += " " + t
            elif u.startswith("PASAL"):
                if not curr_pasal or curr_pasal.get('nomor_raw') != u:
                    p_num = re.search(r"\d+", u).group() if re.search(r"\d+", u) else u
                    curr_pasal = {"nomor": p_num, "teks": t, "nomor_raw": u}
                    if curr_paragraf: curr_paragraf['pasal'].append(curr_pasal)
                    elif curr_bagian: curr_bagian['pasal'].append(curr_pasal)
                    elif curr_bab: curr_bab['pasal'].append(curr_pasal)
                else: curr_pasal['teks'] += " " + t

        

        for c in chapters:
            # Membersihkan label "BAB X" dari judul
            c['judul'] = re.sub(rf"^{c['bab']}\s*", "", self._clean_text([c['judul']]), flags=re.IGNORECASE).strip()

            def clean_list(p_list):
                for p in p_list:
                    raw_text = self._clean_text([p['teks']])
                    # Menghapus "Pasal X" di awal teks
                    cleaned_text = re.sub(rf"^\s*Pasal\s+{p['nomor']}\s*", "", raw_text, flags=re.IGNORECASE).strip()
                    parsed = self._parse_ayat(cleaned_text)
                    # Menghapus header jika hanya berisi kata "Pasal"
                    if isinstance(parsed, dict) and parsed.get("teks_pembuka", "").lower() == "pasal":
                        parsed["teks_pembuka"] = ""
                    p['teks'] = parsed
                    if 'nomor_raw' in p: del p['nomor_raw']
            
            clean_list(c['pasal'])
            for s in c['sections']:
                s['judul'] = re.sub(rf"^{s['bagian']}\s*", "", self._clean_text([s['judul']]), flags=re.IGNORECASE).strip()
                clean_list(s['pasal'])
                for pg in s['paragraphs']:
                    pg['judul'] = re.sub(rf"^{pg['paragraf']}\s*", "", self._clean_text([pg['judul']]), flags=re.IGNORECASE).strip()
                    clean_list(pg['pasal'])
            
            if "KETENTUAN UMUM" in c['judul'].upper(): c['kategori'] = "Ketentuan Umum"
            elif "KETENTUAN PENUTUP" in c['judul'].upper(): c['kategori'] = "Ketentuan Penutup"
            
        return chapters

    def process_penutup(self):
        """D. PENUTUP: Metadata pengesahan dan pengundangan dengan key 'teks'."""
        df_pen = self.df[self.df['sistematika'] == "PENUTUP"]
        full_text = self._clean_text(df_pen['text'])

        m_sah = re.search(r"Ditetapkan di\s+(.*?)\s+pada tanggal\s+(.*?)\s+([A-Z\s\.,]+?)\s+(ttd\.|tanda tangan)\s+([A-Z\s\.,]+?)(?=\s+Diundangkan|$)", full_text, re.IGNORECASE)
        m_und = re.search(r"Diundangkan di\s+(.*?)\s+pada tanggal\s+(.*?)\s+([A-Z\s\.,]+?)\s+(ttd\.|tanda tangan)\s+([A-Z\s\.,]+?)(?=\s+Lembaran|$)", full_text, re.IGNORECASE)
        m_reg = re.search(r"NOMOR REGISTER.*?\s+NOMOR\s+([\d\w/.\-]+)", full_text, re.IGNORECASE)

        return {
            "teks": full_text,
            "pengesahan": {
                "tempat": m_sah.group(1).strip() if m_sah else "NONE",
                "tanggal": m_sah.group(2).strip() if m_sah else "NONE",
                "nama_jabatan": m_sah.group(3).strip() if m_sah else "NONE",
                "tanda_tangan": m_sah.group(4).strip() if m_sah else "NONE",
                "nama_pejabat": m_sah.group(5).strip() if m_sah else "NONE"
            },
            "pengundangan": {
                "tempat": m_und.group(1).strip() if m_und else "NONE",
                "tanggal": m_und.group(2).strip() if m_und else "NONE",
                "nama_jabatan": m_und.group(3).strip() if m_und else "NONE",
                "tanda_tangan": m_und.group(4).strip() if m_und else "NONE",
                "nama_pejabat": m_und.group(5).strip() if m_und else "NONE"
            },
            "nomor_register": m_reg.group(1).strip() if m_reg else "NONE"
        }