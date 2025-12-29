import pandas as pd
import re

class LegalParser:
    def __init__(self, df, label_to_process):
        # Filter data hanya untuk label yang diminta
        self.df = df[df['label'] == label_to_process].copy()
        self.target_label = label_to_process

    def refine_data(self, prefix_pattern, numbering_pattern):
        """
        prefix_pattern: Regex untuk hapus 'Menimbang :' atau 'Mengingat :'
        numbering_pattern: Regex untuk ambil 'a.' atau '1.'
        """
        refined_rows = []
        current_numbering = None
        
        for index, row in self.df.iterrows():
            text = str(row['text']).strip()
            
            # 1. Bersihkan Prefiks (Menimbang / Mengingat)
            text = re.sub(prefix_pattern, "", text, flags=re.IGNORECASE)
            
            # 2. Deteksi Numbering (a. atau 1.)
            match = re.match(numbering_pattern, text, re.IGNORECASE)
            
            if match:
                current_numbering = match.group(1).lower()
                text_content = match.group(2)
            else:
                text_content = text
            
            refined_rows.append({
                "label": self.target_label,
                "numbering": current_numbering if current_numbering else "",
                "text": text_content
            })
        return pd.DataFrame(refined_rows)

    def group_and_format(self, df):
        # Agregasi teks berdasarkan numbering
        grouped = df.groupby(['label', 'numbering'], sort=False).agg({
            'text': lambda x: ' '.join(x)
        }).reset_index()
        
        # Pastikan urutan kolom: label, numbering, text
        return grouped[['label', 'numbering', 'text']]