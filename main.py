import os
import csv
import pandas as pd
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
    file_base = s['input_file'].replace('.pdf', '')
    output_folder = "data/processed"; os.makedirs(output_folder, exist_ok=True)

    print(f"[*] Pipeline START: {s['input_file']}")
    extractor = PDFExtractor(f"data/raw/{s['input_file']}", s['page_range'])
    df_labeled = LayoutClassifier(FeatureProcessor(extractor.extract_raw_data()).process_features(), t).apply_labels()
    df_labeled.to_csv(f"{output_folder}/LABELED_ALL_{file_base}.csv", index=False, quoting=csv.QUOTE_ALL)

    parser = LegalParser(df_labeled)
    # Urutan proses otonom (ASSD)
    tasks = [
        ("JUDUL", parser.process_judul_autonomous),
        ("KONSIDERAN", parser.process_konsideran_autonomous),
        ("DASAR_HUKUM", parser.process_dasar_hukum_autonomous),
        ("DIKTUM", parser.process_diktum_autonomous),
        ("PASAL", parser.process_pasal_autonomous),
        ("PENUTUP", parser.process_penutup_autonomous)
    ]

    for name, func in tasks:
        print(f"[*] Memproses {name}...")
        df = func()
        if not df.empty:
            df.to_csv(f"{output_folder}/{name}_{file_base}.csv", index=False, quoting=csv.QUOTE_ALL)
            save_to_json(df, f"{output_folder}/{name}_{file_base}.json")

    print("[*] Pipeline FINISHED. Seluruh bagian dokumen hukum telah diekstrak.")

if __name__ == "__main__":
    run_pipeline()