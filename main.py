import os, csv, pandas as pd
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.legal_parser import LegalParser
from src.utils import load_config

def save_to_json(df, output_path):
    if df.empty: return
    df[['label', 'numbering', 'text']].astype(str).to_json(output_path, orient='records', indent=4, force_ascii=False)

def run_pipeline():
    cfg = load_config(); s = cfg['settings']; t = s['thresholds']
    file_raw_name = s['input_file'].replace('.pdf', '')
    target_dir = os.path.join("data/processed", file_raw_name)
    os.makedirs(target_dir, exist_ok=True)

    print(f"[*] Pipeline START: {s['input_file']}")
    extractor = PDFExtractor(f"data/raw/{s['input_file']}", s['page_range'])
    df_labeled = LayoutClassifier(FeatureProcessor(extractor.extract_raw_data()).process_features(), t).apply_labels()
    
    # TAHAP 0. MASTER
    df_labeled.to_csv(os.path.join(target_dir, "0. MASTER.csv"), index=False, quoting=csv.QUOTE_ALL)

    parser = LegalParser(df_labeled)
    
    # Daftar tugas sesuai urutan 1-7 dengan penomoran pada nama file
    tasks = [
        ("1. JUDUL", parser.process_judul_autonomous),
        ("2. PEMBUKAAN", parser.process_pembukaan_religius_autonomous),
        ("3. PEMBUKAAN (KONSIDERAN)", parser.process_konsideran_autonomous),
        ("4. PEMBUKAAN (DASAR HUKUM)", parser.process_dasar_hukum_autonomous),
        ("5. PEMBUKAAN (DIKTUM)", parser.process_diktum_autonomous),
        ("6. BATANG TUBUH", parser.process_batang_tubuh_autonomous),
        ("7. PENUTUP", parser.process_penutup_autonomous)
    ]

    for name, func in tasks:
        print(f"[*] Mengekstrak bagian: {name}")
        df = func()
        if not df.empty:
            csv_path = os.path.join(target_dir, f"{name}.csv")
            json_path = os.path.join(target_dir, f"{name}.json")
            df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)
            save_to_json(df, json_path)

    print(f"[*] Pipeline FINISHED. Seluruh file (0-7) tersimpan di: {target_dir}")

if __name__ == "__main__":
    run_pipeline()