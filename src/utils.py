import yaml

def load_config(config_path="config.yaml"):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def parse_pages(page_string, total_pages):
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
    
    # Pastikan tidak melebihi total halaman yang ada
    return sorted([p for p in pages if p <= total_pages])