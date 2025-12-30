import os
import csv
import pandas as pd
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.legal_parser import LegalParser
from src.utils import load_config

def save_to_json(df, output_path):
    """
    Menyimpan DataFrame ke format JSON dengan urutan key yang kaku:
    label -> numbering -> text.
    """
    if df.empty:
        return
    
    # Memastikan urutan kolom dan tipe data string agar terapit tanda petik
    df_json = df[['label', 'numbering', 'text']].astype(str)
    
    df_json.to_json(
        output_path, 
        orient='records', 
        indent=4, 
        force_ascii=False
    )

def run_pipeline():
    # 1. Inisialisasi Konfigurasi dan Folder
    cfg = load_config()
    s = cfg['settings']
    t = s['thresholds']
    
    input_path = f"data/raw/{s['input_file']}"
    output_folder = "data/processed"
    os.makedirs(output_folder, exist_ok=True)
    file_base = s['input_file'].replace('.pdf', '')

    print(f"[*] Memulai Pipeline: {s['input_file']}")

    # 2. Tahap Scraping & Feature Engineering (Master Data)
    # Mengekstrak baris teks beserta 16 kolom metadata koordinat
    print("[1/4] Mengekstrak fitur spasial dari PDF...")
    extractor = PDFExtractor(input_path, s['page_range'])
    raw_data = extractor.extract_raw_data()
    df_features = FeatureProcessor(raw_data).process_features()
    
    # 3. Tahap Labeling Awal
    # Memberikan label awal berdasarkan state machine di classifier.py
    classifier = LayoutClassifier(df_features, t)
    df_labeled = classifier.apply_labels()
    
    # Simpan LABELED_ALL (Source of Truth untuk debugging)
    master_path = f"{output_folder}/LABELED_ALL_{file_base}.csv"
    df_labeled.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL)
    print(f"[+] Master CSV Berhasil: {master_path}")

    # 4. Inisialisasi Parser untuk Refinement Otonom
    parser = LegalParser(df_labeled)

    # --- PROSES KONSIDERAN ---
    print("[2/4] Menjalankan Refinement Otonom: KONSIDERAN...")
    df_kon = parser.process_konsideran_autonomous()
    if not df_kon.empty:
        # Simpan CSV KONSIDERAN
        df_kon.to_csv(f"{output_folder}/KONSIDERAN_{file_base}.csv", index=False, quoting=csv.QUOTE_ALL)
        # Simpan JSON KONSIDERAN
        save_to_json(df_kon, f"{output_folder}/KONSIDERAN_{file_base}.json")
        print(f"[+] Output KONSIDERAN Selesai.")
    else:
        print("[!] KONSIDERAN tidak ditemukan atau gagal diekstrak.")

    # --- PROSES DASAR HUKUM ---
    print("[3/4] Menjalankan Refinement Otonom: DASAR HUKUM...")
    df_dh = parser.process_dasar_hukum_autonomous()
    if not df_dh.empty:
        # Simpan CSV DASAR HUKUM
        df_dh.to_csv(f"{output_folder}/DASAR_HUKUM_{file_base}.csv", index=False, quoting=csv.QUOTE_ALL)
        # Simpan JSON DASAR HUKUM
        save_to_json(df_dh, f"{output_folder}/DASAR_HUKUM_{file_base}.json")
        print(f"[+] Output DASAR HUKUM Selesai.")
    else:
        print("[!] DASAR HUKUM tidak ditemukan atau gagal diekstrak.")

    print("[4/4] Pipeline Selesai.")

if __name__ == "__main__":
    run_pipeline()