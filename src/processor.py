import pandas as pd

class FeatureProcessor:
    def __init__(self, raw_data):
        self.df = pd.DataFrame(raw_data)

    def process_features(self):
        # 1. Menghitung Titik Tengah
        self.df['line_center'] = (self.df['x0'] + self.df['x1']) / 2
        self.df['page_center'] = self.df['page_width'] / 2
        
        # 2. Fitur: Alignment Score (Makin mendekati 0, makin Center)
        # Rumus: $score = \frac{|line\_center - page\_center|}{page\_width}$
        self.df['center_score'] = (abs(self.df['line_center'] - self.df['page_center']) / self.df['page_width'])
        
        # 3. Fitur: Indentasi (Rasio margin kiri)
        self.df['left_ratio'] = self.df['x0'] / self.df['page_width']
        
        # 4. Fitur: Lebar Baris (Rasio terhadap halaman)
        self.df['width_ratio'] = (self.df['x1'] - self.df['x0']) / self.df['page_width']
        
        # 5. Fitur: Deteksi Huruf Kapital (Boolean)
        self.df['is_all_caps'] = self.df['text'].str.isupper()
        
        return self.df