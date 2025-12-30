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
        self.X0_PENUTUP_LEFT = 70.825
        self.X0_PENUTUP_RIGHT = 311.9
        self._calibrate_coordinates()

    def _calibrate_coordinates(self):
        """Auto-Calibration: Mengambil koordinat standar dari data aktual."""
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
            elif "Ditetapkan di" in text:
                self.X0_PENUTUP_RIGHT = x0
            elif "Diundangkan di" in text:
                self.X0_PENUTUP_LEFT = x0

    def process_judul_autonomous(self):
        """Ekstraksi JUDUL."""
        refined_results = []
        collected_text = []
        EXIT_PHRASES = ["DENGAN RAHMAT TUHAN", "KEPALA"]
        for i, row in self.df.iterrows():
            text = str(row['text']).strip()
            if any(phrase in text for phrase in EXIT_PHRASES) or ("Menimbang" in text and abs(float(row['x0']) - self.X0_MENIMBANG) < 1.0): break
            is_caps = sum(1 for c in text if c.isupper()) / len(text) > 0.7 if len(text) > 0 else False
            if is_caps and len(text) > 3 and not re.match(r"^-\s*\d+\s*-$", text):
                collected_text.append(text)
        if collected_text:
            refined_results.append({"label": "JUDUL_PERATURAN", "numbering": "NONE", "text": " ".join(collected_text)})
        return pd.DataFrame(refined_results)

    def process_konsideran_autonomous(self):
        """Ekstraksi KONSIDERAN (a, b, c)."""
        refined_results = []
        i = 0
        def get_next_char(char): return chr(ord(char) + 1)
        while i < len(self.df):
            if "Menimbang" in str(self.df.iloc[i]['text']) and abs(round(float(self.df.iloc[i]['x0']), 3) - self.X0_MENIMBANG) < 0.5:
                expected = 'a'
                while i < len(self.df):
                    clean = re.sub(r"^Menimbang\s*:\s*", "", str(self.df.iloc[i]['text']).strip(), flags=re.IGNORECASE)
                    if re.search(rf"^{expected}\.\s+(.*)", clean, re.IGNORECASE) and round(float(self.df.iloc[i]['x0']), 3) < self.X0_BODY_TEXT:
                        match = re.search(rf"^{expected}\.\s+(.*)", clean, re.IGNORECASE)
                        content = [match.group(1)]; j = i + 1
                        while j < len(self.df):
                            if round(float(self.df.iloc[j]['x0']), 3) < self.X0_BODY_TEXT - 5: break
                            content.append(str(self.df.iloc[j]['text']).strip()); j += 1
                        refined_results.append({"label": "KONSIDERAN", "numbering": expected, "text": " ".join(content)})
                        expected = get_next_char(expected); i = j
                    else:
                        if expected != 'a': return pd.DataFrame(refined_results)
                        i += 1
            i += 1
        return pd.DataFrame(refined_results)

    def process_dasar_hukum_autonomous(self):
        """Ekstraksi DASAR HUKUM (1, 2, 3)."""
        refined_results = []
        i = 0
        while i < len(self.df):
            if "Mengingat" in str(self.df.iloc[i]['text']) and abs(round(float(self.df.iloc[i]['x0']), 3) - self.X0_MENGINGAT) < 0.5:
                expected = 1
                while i < len(self.df):
                    text = str(self.df.iloc[i]['text']).strip()
                    if re.match(r"^-\s*\d+\s*-$", text): i += 1; continue
                    clean = re.sub(r"^Mengingat\s*:\s*", "", text, flags=re.IGNORECASE)
                    if re.search(rf"^{expected}\.\s+(.*)", clean) and round(float(self.df.iloc[i]['x0']), 3) < self.X0_BODY_TEXT:
                        match = re.search(rf"^{expected}\.\s+(.*)", clean)
                        content = [match.group(1)]; j = i + 1
                        while j < len(self.df):
                            nxt = str(self.df.iloc[j]['text']).strip()
                            if re.match(r"^-\s*\d+\s*-$", nxt): j += 1; continue
                            if round(float(self.df.iloc[j]['x0']), 3) < self.X0_BODY_TEXT - 5: break
                            content.append(nxt); j += 1
                        refined_results.append({"label": "DASAR_HUKUM", "numbering": str(expected), "text": " ".join(content)})
                        expected += 1; i = j
                    else:
                        if expected != 1: return pd.DataFrame(refined_results)
                        i += 1
            i += 1
        return pd.DataFrame(refined_results)

    def process_diktum_autonomous(self):
        """Ekstraksi DIKTUM."""
        for i in range(len(self.df)):
            if "MEMUTUSKAN:" in str(self.df.iloc[i]['text']):
                for j in range(i + 1, len(self.df)):
                    if "Menetapkan :" in str(self.df.iloc[j]['text']):
                        content = [re.sub(r"^Menetapkan\s*:\s*", "", str(self.df.iloc[j]['text']).strip(), flags=re.IGNORECASE)]
                        k = j + 1
                        while k < len(self.df):
                            if re.match(r"^(Pasal|BAB)\s+", str(self.df.iloc[k]['text']), re.IGNORECASE): break
                            content.append(str(self.df.iloc[k]['text']).strip()); k += 1
                        return pd.DataFrame([{"label": "DIKTUM", "numbering": "MENETAPKAN", "text": " ".join(content)}])
        return pd.DataFrame()

    def process_pasal_autonomous(self):
        """Ekstraksi PASAL."""
        refined_results = []
        i = 0
        while i < len(self.df):
            text = str(self.df.iloc[i]['text']).strip()
            if re.match(r"^Pasal\s+(\d+)", text, re.IGNORECASE) and abs(round(float(self.df.iloc[i]['x0']), 3) - self.X0_PASAL_TITLE) < 1.0:
                num = re.match(r"^Pasal\s+(\d+)", text, re.IGNORECASE).group(1)
                content = []; j = i + 1
                while j < len(self.df):
                    nxt = str(self.df.iloc[j]['text']).strip()
                    if re.match(r"^Pasal\s+\d+", nxt, re.IGNORECASE) and abs(round(float(self.df.iloc[j]['x0']), 3) - self.X0_PASAL_TITLE) < 1.0: break
                    if "Agar setiap orang mengetahuinya" in nxt: break
                    if not re.match(r"^-\s*\d+\s*-$", nxt): content.append(nxt)
                    j += 1
                refined_results.append({"label": "PASAL", "numbering": num, "text": " ".join(content)})
                i = j
            else: i += 1
        return pd.DataFrame(refined_results)

    def process_penutup_autonomous(self):
        """Mengekstrak blok PENUTUP dari kalimat pengundangan hingga akhir."""
        content = []
        start_collecting = False
        print("\n" + "="*50 + "\nDEBUG: START PENUTUP EXTRACTION\n" + "="*50)

        for i, row in self.df.iterrows():
            text = str(row['text']).strip()
            # 1. Pemicu: Kalimat penutup standar atau koordinat penetapan
            if "Agar setiap orang mengetahuinya" in text or "Ditetapkan di" in text:
                start_collecting = True
            
            if start_collecting:
                # 2. Berhenti jika menabrak metadata Berita Negara
                if "BERITA NEGARA" in text.upper():
                    break
                # Abaikan nomor halaman
                if not re.match(r"^-\s*\d+\s*-$", text):
                    content.append(text)
                    print(f"  [COLLECT] Penutup: {text[:40]}...")

        if content:
            return pd.DataFrame([{"label": "PENUTUP", "numbering": "NONE", "text": " ".join(content)}])
        return pd.DataFrame()