import os
import csv
import json
import logging
import pandas as pd
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.aggregator import MasterAggregator
from src.validator import MasterValidator
from src.utils import load_config, setup_logging

def save_final_json(data, output_path):
    """Menyimpan hasil agregasi ke JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def list_folders_with_file(base_dir, filename):
    """Mendaftar folder dengan file spesifik."""
    if not os.path.exists(base_dir): return []
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) 
            and os.path.isfile(os.path.join(base_dir, d, filename))]

def select_from_list(items, title):
    """Helper seleksi interaktif."""
    if not items:
        logging.warning(f"Tidak ada data tersedia untuk {title}.")
        return None
    print(f"\n{'='*45}\n  DAFTAR {title.upper()}\n{'='*45}")
    for idx, item in enumerate(items): print(f" {idx + 1}. {item}")
    while True:
        try:
            choice = int(input(f"Pilih nomor (1-{len(items)}): "))
            if 1 <= choice <= len(items): return items[choice - 1]
        except ValueError: pass

def display_hierarchy(target_folder):
    """Terminal Viewer Hirarki Batang Tubuh."""
    json_path = os.path.join("data/processed", target_folder, "FINAL_STRUCTURED.json")
    if not os.path.exists(json_path):
        logging.error(f"File JSON tidak ditemukan di {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'='*60}\n HIRARKI: {target_folder}\n{'='*60}")
    for bab in data.get("C_BATANG_TUBUH", []):
        print(f"\n{bab['bab']}: {bab['judul']}")
        for p in bab.get("pasal", []): print(f"  └── PASAL {p['nomor']}")
        for sec in bab.get("sections", []):
            print(f"  ├── {sec['bagian']}: {sec['judul']}")
            for para in sec.get("paragraphs", []):
                print(f"  │   ├── {para['paragraf']}: {para['judul']}")

def run_pipeline():
    cfg = load_config()
    setup_logging(cfg) # Aktifkan logging di awal
    
    s = cfg['settings']
    csv_sep = s.get('csv_delimiter', ',')
    csv_dec = s.get('csv_decimal', '.')
    auto_json = s.get('auto_generate_json', True)

    logging.info("--- Memulai Sesi Baru ---")
    print("\n 1. PDF -> Master\n 2. Master -> JSON\n 3. View Hierarchy")
    mode = input("Pilih mode (1/2/3): ").strip()

    if mode == "1":
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        selected_file = select_from_list(raw_files, "File Raw (PDF)")
        if not selected_file: return

        target_dir = os.path.join("data/processed", selected_file.replace('.pdf', ''))
        os.makedirs(target_dir, exist_ok=True)

        logging.info(f"Ekstraksi PDF dimulai: {selected_file}")
        extractor = PDFExtractor(os.path.join("data/raw", selected_file), s['page_range'])
        df_master = LayoutClassifier(FeatureProcessor(extractor.extract_raw_data()).process_features(), s['thresholds']).apply_sistematika()
        
        master_path = os.path.join(target_dir, "0. MASTER.csv")
        df_master.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL, sep=csv_sep, decimal=csv_dec)
        logging.info(f"Master CSV berhasil disimpan: {master_path}")

        if not auto_json: return
        
    elif mode == "2":
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if not selected_folder: return
        target_dir = os.path.join("data/processed", selected_folder)
        df_master = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"), sep=csv_sep, decimal=csv_dec)
        logging.info(f"Membaca Master CSV dari {selected_folder}")

    elif mode == "3":
        selected_folder = select_from_list(list_folders_with_file("data/processed", "FINAL_STRUCTURED.json"), "Folder JSON")
        if selected_folder: display_hierarchy(selected_folder)
        return

    # Validasi & Agregasi
    validator = MasterValidator(df_master)
    if not validator.run_validation():
        logging.warning("Validasi master gagal, menunggu keputusan user.")
        if input("[?] Lanjut? (y/n): ").lower() != 'y': return

    aggregator = MasterAggregator(df_master)
    final_data = aggregator.run_all()
    save_final_json(final_data, os.path.join(target_dir, "FINAL_STRUCTURED.json"))
    logging.info("JSON Terstruktur berhasil dibuat.")

if __name__ == "__main__":
    run_pipeline()