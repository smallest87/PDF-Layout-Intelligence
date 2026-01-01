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
        """Membersihkan spasi ganda dan menggabungkan list teks."""
        text = " ".join([str(t).strip() for t in text_list if str(t).strip()])
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_metadata(self, text):
        """Mengekstrak Jenis PPU, Nomor, Tahun, dan Tentang dari Judul."""
        detected_jenis = detected_kategori = "TIDAK_TERDETEKSI"
        sorted_samples = sorted(self.ALL_SAMPLES, key=len, reverse=True)
        
        for s in sorted_samples:
            if s.lower() in text.lower():
                detected_jenis = s
                for k, v in self.META_MAPPING.items():
                    if s in v: detected_kategori = k; break
                break

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

    def _parse_rincian(self, text, is_definisi=False):
        """Memecah teks menjadi rincian poin. Mendukung fallback nomor kosong untuk paragraf tunggal."""
        pattern = r"(?:^|\s)(\d+\.|[a-z]\.)\s+"
        key_name = "definisi" if is_definisi else "teks"

        # REVISI: Jika tidak ada numbering, nomor disetel kosong ("")
        if not re.search(pattern, text):
            return {
                "teks_pembuka": "",
                "rincian": [{"nomor": "", key_name: text.strip()}] if text.strip() else []
            }

        parts = re.split(pattern, text)
        res = {"teks_pembuka": parts[0].strip(), "rincian": []}

        for i in range(1, len(parts), 2):
            no_rincian = parts[i].strip().replace(".", "")
            isi_rincian = parts[i+1].strip() if i+1 < len(parts) else ""
            if isi_rincian:
                res["rincian"].append({
                    "nomor": no_rincian,
                    key_name: re.sub(r'\s+', ' ', isi_rincian).strip()
                })
        return res

    def _parse_ayat(self, text, is_definisi=False):
        """Mengurai ayat (1) dan rincian di bawahnya secara hirarkis."""
        matches = list(re.finditer(r"\((\d+)\)", text))
        if not any(int(m.group(1)) == 1 for m in matches):
            return self._parse_rincian(text, is_definisi)

        ayat_results, last_pos, expected_ayat, header_text = [], 0, 1, ""
        for match in matches:
            ayat_num = int(match.group(1))
            if ayat_num == expected_ayat:
                segment = text[last_pos:match.start()].strip()
                if expected_ayat == 1:
                    header_text = segment
                else:
                    if ayat_results:
                        ayat_results[-1]["teks"] = self._parse_rincian(segment, is_definisi)
                
                ayat_results.append({"ayat": str(ayat_num), "teks": ""})
                last_pos, expected_ayat = match.end(), expected_ayat + 1

        if last_pos < len(text) and ayat_results:
            ayat_results[-1]["teks"] = self._parse_rincian(text[last_pos:].strip(), is_definisi)
            
        return {"teks_pembuka": header_text, "ayat": ayat_results}

    def process_judul(self):
        df_j = self.df[self.df['sistematika'] == "JUDUL"]
        full_text = self._clean_text(df_j['text'])
        return {"teks": full_text, "metadata": self._extract_metadata(full_text)}

    def process_pembukaan(self):
        """B. PEMBUKAAN: Membersihkan anchor 'Menimbang' dan 'Mengingat'."""
        df_p = self.df[self.df['sistematika'] == "PEMBUKAAN"]
        
        # Ekstraksi dan Pembersihan Konsiderans
        kon_raw = self._clean_text(df_p[df_p['unsur'] == "KONSIDERANS"]['text'])
        kon_clean = re.sub(r'^Menimbang\s*:\s*', '', kon_raw, flags=re.IGNORECASE).strip()
        
        # Ekstraksi dan Pembersihan Dasar Hukum
        dh_raw = self._clean_text(df_p[df_p['unsur'] == "DASAR HUKUM"]['text'])
        dh_clean = re.sub(r'^Mengingat\s*:\s*', '', dh_raw, flags=re.IGNORECASE).strip()

        return {
            "frasa_religius": self._clean_text(df_p[df_p['unsur'] == "FRASA RELIGIUS"]['text']),
            "jabatan_pembentuk": self._clean_text(df_p[df_p['unsur'] == "PEMBENTUK PPU"]['text']),
            "konsiderans": self._parse_rincian(kon_clean)["rincian"],
            "dasar_hukum": self._parse_rincian(dh_clean)["rincian"],
            "diktum": self._clean_text(df_p[df_p['unsur'] == "DIKTUM"]['text'])
        }

    def process_batang_tubuh(self):
        df_bt = self.df[self.df['sistematika'] == "BATANG TUBUH"]
        chapters = []
        curr_bab = curr_bagian = curr_paragraf = curr_pasal = None

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
                    curr_pasal = {"nomor": p_num, "teks": t, "nomor_raw": u}
                    if curr_paragraf: curr_paragraf['pasal'].append(curr_pasal)
                    elif curr_bagian: curr_bagian['pasal'].append(curr_pasal)
                    elif curr_bab: curr_bab['pasal'].append(curr_pasal)
                else: curr_pasal['teks'] += " " + t

        for c in chapters:
            c['judul'] = re.sub(rf"^{c['bab']}\s*", "", self._clean_text([c['judul']]), flags=re.IGNORECASE).strip()
            if "KETENTUAN UMUM" in c['judul'].upper(): c['kategori'] = "Ketentuan Umum"
            elif "KETENTUAN PENUTUP" in c['judul'].upper(): c['kategori'] = "Ketentuan Penutup"
            is_def = (c['kategori'] == "Ketentuan Umum")

            def process_pasal_list(p_list):
                for p in p_list:
                    raw = self._clean_text([p['teks']])
                    cleaned = re.sub(rf"^\s*Pasal\s+{p['nomor']}\s*", "", raw, flags=re.IGNORECASE).strip()
                    p['teks'] = self._parse_ayat(cleaned, is_definisi=is_def)
                    if 'nomor_raw' in p: del p['nomor_raw']

            process_pasal_list(c['pasal'])
            for s in c['sections']:
                s['judul'] = re.sub(rf"^{s['bagian']}\s*", "", self._clean_text([s['judul']]), flags=re.IGNORECASE).strip()
                process_pasal_list(s['pasal'])
                for pg in s['paragraphs']:
                    pg['judul'] = re.sub(rf"^{pg['paragraf']}\s*", "", self._clean_text([pg['judul']]), flags=re.IGNORECASE).strip()
                    process_pasal_list(pg['pasal'])
        return chapters

    def process_penutup(self):
        df_pen = self.df[self.df['sistematika'] == "PENUTUP"]
        full_text = self._clean_text(df_pen['text'])

        m_sah = re.search(r"(?:Ditetapkan|Disahkan) di\s+(.*?)\s+pada tanggal\s+(.*?)\s+([A-Z\s\.,]+?)\s+(ttd\.|tanda tangan)\s+([A-Z\s\.,]+?)(?=\s+Diundangkan|$)", full_text, re.IGNORECASE)
        m_und = re.search(r"Diundangkan di\s+(.*?)\s+pada tanggal\s+(.*?)\s+([A-Z\s\.,]+?)\s+(ttd\.|tanda tangan)\s+([A-Z\s\.,]+?)(?=\s+(?:Berita|Lembaran|TAMBAHAN|$))", full_text, re.IGNORECASE)
        m_pub = re.search(r"((?:Berita|Lembaran)\s+Daerah.*?(?:Tahun\s+\d{4}\s+Nomor\s+[\d\w\s]+|$))", full_text, re.IGNORECASE)

        return {
            "teks": full_text,
            "pengesahan": {
                "tempat": m_sah.group(1).strip() if m_sah else "NONE",
                "tanggal": m_sah.group(2).strip() if m_sah else "NONE",
                "nama_jabatan": m_sah.group(3).strip() if m_sah else "NONE",
                "nama_pejabat": m_sah.group(5).strip() if m_sah else "NONE"
            },
            "pengundangan": {
                "tempat": m_und.group(1).strip() if m_und else "NONE",
                "tanggal": m_und.group(2).strip() if m_und else "NONE",
                "nama_jabatan": m_und.group(3).strip() if m_und else "NONE",
                "nama_pejabat": m_und.group(5).strip() if m_und else "NONE"
            },
            "publikasi": m_pub.group(0).strip() if m_pub else "NONE"
        }

    def run_all(self):
        return {
            "A_JUDUL": self.process_judul(),
            "B_PEMBUKAAN": self.process_pembukaan(),
            "C_BATANG_TUBUH": self.process_batang_tubuh(),
            "D_PENUTUP": self.process_penutup()
        }