import os
import csv
from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.legal_parser import LegalParser
from src.utils import load_config

def process_label(df_labeled, label_name, prefix_reg, numbering_reg, output_folder, file_base_name):
    """Fungsi untuk memproses setiap label secara terisolasi"""
    print(f"[*] Memproses kategori: {label_name}")
    
    parser = LegalParser(df_labeled, label_name)
    
    # 1. Refined CSV (Poin 2 Anda: File CSV baru berdasar pengelompokan label)
    df_refined = parser.refine_data(prefix_reg, numbering_reg)
    csv_path = f"{output_folder}/{label_name}_{file_base_name}.csv"
    df_refined.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)
    
    # 2. Grouped JSON (Poin 3 Anda: Pengelompokan sub-label/numbering yang sama)
    df_grouped = parser.group_and_format(df_refined)
    df_grouped = df_grouped.astype(str) # Pastikan semua string agar JSON konsisten
    json_path = f"{output_folder}/{label_name}_{file_base_name}.json"
    df_grouped.to_json(json_path, orient='records', indent=4, force_ascii=False)

def run_pipeline():
    cfg = load_config()
    s = cfg['settings']
    t = s['thresholds']
    input_path = f"data/raw/{s['input_file']}"
    output_folder = "data/processed"
    os.makedirs(output_folder, exist_ok=True)
    file_base = s['input_file'].replace('.pdf', '')

    # --- LANGKAH 1: SCRAPING & LABELING UTAMA ---
    extractor = PDFExtractor(input_path, s['page_range'])
    df_features = FeatureProcessor(extractor.extract_raw_data()).process_features()
    df_labeled = LayoutClassifier(df_features, t).apply_labels()
    
    # SIMPAN MASTER CSV (Ini file yang Anda cari)
    master_path = f"{output_folder}/LABELED_ALL_{file_base}.csv"
    df_labeled.to_csv(master_path, index=False, quoting=csv.QUOTE_ALL)
    print(f"[+] Master Labeled CSV tersimpan di: {master_path}")

    # --- LANGKAH 2 & 3: PROSES PER LABEL (CSV & JSON) ---
    # KONSIDERAN
    process_label(
        df_labeled, 
        "KONSIDERAN", 
        prefix_reg=r"^Menimbang\s*:\s*", 
        numbering_reg=r"^([a-z])\.\s+(.*)", 
        output_folder=output_folder,  # Tambahkan nama argumen
        file_base_name=file_base      # Tambahkan nama argumen
    )

    # DASAR HUKUM
    process_label(
        df_labeled, 
        "DASAR_HUKUM", 
        prefix_reg=r"^Mengingat\s*:\s*", 
        numbering_reg=r"^(\d+)\.\s+(.*)", 
        output_folder=output_folder,  # Tambahkan nama argumen
        file_base_name=file_base      # Tambahkan nama argumen
    )

    # PASAL
    process_label(
        df_labeled, 
        "PASAL", 
        prefix_reg=r"^Pasal\s+", 
        numbering_reg=r"^(\d+)\s*(.*)", 
        output_folder=output_folder,  # Tambahkan nama argumen
        file_base_name=file_base      # Tambahkan nama argumen
    )

if __name__ == "__main__":
    run_pipeline()