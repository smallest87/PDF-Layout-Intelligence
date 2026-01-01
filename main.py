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

# --- FUNGSI PEMBANTU (HELPERS) ---

def save_final_json(data, output_path):
    """Menyimpan hasil akhir agregasi ke format JSON terstruktur."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def list_folders_with_file(base_dir, filename):
    """Mendaftar folder yang memiliki file spesifik."""
    if not os.path.exists(base_dir): 
        return []
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) 
            and os.path.isfile(os.path.join(base_dir, d, filename))]

def select_from_list(items, title):
    """Helper interaktif untuk memilih item dari daftar pilihan."""
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
    """Menampilkan hirarki dokumen (BAB s/d PASAL) ke Terminal."""
    json_path = os.path.join("data/processed", target_folder, "FINAL_STRUCTURED.json")
    if not os.path.exists(json_path):
        logging.error(f"File JSON tidak ditemukan di: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'='*60}\n HIRARKI BATANG TUBUH: {target_folder}\n{'='*60}")
    # Menelusuri Batang Tubuh
    for bab in data.get("C_BATANG_TUBUH", []):
        print(f"\n{bab['bab']}: {bab['judul']}")
        # Pasal langsung di bawah Bab
        for p in bab.get("pasal", []): 
            print(f"  └── PASAL {p['nomor']}")
        # Bagian
        for sec in bab.get("sections", []):
            print(f"  ├── {sec['bagian']}: {sec['judul']}")
            for p in sec.get("pasal", []): 
                print(f"  │   └── PASAL {p['nomor']}")
            # Paragraf
            for para in sec.get("paragraphs", []):
                print(f"  │   ├── {para['paragraf']}: {para['judul']}")
                for p in para.get("pasal", []): 
                    print(f"  │   │   └── PASAL {p['nomor']}")
    print(f"{'='*60}\n")

# --- LOGIKA INTI PEMROSESAN ---

def process_single_pdf(file_name, settings, csv_cfg):
    """Memproses satu PDF dari ekstraksi hingga JSON (jika auto_json aktif)."""
    target_dir = os.path.join("data/processed", file_name.replace('.pdf', ''))
    os.makedirs(target_dir, exist_ok=True)

    # 1. Ekstraksi & Klasifikasi
    extractor = PDFExtractor(os.path.join("data/raw", file_name), settings['page_range'])
    raw_data = extractor.extract_raw_data()
    processed_features = FeatureProcessor(raw_data).process_features()
    df_master = LayoutClassifier(processed_features, settings['thresholds']).apply_sistematika()
    
    # 2. Simpan Master CSV dengan Delimiter dan Desimal Kustom
    master_path = os.path.join(target_dir, "0. MASTER.csv")
    df_master.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL, 
                     sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
    
    # 3. Validasi & Agregasi Otomatis
    if settings.get('auto_generate_json', True):
        validator = MasterValidator(df_master)
        if validator.run_validation():
            aggregator = MasterAggregator(df_master)
            save_final_json(aggregator.run_all(), os.path.join(target_dir, "FINAL_STRUCTURED.json"))
            return True, "SUCCESS (CSV & JSON)"
        return True, "WARNING (JSON dibuat dengan catatan validasi)"
    
    return True, "SUCCESS (Hanya CSV)"

# --- MAIN PIPELINE ---

def run_pipeline():
    # Load konfigurasi dan inisialisasi Logging
    cfg = load_config()
    setup_logging(cfg)
    
    s = cfg['settings']
    csv_cfg = {
        'sep': s.get('csv_delimiter', ','), 
        'dec': s.get('csv_decimal', '.')
    }
    auto_json = s.get('auto_generate_json', True)

    logging.info("=== Sesi Aplikasi Dimulai ===")
    print("\n" + "="*45)
    print("      LEGAL DOCUMENT MANAGEMENT SYSTEM      ")
    print("="*45)
    print(" 1. Proses Satu PDF (Interaktif)")
    print(" 2. Re-proses Master CSV -> JSON (Finetuning)")
    print(" 3. Lihat Hirarki JSON (Terminal Viewer)")
    print(" 4. BATCH PROCESS: Semua PDF di Folder Raw")
    print("="*45)
    print(f" *Format CSV: Delimiter '{csv_cfg['sep']}' | Decimal '{csv_cfg['dec']}'")
    print(f" *Auto-generate JSON: {'AKTIF' if auto_json else 'NON-AKTIF'}")
    print("="*45)
    
    mode = input("Pilih mode (1/2/3/4): ").strip()

    if mode == "1":
        # Mode Interaktif untuk satu file
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        selected_file = select_from_list(raw_files, "File Raw (PDF)")
        if selected_file:
            logging.info(f"Memulai proses interaktif: {selected_file}")
            _, msg = process_single_pdf(selected_file, s, csv_cfg)
            logging.info(f"Selesai: {msg}")

    elif mode == "2":
        # Re-proses CSV hasil koreksi manual
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if selected_folder:
            target_dir = os.path.join("data/processed", selected_folder)
            df_master = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"), 
                                    sep=csv_cfg['sep'], decimal=csv_cfg['dec'])
            
            validator = MasterValidator(df_master)
            if validator.run_validation() or input("[?] Lanjut proses JSON? (y/n): ").lower() == 'y':
                aggregator = MasterAggregator(df_master)
                save_final_json(aggregator.run_all(), os.path.join(target_dir, "FINAL_STRUCTURED.json"))
                logging.info(f"JSON diperbarui untuk: {selected_folder}")

    elif mode == "3":
        # Viewer Hirarki
        selected_folder = select_from_list(list_folders_with_file("data/processed", "FINAL_STRUCTURED.json"), "Folder JSON")
        if selected_folder:
            display_hierarchy(selected_folder)

    elif mode == "4":
        # Batch Processing
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        if not raw_files:
            logging.warning("Tidak ditemukan file PDF di folder data/raw.")
            return

        logging.info(f"Memulai Batch Processing untuk {len(raw_files)} file.")
        stats = {"success": 0, "failed": 0}

        for f in raw_files:
            try:
                logging.info(f"Memproses: {f}...")
                success, msg = process_single_pdf(f, s, csv_cfg)
                if success:
                    stats["success"] += 1
                logging.info(f"Status {f}: {msg}")
            except Exception as e:
                stats["failed"] += 1
                logging.error(f"Gagal memproses {f}: {str(e)}")

        logging.info(f"Batch Selesai. Sukses: {stats['success']}, Gagal: {stats['failed']}")

    else:
        logging.warning("Pilihan mode tidak valid.")

if __name__ == "__main__":
    run_pipeline()