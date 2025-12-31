import os
import csv
import json
import pandas as pd
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.aggregator import MasterAggregator
from src.validator import MasterValidator
from src.utils import load_config

def save_final_json(data, output_path):
    """Menyimpan hasil akhir agregasi ke format JSON terstruktur secara permanen."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def list_files(directory, extension):
    """Mendaftar file berdasarkan ekstensi tertentu dalam direktori."""
    if not os.path.exists(directory):
        os.makedirs(directory)
    return [f for f in os.listdir(directory) if f.endswith(extension)]

def list_processed_folders():
    """Mendaftar folder di data/processed yang memiliki file 0. MASTER.csv valid."""
    base_dir = "data/processed"
    if not os.path.exists(base_dir):
        return []
    
    valid_folders = []
    for d in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, d)):
            if os.path.isfile(os.path.join(base_dir, d, "0. MASTER.csv")):
                valid_folders.append(d)
    return valid_folders

def select_from_list(items, title):
    """Helper interaktif untuk memilih item dari daftar pilihan."""
    if not items:
        print(f"[!] Gagal: Tidak ada data tersedia untuk {title}.")
        return None

    print(f"\n{'='*45}\n  DAFTAR {title.upper()}\n{'='*45}")
    for idx, item in enumerate(items):
        print(f" {idx + 1}. {item}")
    print("="*45)

    while True:
        try:
            choice = int(input(f"Pilih nomor (1-{len(items)}): "))
            if 1 <= choice <= len(items):
                return items[choice - 1]
        except ValueError:
            pass
        print(f"[!] Masukkan angka valid 1-{len(items)}.")

def run_pipeline():
    """Fungsi utama pengendali alur Ekstraksi, Validasi, dan Agregasi."""
    cfg = load_config()
    s = cfg['settings']
    t = s['thresholds']

    print("\n" + "="*45)
    print("      LEGAL DOCUMENT PARSER SYSTEM      ")
    print("="*45)
    print(" 1. Proses File Raw (PDF -> Master -> JSON)")
    print(" 2. Re-proses Master CSV (Master -> JSON)")
    print("="*45)
    
    mode = input("Pilih mode (1/2): ").strip()

    df_master = None
    target_dir = ""

    if mode == "1":
        # JALUR 1: Ekstraksi awal dari PDF
        selected_file = select_from_list(list_files("data/raw", ".pdf"), "File Raw (PDF)")
        if not selected_file: return

        file_name = selected_file.replace('.pdf', '')
        target_dir = os.path.join("data/processed", file_name)
        os.makedirs(target_dir, exist_ok=True)

        print(f"[*] Memulai Ekstraksi PDF: {selected_file}")
        extractor = PDFExtractor(os.path.join("data/raw", selected_file), s['page_range'])
        raw_data = extractor.extract_raw_data()
        
        print("[*] Melabeli sistematika baris dan membangun Master Data...")
        processed_features = FeatureProcessor(raw_data).process_features()
        df_master = LayoutClassifier(processed_features, t).apply_sistematika()
        
        master_path = os.path.join(target_dir, "0. MASTER.csv")
        df_master.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL)
        print(f"[OK] Master CSV berhasil dibuat: {master_path}")
        print("[!] Anda dapat melakukan koreksi manual pada file CSV tersebut sebelum lanjut.")

    elif mode == "2":
        # JALUR 2: Mengolah Master CSV hasil finetuning manusia
        selected_folder = select_from_list(list_processed_folders(), "Folder Master CSV")
        if not selected_folder: return

        target_dir = os.path.join("data/processed", selected_folder)
        master_path = os.path.join(target_dir, "0. MASTER.csv")
        
        print(f"[*] Memuat Master CSV dari folder: {selected_folder}")
        df_master = pd.read_csv(master_path)
    
    else:
        print("[!] Pilihan tidak valid. Eksekusi dibatalkan.")
        return

    # TAHAP VALIDASI: Wajib sebelum Agregasi
    print("[*] Menjalankan MasterValidator untuk mengecek integritas data...")
    validator = MasterValidator(df_master)
    if not validator.run_validation():
        print("[!] PERINGATAN: Ditemukan kesalahan kritikal pada data MASTER.")
        cont = input("[?] Tetap paksa proses ke JSON? (y/n): ").lower()
        if cont != 'y':
            print("[*] Proses dihentikan oleh user. Silakan perbaiki Master CSV.")
            return

    # TAHAP AGGREGASI AKHIR: Membangun Nested JSON
    print("[*] Memulai Agregasi menjadi Struktur Dokumen Hukum (A, B, C, D)...")
    aggregator = MasterAggregator(df_master, config_meta="config/meta_mapping.yaml")
    final_structured_data = aggregator.run_all()
    
    final_json_path = os.path.join(target_dir, "FINAL_STRUCTURED.json")
    save_final_json(final_structured_data, final_json_path)

    print("\n" + "="*45)
    print("        SELURUH PROSES BERHASIL SELESAI        ")
    print("="*45)
    print(f" Lokasi Output : {target_dir}")
    print(f" Data Master   : 0. MASTER.csv")
    print(f" Data Final    : FINAL_STRUCTURED.json")
    print("="*45)

if __name__ == "__main__":
    run_pipeline()