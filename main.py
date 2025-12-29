from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.utils import load_config
import os
import csv

def run_pipeline():
    # 1. Load Config
    cfg = load_config()
    s = cfg['settings']
    t = cfg['settings']['thresholds'] # Ambil bagian thresholds
    
    input_path = f"data/raw/{s['input_file']}"
    output_folder = "data/processed"
    os.makedirs(output_folder, exist_ok=True)
    
    output_path = f"{output_folder}/LABELED_{s['input_file'].replace('.pdf', '.csv')}"

    # 2. Ekstraksi
    extractor = PDFExtractor(input_path, s['page_range'])
    raw_data = extractor.extract_raw_data()
    
    # 3. Fitur Engineering
    processor = FeatureProcessor(raw_data)
    df_features = processor.process_features()
    
    # 4. Klasifikasi Dinamis
    print(f"[*] Menjalankan klasifikasi dengan center_limit: {t['center_limit']}")
    classifier = LayoutClassifier(df_features, t)
    final_df = classifier.apply_labels()
    
    # 5. Simpan Hasil Akhir
    # Untuk memaksa semua teks menggunakan tanda petik
    final_df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL)
    print(f"[+] Selesai! Hasil akhir: {output_path}")

if __name__ == "__main__":
    run_pipeline()