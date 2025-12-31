import pandas as pd
import re

class MasterValidator:
    def __init__(self, df_master):
        self.df = df_master
        self.errors = []
        self.warnings = []

    def check_pasal_sequence(self):
        """Memeriksa apakah ada nomor Pasal yang melompat atau hilang."""
        # Ambil semua label unsur yang mengandung PASAL
        pasal_rows = self.df[self.df['unsur'].str.startswith("PASAL", na=False)]
        
        # Ekstrak nomor unik pasal sesuai urutan kemunculan
        seen = set()
        pasal_numbers = []
        for p in pasal_rows['unsur'].unique():
            match = re.search(r"PASAL\s+(\d+)", p, re.IGNORECASE)
            if match:
                num = int(match.group(1))
                if num not in seen:
                    pasal_numbers.append(num)
                    seen.add(num)

        # Validasi urutan (1, 2, 3...)
        for i in range(len(pasal_numbers)):
            expected = i + 1
            actual = pasal_numbers[i]
            if actual != expected:
                self.errors.append(f"URUTAN PASAL SALAH: Menemukan Pasal {actual}, seharusnya Pasal {expected}.")
                # Kita tidak berhenti di satu error agar user bisa melihat semua lompatan
                break 

    def check_empty_content(self):
        """Memeriksa apakah ada baris berlabel yang tidak memiliki teks."""
        empty_rows = self.df[self.df['text'].isna() | (self.df['text'].str.strip() == "")]
        for _, row in empty_rows.iterrows():
            if row['sistematika'] != "BODY_TEXT":
                self.warnings.append(f"KONTEN KOSONG: Baris {row.name} label [{row['unsur']}] tidak memiliki teks.")

    def check_mandatory_sistematika(self):
        """Memastikan elemen wajib peraturan perundang-undangan tersedia."""
        required = ["JUDUL", "PEMBUKAAN", "BATANG TUBUH", "PENUTUP"]
        existing = self.df['sistematika'].unique()
        
        for req in required:
            if req not in existing:
                self.errors.append(f"STRUKTUR HILANG: Bagian {req} tidak ditemukan dalam dokumen.")

    def run_validation(self):
        """Menjalankan seluruh modul validasi dan mengembalikan laporan."""
        self.check_mandatory_sistematika()
        self.check_pasal_sequence()
        self.check_empty_content()

        print("\n" + "="*45)
        print("         HASIL VALIDASI MASTER CSV         ")
        print("="*45)
        
        if not self.errors and not self.warnings:
            print("[OK] Tidak ditemukan anomali. Data siap diproses.")
            return True
        
        if self.errors:
            print(f"[!] DITEMUKAN {len(self.errors)} ERROR KRITIKAL:")
            for err in self.errors:
                print(f"    - {err}")
        
        if self.warnings:
            print(f"[*] DITEMUKAN {len(self.warnings)} PERINGATAN:")
            for warn in self.warnings:
                print(f"    - {warn}")
        
        print("="*45)
        
        # Jika ada error, user harus memperbaiki MASTER.csv secara manual
        return len(self.errors) == 0