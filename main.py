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
    """Menyimpan hasil akhir agregasi ke format JSON terstruktur."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def list_folders_with_file(base_dir, filename):
    """Mendaftar folder yang memiliki file spesifik."""
    if not os.path.exists(base_dir): return []
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) 
            and os.path.isfile(os.path.join(base_dir, d, filename))]

def select_from_list(items, title):
    """Helper interaktif untuk memilih item dari daftar pilihan."""
    if not items:
        print(f"[!] Gagal: Tidak ada data tersedia untuk {title}."); return None
    print(f"\n{'='*45}\n  DAFTAR {title.upper()}\n{'='*45}")
    for idx, item in enumerate(items): print(f" {idx + 1}. {item}")
    print("="*45)
    while True:
        try:
            choice = int(input(f"Pilih nomor (1-{len(items)}): "))
            if 1 <= choice <= len(items): return items[choice - 1]
        except ValueError: pass
        print(f"[!] Masukkan angka valid 1-{len(items)}.")

def display_hierarchy(target_folder):
    """Menampilkan hirarki dokumen (BAB s/d PASAL) ke Terminal."""
    json_path = os.path.join("data/processed", target_folder, "FINAL_STRUCTURED.json")
    if not os.path.exists(json_path):
        print("[!] File JSON tidak ditemukan."); return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'='*60}\n HIRARKI BATANG TUBUH: {target_folder}\n{'='*60}")
    for bab in data.get("C_BATANG_TUBUH", []):
        print(f"\n{bab['bab']}: {bab['judul']}")
        for p in bab.get("pasal", []): print(f"  └── PASAL {p['nomor']}")
        for sec in bab.get("sections", []):
            print(f"  ├── {sec['bagian']}: {sec['judul']}")
            for p in sec.get("pasal", []): print(f"  │   └── PASAL {p['nomor']}")
            for para in sec.get("paragraphs", []):
                print(f"  │   ├── {para['paragraf']}: {para['judul']}")
                for p in para.get("pasal", []): print(f"  │   │   └── PASAL {p['nomor']}")
    print(f"{'='*60}\n")

def run_pipeline():
    # Load konfigurasi dari config.yaml
    cfg = load_config()
    s = cfg['settings']
    t = s['thresholds']
    auto_json = s.get('auto_generate_json', True) # Default True jika tidak ada

    print("\n" + "="*45)
    print("      LEGAL DOCUMENT MANAGEMENT SYSTEM      ")
    print("="*45)
    print(" 1. Proses File Raw (PDF -> Master -> JSON*)")
    print(" 2. Re-proses Master CSV (Master -> JSON)")
    print(" 3. Lihat Hirarki JSON (Terminal Viewer)")
    print("="*45)
    print(f" *Auto-generate JSON: {'AKTIF' if auto_json else 'NON-AKTIF'}")
    print("="*45)
    
    mode = input("Pilih mode (1/2/3): ").strip()

    if mode == "1":
        # JALUR 1: PDF -> MASTER
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        selected_file = select_from_list(raw_files, "File Raw (PDF)")
        if not selected_file: return

        file_name = selected_file.replace('.pdf', '')
        target_dir = os.path.join("data/processed", file_name)
        os.makedirs(target_dir, exist_ok=True)

        print(f"[*] Mengekstraksi PDF: {selected_file}")
        extractor = PDFExtractor(os.path.join("data/raw", selected_file), s['page_range'])
        processed_features = FeatureProcessor(extractor.extract_raw_data()).process_features()
        df_master = LayoutClassifier(processed_features, t).apply_sistematika()
        
        master_path = os.path.join(target_dir, "0. MASTER.csv")
        df_master.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL)
        print(f"[OK] Master CSV dibuat: {master_path}")

        # Cek apakah lanjut ke JSON secara otomatis
        if not auto_json:
            print("[*] Selesai. Silakan lakukan finetuning pada CSV sebelum menjalankan Mode 2.")
            return
        
    elif mode == "2":
        # JALUR 2: MASTER CSV -> JSON
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if not selected_folder: return
        target_dir = os.path.join("data/processed", selected_folder)
        df_master = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"))

    elif mode == "3":
        # JALUR 3: LIHAT HIRARKI
        selected_folder = select_from_list(list_folders_with_file("data/processed", "FINAL_STRUCTURED.json"), "Folder JSON")
        if selected_folder: display_hierarchy(selected_folder)
        return
    else:
        print("[!] Pilihan tidak valid."); return

    # TAHAP VALIDASI & AGREGASI (Mode 1 Auto atau Mode 2)
    print("[*] Validasi data MASTER...")
    validator = MasterValidator(df_master)
    if not validator.run_validation():
        if input("[?] Tetap proses ke JSON meskipun ada error? (y/n): ").lower() != 'y': return

    print("[*] Agregasi ke struktur JSON terorganisir...")
    aggregator = MasterAggregator(df_master, config_meta="config/meta_mapping.yaml")
    final_data = aggregator.run_all()
    
    save_final_json(final_data, os.path.join(target_dir, "FINAL_STRUCTURED.json"))
    print(f"[DONE] JSON tersimpan di: {target_dir}/FINAL_STRUCTURED.json")

if __name__ == "__main__":
    run_pipeline()