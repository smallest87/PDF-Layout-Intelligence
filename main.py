import os, csv, json, pandas as pd
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.legal_parser import LegalParser
from src.utils import load_config

def save_to_json(df, output_path):
    if df.empty: return
    data = df.to_dict(orient='records')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def select_raw_file():
    """Menampilkan daftar PDF di data/raw/ dan meminta input user."""
    raw_dir = "data/raw"
    files = [f for f in os.listdir(raw_dir) if f.endswith('.pdf')]
    
    if not files:
        print("[!] Folder data/raw/ kosong.")
        return None

    print("\n" + "="*40)
    print(" DAFTAR FILE RAW (PDF)")
    print("="*40)
    for idx, f in enumerate(files):
        print(f" {idx + 1}. {f}")
    print("="*40)

    while True:
        try:
            choice = int(input(f"Pilih nomor file (1-{len(files)}): "))
            if 1 <= choice <= len(files):
                return files[choice - 1]
            print(f"[!] Masukkan angka antara 1 sampai {len(files)}.")
        except ValueError:
            print("[!] Harap masukkan angka yang valid.")

def run_pipeline():
    cfg = load_config(); s = cfg['settings']; t = s['thresholds']
    
    # INTERACTIVE FILE SELECTION
    selected_file = select_raw_file()
    if not selected_file: return

    file_raw_name = selected_file.replace('.pdf', '')
    target_dir = os.path.join("data/processed", file_raw_name)
    os.makedirs(target_dir, exist_ok=True)

    print(f"\n[*] Memulai Pipeline untuk: {selected_file}")
    
    # Ekstraksi Fitur
    extractor = PDFExtractor(os.path.join("data/raw", selected_file), s['page_range'])
    df_labeled = LayoutClassifier(FeatureProcessor(extractor.extract_raw_data()).process_features(), t).apply_labels()
    
    # 0. MASTER
    df_labeled.to_csv(os.path.join(target_dir, "0. MASTER.csv"), index=False, quoting=csv.QUOTE_ALL)

    # Inisialisasi Parser
    parser = LegalParser(df_labeled, config_path="config/meta_mapping.yaml")
    
    # Daftar 1-7
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
            df.to_csv(os.path.join(target_dir, f"{name}.csv"), index=False, quoting=csv.QUOTE_ALL)
            save_to_json(df, os.path.join(target_dir, f"{name}.json"))

    print(f"\n[DONE] Seluruh file (0-7) tersimpan di: {target_dir}")

if __name__ == "__main__":
    run_pipeline()