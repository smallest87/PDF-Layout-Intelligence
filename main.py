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
from src.converter import JSONToHTML
from src.utils import load_config, setup_logging

# --- FUNGSI PEMBANTU (HELPERS) ---

def save_final_json(data, output_path):
    """Menyimpan hasil akhir agregasi ke format JSON terstruktur."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def list_folders_with_file(base_dir, filename):
    """Mendaftar folder di data/processed yang memiliki file spesifik."""
    if not os.path.exists(base_dir): 
        return []
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) 
            and os.path.isfile(os.path.join(base_dir, d, filename))]

def select_from_list(items, title):
    """Helper interaktif untuk memilih item dari daftar di terminal."""
    if not items:
        logging.warning(f"Gagal: Tidak ada data tersedia untuk {title}.")
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

def display_hierarchy(target_folder):
    """Menampilkan hirarki dokumen (BAB s/d PASAL) di Terminal."""
    json_path = os.path.join("data/processed", target_folder, "FINAL_STRUCTURED.json")
    if not os.path.exists(json_path):
        logging.error(f"File JSON tidak ditemukan di: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'='*60}\n HIRARKI BATANG TUBUH: {target_folder}\n{'='*60}")
    for bab in data.get("C_BATANG_TUBUH", []):
        print(f"\n{bab['bab']}: {bab['judul']}")
        for p in bab.get("pasal", []): 
            print(f"  └── PASAL {p['nomor']}")
        for sec in bab.get("sections", []):
            print(f"  ├── {sec['bagian']}: {sec['judul']}")
            for p in sec.get("pasal", []): 
                print(f"  │   └── PASAL {p['nomor']}")
    print(f"{'='*60}\n")

def export_to_html(target_folder):
    """Mengonversi file JSON menjadi tampilan HTML (READABLE_VIEW.html)."""
    json_path = os.path.join("data/processed", target_folder, "FINAL_STRUCTURED.json")
    if not os.path.exists(json_path):
        logging.error(f"Gagal ekspor: File JSON tidak ditemukan di {target_folder}.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # CSS URL diarahkan ke folder terpisah jika diperlukan
    converter = JSONToHTML(data)
    html_content = converter.convert()
    
    output_path = os.path.join("data/processed", target_folder, "READABLE_VIEW.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logging.info(f"HTML Berhasil dibuat: {output_path}")

# --- LOGIKA INTI PEMROSESAN ---

def process_single_pdf(file_name, settings, csv_cfg):
    """Alur eksekusi dari PDF hingga Master CSV."""
    target_dir = os.path.join("data/processed", file_name.replace('.pdf', ''))
    os.makedirs(target_dir, exist_ok=True)

    # 1. Ekstraksi & Feature Engineering
    extractor = PDFExtractor(os.path.join("data/raw", file_name), settings['page_range'])
    raw_data = extractor.extract_raw_data()
    processed_features = FeatureProcessor(raw_data).process_features()
    
    # 2. Klasifikasi Otomatis (Default)
    df_master = LayoutClassifier(processed_features, settings['thresholds']).apply_sistematika()
    
    # 3. Simpan Master CSV
    master_path = os.path.join(target_dir, "0. MASTER.csv")
    df_master.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL, 
                     sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
    
    # 4. Agregasi Otomatis (Jika aktif di config)
    if settings.get('auto_generate_json', True):
        aggregator = MasterAggregator(df_master)
        save_final_json(aggregator.run_all(), os.path.join(target_dir, "FINAL_STRUCTURED.json"))
        return True, "SUCCESS (CSV & JSON)"
    
    return True, "SUCCESS (Hanya CSV)"

# --- MAIN PIPELINE ---

def run_pipeline():
    """Menu Utama Aplikasi dengan fitur pengisian kolom terpisah."""
    cfg = load_config()
    setup_logging(cfg)
    
    s = cfg['settings']
    csv_cfg = {
        'sep': s.get('csv_delimiter', ','), 
        'dec': s.get('csv_decimal', '.')
    }

    logging.info("=== Sesi Aplikasi Dimulai ===")
    print("\n" + "="*45)
    print("      LEGAL DOCUMENT MANAGEMENT SYSTEM      ")
    print("="*45)
    print(" 1. Proses Satu PDF (Full Pipeline)")
    print(" 2. Re-proses Master CSV -> JSON (Agregasi)")
    print(" 3. Lihat Hirarki JSON (Terminal Viewer)")
    print(" 4. BATCH PROCESS: Semua PDF di Folder Raw")
    print(" 5. Export JSON ke HTML (Readable View)")
    print(" 6. UPDATE KOLOM SISTEMATIKA (Tahap 1 PEMBUKAAN)")
    print(" 7. UPDATE KOLOM UNSUR (Mapping Unsur)")
    print("="*45)
    
    mode = input("Pilih mode (1-7): ").strip()

    if mode == "1":
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        selected_file = select_from_list(raw_files, "File Raw (PDF)")
        if selected_file:
            process_single_pdf(selected_file, s, csv_cfg)

    elif mode == "2":
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if selected_folder:
            target_dir = os.path.join("data/processed", selected_folder)
            df_master = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"), sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
            aggregator = MasterAggregator(df_master)
            save_final_json(aggregator.run_all(), os.path.join(target_dir, "FINAL_STRUCTURED.json"))
            logging.info(f"JSON diperbarui untuk: {selected_folder}")

    elif mode == "3":
        selected_folder = select_from_list(list_folders_with_file("data/processed", "FINAL_STRUCTURED.json"), "Folder JSON")
        if selected_folder: display_hierarchy(selected_folder)

    elif mode == "4":
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        for f in raw_files:
            process_single_pdf(f, s, csv_cfg)

    elif mode == "5":
        selected_folder = select_from_list(list_folders_with_file("data/processed", "FINAL_STRUCTURED.json"), "Folder JSON")
        if selected_folder: export_to_html(selected_folder)

    elif mode == "6":
        # Fitur Baru: Hanya update Sistematika
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if selected_folder:
            target_dir = os.path.join("data/processed", selected_folder)
            df = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"), sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
            df = LayoutClassifier(df, s['thresholds']).classify_sistematika()
            df.to_csv(os.path.join(target_dir, "0. MASTER.csv"), index=False, quoting=csv.QUOTE_ALL, sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
            logging.info(f"Kolom Sistematika diperbarui (Tahap 1) di: {selected_folder}")

    elif mode == "7":
        # Fitur Baru: Hanya update Unsur
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if selected_folder:
            target_dir = os.path.join("data/processed", selected_folder)
            df = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"), sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
            df = LayoutClassifier(df, s['thresholds']).classify_unsur()
            df.to_csv(os.path.join(target_dir, "0. MASTER.csv"), index=False, quoting=csv.QUOTE_ALL, sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
            logging.info(f"Kolom Unsur diperbarui di: {selected_folder}")

if __name__ == "__main__":
    run_pipeline()