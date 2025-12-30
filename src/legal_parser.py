import pandas as pd
import re

class LegalParser:
    def __init__(self, df):
        self.df = df.reset_index(drop=True)
        # Koordinat dasar sebagai referensi (akan dikalibrasi)
        self.X0_MENIMBANG = 70.825
        self.X0_MENGINGAT = 71.025
        self.X0_BODY_TEXT = 198.48
        self._calibrate_coordinates()

    def _calibrate_coordinates(self):
        """Mendeteksi standar koordinat dokumen secara dinamis."""
        print("\n[*] Menjalankan Kalibrasi Koordinat...")
        for i, row in self.df.iterrows():
            text = str(row['text']).strip()
            x0 = round(float(row['x0']), 3)
            
            if "Menimbang" in text:
                self.X0_MENIMBANG = x0
                if i + 1 < len(self.df):
                    # Kalibrasi Body Text dari baris setelah anchor
                    self.X0_BODY_TEXT = round(float(self.df.iloc[i+1]['x0']), 3)
            elif "Mengingat" in text:
                self.X0_MENGINGAT = x0
        
        print(f"    [OK] Anchor Menimbang: {self.X0_MENIMBANG}")
        print(f"    [OK] Anchor Mengingat: {self.X0_MENGINGAT}")
        print(f"    [OK] Standard Body Text: {self.X0_BODY_TEXT}")

    def process_konsideran_autonomous(self):
        """Ekstraksi KONSIDERAN dengan pencarian numbering yang fleksibel."""
        refined_results = []
        i = 0
        total_rows = len(self.df)
        
        def get_next_char(char):
            return chr(ord(char) + 1)

        print("\n" + "="*50)
        print("DEBUG: KONSIDERAN OTONOM (FLEXIBLE NUMBERING)")
        print("="*50)

        while i < total_rows:
            row = self.df.iloc[i]
            text_raw = str(row['text']).strip()
            x0_curr = round(float(row['x0']), 3)

            if "Menimbang" in text_raw and abs(x0_curr - self.X0_MENIMBANG) < 0.5:
                print(f"[FOUND] Pemicu Menimbang ditemukan di x0: {x0_curr}")
                expected_letter = 'a'
                
                while i < total_rows:
                    current_row = self.df.iloc[i]
                    current_text = str(current_row['text']).strip()
                    current_x0 = round(float(current_row['x0']), 3)
                    
                    text_clean = re.sub(r"^Menimbang\s*:\s*", "", current_text, flags=re.IGNORECASE)
                    
                    # LOGIKA BARU: Cari numbering di mana saja di sebelah kiri Body Text
                    pattern = rf"^{expected_letter}\.\s+(.*)"
                    match = re.search(pattern, text_clean, re.IGNORECASE)
                    
                    if match and current_x0 < self.X0_BODY_TEXT:
                        content_start = match.group(1)
                        print(f"  [MATCH] Ketemu '{expected_letter}.' di x0: {current_x0}")
                        
                        collected_text = [content_start]
                        j = i + 1
                        
                        # Ambil teks lanjutan (Body Text)
                        while j < total_rows:
                            next_row = self.df.iloc[j]
                            next_text = str(next_row['text']).strip()
                            next_x0 = round(float(next_row['x0']), 3)
                            
                            # Berhenti jika x0 bergeser kembali ke kiri (potensi numbering baru)
                            if next_x0 < self.X0_BODY_TEXT - 5:
                                break
                            
                            collected_text.append(next_text)
                            j += 1
                        
                        refined_results.append({
                            "label": "KONSIDERAN",
                            "numbering": expected_letter,
                            "text": " ".join(collected_text)
                        })
                        
                        expected_letter = get_next_char(expected_letter)
                        i = j
                    else:
                        # Jika tidak ketemu expected_letter, cek apakah ini akhir blok
                        if expected_letter != 'a': # Sudah pernah ketemu 'a'
                            print(f"[TERMINATE] '{expected_letter}.' tidak ditemukan. Blok selesai.")
                            return pd.DataFrame(refined_results)
                        i += 1
            i += 1
        return pd.DataFrame(refined_results)

    def process_dasar_hukum_autonomous(self):
        """Ekstraksi DASAR HUKUM dengan pencarian numbering yang fleksibel."""
        refined_results = []
        i = 0
        total_rows = len(self.df)
        
        print("\n" + "="*50)
        print("DEBUG: DASAR HUKUM OTONOM (FLEXIBLE NUMBERING)")
        print("="*50)

        while i < total_rows:
            row = self.df.iloc[i]
            text_raw = str(row['text']).strip()
            x0_curr = round(float(row['x0']), 3)

            if "Mengingat" in text_raw and abs(x0_curr - self.X0_MENGINGAT) < 0.5:
                print(f"[FOUND] Pemicu Mengingat ditemukan di x0: {x0_curr}")
                expected_num = 1
                
                while i < total_rows:
                    current_row = self.df.iloc[i]
                    current_text = str(current_row['text']).strip()
                    current_x0 = round(float(current_row['x0']), 3)
                    
                    if re.match(r"^-\s*\d+\s*-$", current_text):
                        i += 1
                        continue

                    text_clean = re.sub(r"^Mengingat\s*:\s*", "", current_text, flags=re.IGNORECASE)
                    pattern = rf"^{expected_num}\.\s+(.*)"
                    match = re.search(pattern, text_clean, re.IGNORECASE)
                    
                    if match and current_x0 < self.X0_BODY_TEXT:
                        content_start = match.group(1)
                        print(f"  [MATCH] Ketemu '{expected_num}.' di x0: {current_x0}")
                        
                        collected_text = [content_start]
                        j = i + 1
                        
                        while j < total_rows:
                            next_row = self.df.iloc[j]
                            next_text = str(next_row['text']).strip()
                            next_x0 = round(float(next_row['x0']), 3)
                            
                            if re.match(r"^-\s*\d+\s*-$", next_text):
                                j += 1
                                continue
                            
                            if next_x0 < self.X0_BODY_TEXT - 5:
                                break
                            
                            collected_text.append(next_text)
                            j += 1
                        
                        refined_results.append({
                            "label": "DASAR_HUKUM",
                            "numbering": str(expected_num),
                            "text": " ".join(collected_text)
                        })
                        
                        expected_num += 1
                        i = j
                    else:
                        if expected_num != 1:
                            print(f"[TERMINATE] '{expected_num}.' tidak ditemukan. Blok selesai.")
                            return pd.DataFrame(refined_results)
                        i += 1
            i += 1
        return pd.DataFrame(refined_results)