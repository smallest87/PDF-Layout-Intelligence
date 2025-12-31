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

# --- HELPER FUNCTIONS ---

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

# --- HIERARCHY VIEWER LOGIC ---

def display_hierarchy(target_folder):
    """Menampilkan hirarki dokumen dari JSON ke Terminal."""
    json_path = os.path.join("data/processed", target_folder, "FINAL_STRUCTURED.json")
    if not os.path.exists(json_path):
        print("[!] File JSON tidak ditemukan."); return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print(f" HIRARKI BATANG TUBUH: {target_folder}")
    print(f"{'='*60}")

    bt = data.get("C_BATANG_TUBUH", [])
    for bab in bt:
        print(f"\n{bab['bab']}: {bab['judul']}")
        
        # 1. Pasal langsung di bawah BAB
        for p in bab.get("pasal", []):
            print(f"  └── PASAL {p['nomor']}")
            
        # 2. Iterasi Sections (Bagian)
        for sec in bab.get("sections", []):
            print(f"  ├── {sec['bagian']}: {sec['judul']}")
            
            # Pasal di bawah Bagian
            for p in sec.get("pasal", []):
                print(f"  │   └── PASAL {p['nomor']}")
                
            # 3. Iterasi Paragraphs (Paragraf)
            for para in sec.get("paragraphs", []):
                print(f"  │   ├── {para['paragraf']}: {para['judul']}")
                
                # Pasal di bawah Paragraf
                for p in para.get("pasal", []):
                    print(f"  │   │   └── PASAL {p['nomor']}")
    print(f"\n{'='*60}\n")

# --- MAIN PIPELINE ---

def run_pipeline():
    cfg = load_config()
    s, t = cfg['settings'], cfg['settings']['thresholds']

    print("\n" + "="*45)
    print("      LEGAL DOCUMENT MANAGEMENT SYSTEM      ")
    print("="*45)
    print(" 1. Proses File Raw (PDF -> Master -> JSON)")
    print(" 2. Re-proses Master CSV (Master -> JSON)")
    print(" 3. Lihat Hirarki JSON (Terminal Viewer)")
    print("="*45)
    
    mode = input("Pilih mode (1/2/3): ").strip()

    if mode == "1":
        # JALUR 1: PDF -> MASTER -> JSON
        from src.extractor import PDFExtractor
        raw_files = [f for f in os.listdir("data/raw") if f.endswith('.pdf')]
        selected_file = select_from_list(raw_files, "File Raw (PDF)")
        if not selected_file: return

        file_name = selected_file.replace('.pdf', '')
        target_dir = os.path.join("data/processed", file_name)
        os.makedirs(target_dir, exist_ok=True)

        extractor = PDFExtractor(os.path.join("data/raw", selected_file), s['page_range'])
        df_master = LayoutClassifier(FeatureProcessor(extractor.extract_raw_data()).process_features(), t).apply_sistematika()
        df_master.to_csv(os.path.join(target_dir, "0. MASTER.csv"), index=False, quoting=csv.QUOTE_ALL)
        
        # Lanjut Agregasi
        aggregator = MasterAggregator(df_master)
        with open(os.path.join(target_dir, "FINAL_STRUCTURED.json"), 'w', encoding='utf-8') as f:
            json.dump(aggregator.run_all(), f, indent=4, ensure_ascii=False)

    elif mode == "2":
        # JALUR 2: MASTER CSV -> JSON
        selected_folder = select_from_list(list_folders_with_file("data/processed", "0. MASTER.csv"), "Folder Master CSV")
        if not selected_folder: return

        target_dir = os.path.join("data/processed", selected_folder)
        df_master = pd.read_csv(os.path.join(target_dir, "0. MASTER.csv"))
        
        # Validasi & Agregasi
        validator = MasterValidator(df_master)
        if validator.run_validation() or input("[?] Paksa proses? (y/n): ").lower() == 'y':
            aggregator = MasterAggregator(df_master)
            with open(os.path.join(target_dir, "FINAL_STRUCTURED.json"), 'w', encoding='utf-8') as f:
                json.dump(aggregator.run_all(), f, indent=4, ensure_ascii=False)

    elif mode == "3":
        # JALUR 3: LIHAT HIRARKI
        selected_folder = select_from_list(list_folders_with_file("data/processed", "FINAL_STRUCTURED.json"), "Folder JSON")
        if selected_folder:
            display_hierarchy(selected_folder)
    
    else:
        print("[!] Pilihan tidak valid.")

if __name__ == "__main__":
    run_pipeline()