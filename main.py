import os
import csv
import json
import pandas as pd
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.aggregator import MasterAggregator
from src.utils import load_config

def save_final_json(data, output_path):
    """Menyimpan hasil akhir agregasi ke format JSON terstruktur."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def select_raw_file():
    """Menampilkan daftar PDF di data/raw/ dan meminta input user."""
    raw_dir = "data/raw"
    if not os.path.exists(raw_dir):
        os.makedirs(raw_dir)
        
    files = [f for f in os.listdir(raw_dir) if f.endswith('.pdf')]
    
    if not files:
        print("[!] Folder data/raw/ kosong. Silakan masukkan file PDF terlebih dahulu.")
        return None

    print("\n" + "="*45)
    print("      DAFTAR FILE PERATURAN (PDF)      ")
    print("="*45)
    for idx, f in enumerate(files):
        print(f" {idx + 1}. {f}")
    print("="*45)

    while True:
        try:
            choice = int(input(f"Pilih nomor file (1-{len(files)}): "))
            if 1 <= choice <= len(files):
                return files[choice - 1]
            print(f"[!] Masukkan angka antara 1 sampai {len(files)}.")
        except ValueError:
            print("[!] Harap masukkan angka yang valid.")

def run_pipeline():
    """Menjalankan alur Extract -> Classify (MASTER) -> Aggregate (JSON)."""
    # 1. Load Konfigurasi & Thresholds
    cfg = load_config()
    s = cfg['settings']
    t = s['thresholds']
    
    # 2. Seleksi File Interaktif
    selected_file = select_raw_file()
    if not selected_file:
        return

    file_raw_name = selected_file.replace('.pdf', '')
    target_dir = os.path.join("data/processed", file_raw_name)
    os.makedirs(target_dir, exist_ok=True)

    print(f"\n[*] Memulai Pipeline untuk: {selected_file}")
    
    # ---------------------------------------------------------
    # TAHAP 1: EKSTRAKSI & KLASIFIKASI (PEMBUATAN MASTER)
    # ---------------------------------------------------------
    print("[*] Tahap 1: Mengekstraksi fitur dan melabeli baris...")
    
    # Ekstraksi teks mentah dari PDF
    extractor = PDFExtractor(os.path.join("data/raw", selected_file), s['page_range'])
    raw_data = extractor.extract_raw_data()
    
    # Pemrosesan fitur (koordinat, kapitalisasi, dll)
    processed_features = FeatureProcessor(raw_data).process_features()
    
    # Klasifikasi sistematika dan unsur ke dalam DataFrame
    # Hasilnya adalah df_master yang memiliki kolom 'sistematika' dan 'unsur'
    df_master = LayoutClassifier(processed_features, t).apply_sistematika()
    
    # Simpan sebagai 0. MASTER.csv
    master_path = os.path.join(target_dir, "0. MASTER.csv")
    df_master.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL)
    print(f"[OK] File Master berhasil dibuat: {master_path}")

    # ---------------------------------------------------------
    # TAHAP 2: AGGREGASI (PEMBENTUKAN STRUKTUR FINAL)
    # ---------------------------------------------------------
    print("[*] Tahap 2: Mengagregasi baris menjadi struktur UU 12/2011...")
    
    # Inisialisasi Aggregator dengan df_master
    aggregator = MasterAggregator(df_master, config_meta="config/meta_mapping.yaml")
    
    # Menjalankan seluruh proses agregasi (A, B, C, D)
    final_structured_data = aggregator.run_all()
    
    # Simpan hasil akhir ke FINAL_STRUCTURED.json
    final_json_path = os.path.join(target_dir, "FINAL_STRUCTURED.json")
    save_final_json(final_structured_data, final_json_path)

    print(f"\n" + "="*45)
    print(" PROCESS COMPLETED SUCCESSFULLY ")
    print("="*45)
    print(f" Folder Hasil : {target_dir}")
    print(f" Master CSV  : 0. MASTER.csv")
    print(f" Final JSON  : FINAL_STRUCTURED.json")
    print("="*45)

if __name__ == "__main__":
    run_pipeline()