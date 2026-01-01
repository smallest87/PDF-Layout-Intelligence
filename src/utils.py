import yaml
import logging
import os

def load_config(config_path="config.yaml"):
    """Memuat file konfigurasi YAML."""
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def setup_logging(cfg):
    """Inisialisasi sistem logging ke file dan terminal."""
    log_cfg = cfg.get('logging', {})
    log_file = log_cfg.get('log_file', 'logs/process.log')
    log_level = log_cfg.get('log_level', 'INFO')

    # Buat direktori log jika belum ada
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler() # Tetap tampil di terminal
        ]
    )
    logging.info("Sistem Logging Berhasil Diaktifkan.")

def parse_pages(page_string, total_pages):
    """Mengurai rentang halaman."""
    if page_string == "all":
        return list(range(1, total_pages + 1))
    
    pages = set()
    parts = page_string.split(',')
    for part in parts:
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    
    return sorted([p for p in pages if p <= total_pages])