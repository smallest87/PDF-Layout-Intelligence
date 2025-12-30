import pandas as pd
import re

class LegalParser:
    def __init__(self, df):
        self.df = df.reset_index(drop=True)
        # Koordinat jangkar hasil kalibrasi
        self.X0_MENIMBANG = 70.825 
        self.X0_MENGINGAT = 71.025
        self.X0_PASAL_TITLE = 325.1
        self.X0_BODY_TEXT = 198.48
        self._calibrate_coordinates()

    def _calibrate_coordinates(self):
        """Auto-Calibration koordinat dokumen secara dinamis."""
        for i, row in self.df.iterrows():
            text = str(row['text']).strip()
            x0 = round(float(row['x0']), 3)
            if "Menimbang" in text:
                self.X0_MENIMBANG = x0
                if i + 1 < len(self.df):
                    self.X0_BODY_TEXT = round(float(self.df.iloc[i+1]['x0']), 3)
            elif "Mengingat" in text:
                self.X0_MENGINGAT = x0
            elif re.match(r"^Pasal\s+\d+", text, re.IGNORECASE):
                self.X0_PASAL_TITLE = x0

    def process_judul_autonomous(self):
        """TAHAP 1: Mengekstrak JUDUL (Nama Peraturan)."""
        results, content = [], []
        EXIT_PHRASES = ["DENGAN RAHMAT TUHAN", "KEPALA"]
        for _, row in self.df.iterrows():
            text = str(row['text']).strip()
            if any(p in text for p in EXIT_PHRASES) or ("Menimbang" in text and abs(float(row['x0']) - self.X0_MENIMBANG) < 1.0):
                break
            is_caps = sum(1 for c in text if c.isupper()) / len(text) > 0.7 if len(text) > 0 else False
            if is_caps and len(text) > 3 and not re.match(r"^-\s*\d+\s*-$", text):
                content.append(text)
        if content:
            results.append({"label": "JUDUL", "numbering": "NONE", "text": " ".join(content)})
        return pd.DataFrame(results)

    def process_pembukaan_religius_autonomous(self):
        """TAHAP 2: Mengekstrak PEMBUKAAN (Frasa Religius & Jabatan)."""
        results, content = [], []
        START_PHRASES = ["DENGAN RAHMAT TUHAN", "KEPALA"]
        collecting = False
        for _, row in self.df.iterrows():
            text = str(row['text']).strip()
            if any(p in text for p in START_PHRASES): collecting = True
            if collecting:
                if "Menimbang" in text and abs(float(row['x0']) - self.X0_MENIMBANG) < 1.0: break
                if not re.match(r"^-\s*\d+\s*-$", text): content.append(text)
        if content:
            results.append({"label": "PEMBUKAAN", "numbering": "NONE", "text": " ".join(content)})
        return pd.DataFrame(results)

    def process_konsideran_autonomous(self):
        """TAHAP 3: PEMBUKAAN (KONSIDERAN)."""
        results, i = [], 0
        def get_next_char(char): return chr(ord(char) + 1)
        while i < len(self.df):
            if "Menimbang" in str(self.df.iloc[i]['text']) and abs(round(float(self.df.iloc[i]['x0']), 3) - self.X0_MENIMBANG) < 0.5:
                exp = 'a'
                while i < len(self.df):
                    clean = re.sub(r"^Menimbang\s*:\s*", "", str(self.df.iloc[i]['text']).strip(), flags=re.IGNORECASE)
                    if re.search(rf"^{exp}\.\s+(.*)", clean, re.IGNORECASE) and round(float(self.df.iloc[i]['x0']), 3) < self.X0_BODY_TEXT:
                        m = re.search(rf"^{exp}\.\s+(.*)", clean, re.IGNORECASE); body = [m.group(1)]; j = i + 1
                        while j < len(self.df):
                            if round(float(self.df.iloc[j]['x0']), 3) < self.X0_BODY_TEXT - 5: break
                            body.append(str(self.df.iloc[j]['text']).strip()); j += 1
                        results.append({"label": "PEMBUKAAN (KONSIDERAN)", "numbering": exp, "text": " ".join(body)})
                        exp = chr(ord(exp) + 1); i = j
                    else:
                        if exp != 'a': return pd.DataFrame(results)
                        i += 1
            i += 1
        return pd.DataFrame(results)

    def process_dasar_hukum_autonomous(self):
        """TAHAP 4: PEMBUKAAN (DASAR HUKUM)."""
        results, i = [], 0
        while i < len(self.df):
            if "Mengingat" in str(self.df.iloc[i]['text']) and abs(round(float(self.df.iloc[i]['x0']), 3) - self.X0_MENGINGAT) < 0.5:
                exp = 1
                while i < len(self.df):
                    txt = str(self.df.iloc[i]['text']).strip()
                    if re.match(r"^-\s*\d+\s*-$", txt): i += 1; continue
                    clean = re.sub(r"^Mengingat\s*:\s*", "", txt, flags=re.IGNORECASE)
                    if re.search(rf"^{exp}\.\s+(.*)", clean) and round(float(self.df.iloc[i]['x0']), 3) < self.X0_BODY_TEXT:
                        m = re.search(rf"^{exp}\.\s+(.*)", clean); body = [m.group(1)]; j = i + 1
                        while j < len(self.df):
                            nxt = str(self.df.iloc[j]['text']).strip()
                            if re.match(r"^-\s*\d+\s*-$", nxt): j += 1; continue
                            if round(float(self.df.iloc[j]['x0']), 3) < self.X0_BODY_TEXT - 5: break
                            body.append(nxt); j += 1
                        results.append({"label": "PEMBUKAAN (DASAR HUKUM)", "numbering": str(exp), "text": " ".join(body)})
                        exp += 1; i = j
                    else:
                        if exp != 1: return pd.DataFrame(results)
                        i += 1
            i += 1
        return pd.DataFrame(results)

    def process_diktum_autonomous(self):
        """TAHAP 5: PEMBUKAAN (DIKTUM)."""
        for i in range(len(self.df)):
            if "MEMUTUSKAN:" in str(self.df.iloc[i]['text']):
                for j in range(i + 1, len(self.df)):
                    if "Menetapkan :" in str(self.df.iloc[j]['text']):
                        body = [re.sub(r"^Menetapkan\s*:\s*", "", str(self.df.iloc[j]['text']).strip(), flags=re.IGNORECASE)]
                        k = j + 1
                        while k < len(self.df):
                            if re.match(r"^(Pasal|BAB)\s+", str(self.df.iloc[k]['text']), re.IGNORECASE): break
                            body.append(str(self.df.iloc[k]['text']).strip()); k += 1
                        return pd.DataFrame([{"label": "PEMBUKAAN (DIKTUM)", "numbering": "MENETAPKAN", "text": " ".join(body)}])
        return pd.DataFrame()

    def process_batang_tubuh_autonomous(self):
        """TAHAP 6: BATANG TUBUH."""
        results, i = [], 0
        while i < len(self.df):
            text = str(self.df.iloc[i]['text']).strip()
            if "Agar setiap orang mengetahuinya" in text: break
            if re.match(r"^Pasal\s+(\d+)", text, re.IGNORECASE) and abs(round(float(self.df.iloc[i]['x0']), 3) - self.X0_PASAL_TITLE) < 1.0:
                num = re.match(r"^Pasal\s+(\d+)", text, re.IGNORECASE).group(1)
                body = []; j = i + 1
                while j < len(self.df):
                    nxt = str(self.df.iloc[j]['text']).strip()
                    if re.match(r"^Pasal\s+\d+", nxt, re.IGNORECASE) or "Agar setiap orang mengetahuinya" in nxt: break
                    if not re.match(r"^-\s*\d+\s*-$", nxt): body.append(nxt)
                    j += 1
                results.append({"label": "BATANG_TUBUH", "numbering": num, "text": " ".join(body)})
                i = j
            else: i += 1
        return pd.DataFrame(results)

    def process_penutup_autonomous(self):
        """TAHAP 7: PENUTUP."""
        results, perintah, penetapan, pengundangan = [], [], [], []
        state = "START"
        for _, row in self.df.iterrows():
            text = str(row['text']).strip()
            if "Agar setiap orang mengetahuinya" in text: state = "PERINTAH"
            elif "Ditetapkan di" in text: state = "PENETAPAN"
            elif "Diundangkan di" in text: state = "PENGUNDANGAN"
            elif "BERITA NEGARA" in text.upper(): break
            if state != "START" and not re.match(r"^-\s*\d+\s*-$", text):
                if state == "PERINTAH": perintah.append(text)
                elif state == "PENETAPAN": penetapan.append(text)
                elif state == "PENGUNDANGAN": pengundangan.append(text)
        if perintah: results.append({"label": "PENUTUP_PERINTAH", "numbering": "a", "text": " ".join(perintah)})
        if penetapan: results.append({"label": "PENUTUP_PENETAPAN", "numbering": "b", "text": " ".join(penetapan)})
        if pengundangan: results.append({"label": "PENUTUP_PENGUNDANGAN", "numbering": "c", "text": " ".join(pengundangan)})
        return pd.DataFrame(results)