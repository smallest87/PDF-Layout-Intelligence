from src.extractor import PDFExtractor
from src.processor import FeatureProcessor
from src.classifier import LayoutClassifier
from src.legal_parser import LegalParser
from src.utils import load_config
import os

def process_label(df_labeled, label_name, prefix_reg, numbering_reg, output_folder, file_base_name):
    print(f"[*] Memproses file untuk label: {label_name}...")
    
    parser = LegalParser(df_labeled, label_name)
    df_refined = parser.refine_data(prefix_reg, numbering_reg)
    df_grouped = parser.group_and_format(df_refined)
    
    # Paksa semua ke string untuk JSON quoting
    df_grouped = df_grouped.astype(str)
    
    # Simpan JSON
    json_path = f"{output_folder}/{label_name}_{file_base_name}.json"
    df_grouped.to_json(json_path, orient='records', indent=4, force_ascii=False)
    print(f"[+] JSON Berhasil: {json_path}")

def run_pipeline():
    cfg = load_config()
    s = cfg['settings']
    t = s['thresholds']
    input_path = f"data/raw/{s['input_file']}"
    output_folder = "data/processed"
    os.makedirs(output_folder, exist_ok=True)
    file_base = s['input_file'].replace('.pdf', '')

    # --- TAHAP 1: EKSTRAKSI & LABELING UTAMA ---
    extractor = PDFExtractor(input_path, s['page_range'])
    df_features = FeatureProcessor(extractor.extract_raw_data()).process_features()
    df_labeled = LayoutClassifier(df_features, t).apply_labels()
    
    # Simpan CSV utama sebagai arsip labeling (Optional)
    df_labeled.to_csv(f"{output_folder}/LABELED_ALL_{file_base}.csv", index=False)

    # --- TAHAP 2: PROSES TERPISAH KONSIDERAN ---
    process_label(
        df_labeled, 
        label_name="KONSIDERAN", 
        prefix_reg=r"^Menimbang\s*:\s*", 
        numbering_reg=r"^([a-z])\.\s+(.*)", 
        output_folder=output_folder,
        file_base_name=file_base
    )

    # --- TAHAP 3: PROSES TERPISAH DASAR HUKUM ---
    process_label(
        df_labeled, 
        label_name="DASAR_HUKUM", 
        prefix_reg=r"^Mengingat\s*:\s*", 
        numbering_reg=r"^(\d+)\.\s+(.*)", # Menggunakan angka \d+
        output_folder=output_folder,
        file_base_name=file_base
    )

if __name__ == "__main__":
    run_pipeline()