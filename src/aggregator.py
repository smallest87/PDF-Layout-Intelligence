import pandas as pd
import re
import yaml
import os

class MasterAggregator:
    def __init__(self, master_df, config_meta="config/meta_mapping.yaml"):
        # Sumber data tunggal dari file MASTER yang telah dilabeli
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
        """Pembersihan spasi ganda dan penggabungan list teks."""
        text = " ".join([str(t).strip() for t in text_list if str(t).strip()])
        return re.sub(r'\s+', ' ', text).strip()

    def _parse_points(self, df_unsur, pattern, prefix_to_strip=None):
        """Mengurai teks poin (a. b. c.) menjadi array objek terstruktur."""
        points = []
        current_point = None
        for _, row in df_unsur.iterrows():
            text = str(row['text']).strip()
            if prefix_to_strip:
                text = re.sub(rf"^{prefix_to_strip}\s*:\s*", "", text, flags=re.IGNORECASE)
            match = re.match(pattern, text)
            if match:
                if current_point: points.append(current_point)
                current_point = {"nomor": match.group(1), "isi": match.group(2)}
            else:
                if current_point: current_point["isi"] += " " + text
        if current_point: points.append(current_point)
        for p in points: p['isi'] = re.sub(r'\s+', ' ', p['isi']).strip()
        return points

    def _parse_ayat(self, text):
        """Mengurai ayat dengan Sequential Validation untuk menghindari anomali referensi."""
        # Cari semua kandidat ayat (angka dalam kurung) di seluruh teks pasal
        matches = list(re.finditer(r"\((\d+)\)", text))
        
        # Jika tidak ditemukan angka (1) di awal atau dalam teks, anggap pasal tanpa ayat
        if not any(int(m.group(1)) == 1 for m in matches):
            return text

        ayat_list = []
        last_pos = 0
        expected_ayat = 1
        
        for match in matches:
            ayat_num = int(match.group(1))
            start_pos = match.start()
            
            # VALIDASI: Hanya pecah jika nomor ayat sesuai urutan (1, 2, 3...)
            if ayat_num == expected_ayat:
                # Ambil teks yang berada di antara marker ayat saat ini dan sebelumnya
                segment_text = text[last_pos:start_pos].strip()
                if segment_text:
                    if not ayat_list:
                        # Jika teks muncul sebelum ayat (1), simpan sebagai header
                        ayat_list.append({"ayat": "header", "teks": segment_text})
                    else:
                        # Masukkan teks ke dalam isi ayat sebelumnya
                        ayat_list[-1]["teks"] = (ayat_list[-1]["teks"] + " " + segment_text).strip()
                
                # Buat entri ayat baru dan naikkan counter urutan
                ayat_list.append({"ayat": str(ayat_num), "teks": ""})
                last_pos = match.end()
                expected_ayat += 1
            # Jika tidak sesuai urutan (misal: (1) muncul di tengah ayat 2), abaikan sebagai referensi

        # Tambahkan sisa teks setelah marker ayat terakhir
        if last_pos < len(text):
            final_text = text[last_pos:].strip()
            if final_text and ayat_list:
                ayat_list[-1]["teks"] = (ayat_list[-1]["teks"] + " " + final_text).strip()

        return ayat_list

    def run_all(self):
        """Eksekutor utama pengolahan data terstruktur A, B, C, D."""
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
        kon_nested = self._parse_points(df_p[df_p['unsur'] == "KONSIDERANS"], r"^([a-z])\.\s+(.*)", "Menimbang")
        dh_nested = self._parse_points(df_p[df_p['unsur'] == "DASAR HUKUM"], r"^(\d+)\.\s+(.*)", "Mengingat")
        return {
            "frasa_religius": self._clean_text(df_p[df_p['unsur'] == "FRASA RELIGIUS"]['text']),
            "jabatan_pembentuk": self._clean_text(df_p[df_p['unsur'] == "PEMBENTUK PPU"]['text']),
            "konsiderans": kon_nested, "dasar_hukum": dh_nested,
            "diktum": self._clean_text(df_p[df_p['unsur'] == "DIKTUM"]['text'])
        }

    def process_batang_tubuh(self):
        """C. BATANG TUBUH: Struktur Hierarki dengan Sequential Verse Parsing."""
        df_bt = self.df[self.df['sistematika'] == "BATANG TUBUH"]
        chapters = []
        curr_bab, curr_bagian, curr_paragraf, curr_pasal = None, None, None, None

        for _, row in df_bt.iterrows():
            u = str(row['unsur'])
            t = str(row['text'])
            
            if u.startswith("BAB"):
                if not curr_bab or curr_bab['bab'] != u:
                    curr_bab = {"bab": u, "judul": t, "kategori": "Materi Pokok", "sections": [], "pasal": []}
                    chapters.append(curr_bab)
                    curr_bagian, curr_paragraf, curr_pasal = None, None, None
                else: curr_bab['judul'] += " " + t
            elif u.startswith("BAGIAN"):
                if not curr_bagian or curr_bagian['bagian'] != u:
                    curr_bagian = {"bagian": u, "judul": t, "paragraphs": [], "pasal": []}
                    if curr_bab: curr_bab['sections'].append(curr_bagian)
                    curr_paragraf, curr_pasal = None, None
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
            def process_pasal_list(art_list):
                for p in art_list:
                    p['isi'] = self._clean_text([p['isi']])
                    p['isi'] = re.sub(rf"^Pasal\s+{p['nomor']}\s*", "", p['isi'], flags=re.IGNORECASE).strip()
                    p['isi'] = self._parse_ayat(p['isi']) # Menggunakan logika sequential baru
                    if 'nomor_raw' in p: del p['nomor_raw']
            
            process_pasal_list(c['pasal'])
            for s in c['sections']:
                s['judul'] = self._clean_text([s['judul']])
                process_pasal_list(s['pasal'])
                for pg in s['paragraphs']:
                    pg['judul'] = self._clean_text([pg['judul']])
                    process_pasal_list(pg['pasal'])
            
            if "KETENTUAN UMUM" in c['judul'].upper(): c['kategori'] = "Ketentuan Umum"
            elif "KETENTUAN PENUTUP" in c['judul'].upper(): c['kategori'] = "Ketentuan Penutup"
            
        return chapters

    def process_penutup(self):
        df_pen = self.df[self.df['sistematika'] == "PENUTUP"]
        return {"text": self._clean_text(df_pen['text'])}