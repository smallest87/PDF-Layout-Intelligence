import json
import os

class JSONToHTML:
    def __init__(self, json_data):
        """Inisialisasi dengan data JSON hasil agregasi."""
        self.data = json_data

    def _render_rincian(self, rincian_list):
        """Me-render daftar rincian (poin a, b, c). Menghilangkan tanda titik jika nomor kosong."""
        if not rincian_list:
            return ""
            
        html = '<div class="rincian-container">'
        for item in rincian_list:
            isi = item.get("teks") or item.get("definisi")
            nomor = item.get("nomor", "")
            
            # Jika nomor kosong (paragraf tunggal), tampilkan tanpa indentasi angka
            if nomor == "":
                html += f'<p class="isi-paragraf">{isi}</p>'
            else:
                html += f'<div class="poin"><span class="nomor-poin">{nomor}.</span> <span class="teks-poin">{isi}</span></div>'
        html += '</div>'
        return html

    def _render_ayat_atau_rincian(self, content):
        """Me-render konten pasal baik berupa ayat-ayat atau rincian teks."""
        if isinstance(content, str):
            return f'<p class="isi-pasal">{content}</p>'
            
        html = ""
        if "ayat" in content and content["ayat"]:
            if content.get("teks_pembuka"):
                html += f'<p class="isi-pasal">{content["teks_pembuka"]}</p>'
            for ay in content["ayat"]:
                html += f'<div class="ayat-row"><span class="nomor-ayat">({ay["ayat"]})</span> <div class="isi-ayat">{self._render_rincian(ay["teks"]["rincian"])}</div></div>'
        elif "rincian" in content:
            if content.get("teks_pembuka"):
                html += f'<p class="isi-pasal">{content["teks_pembuka"]}</p>'
            html += self._render_rincian(content["rincian"])
            
        return html

    def convert(self):
        """Fungsi utama untuk menghasilkan HTML dengan layout Penutup sesuai gambar."""
        html = """
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: 'Bookman Old Style', serif; line-height: 1.5; padding: 50px 80px; color: #000; font-size: 11pt; background-color: #f4f4f4; }
                .page { background: white; padding: 80px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 900px; margin: auto; min-height: 1200px; }
                
                .judul { text-align: center; font-weight: bold; margin-bottom: 40px; text-transform: uppercase; line-height: 1.3; }
                
                /* Layout Kolom Menimbang/Mengingat */
                .legal-row { display: flex; margin-bottom: 10px; align-items: flex-start; }
                .legal-label { min-width: 110px; font-weight: normal; }
                .legal-sep { padding-right: 10px; }
                .legal-content { flex: 1; text-align: justify; }
                
                .centered-bold { text-align: center; font-weight: bold; margin: 10px 0; text-transform: uppercase; }
                .isi-paragraf { margin: 0; padding: 0; text-align: justify; }
                
                /* List & Poin */
                .poin { display: flex; margin-bottom: 5px; text-align: justify; }
                .nomor-poin { font-weight: bold; min-width: 25px; display: inline-block; }
                .teks-poin { flex: 1; }
                
                /* Batang Tubuh */
                .bab { text-align: center; margin-top: 40px; font-weight: bold; text-transform: uppercase; }
                .pasal-container { margin-top: 25px; }
                .pasal-header { font-weight: bold; display: block; text-align: center; margin-bottom: 10px; }
                .ayat-row { display: flex; margin-top: 8px; text-align: justify; }
                .nomor-ayat { min-width: 35px; font-weight: normal; }
                .isi-ayat { flex: 1; }

                /* SEKSI PENUTUP (Sesuai Gambar) */
                .penutup-container { margin-top: 50px; position: relative; width: 100%; }
                
                /* Blok Pengesahan (Kanan Atas) */
                .pengesahan-block { margin-left: auto; width: 45%; text-align: left; margin-bottom: 40px; }
                
                /* Blok Pengundangan (Kiri Bawah) */
                .pengundangan-block { width: 45%; text-align: left; margin-top: 20px; }
                
                .signature-name { font-weight: bold; text-decoration: none; margin-top: 50px; display: block; text-transform: uppercase; }
                .publikasi { margin-top: 30px; font-size: 10pt; text-align: left; }
            </style>
        </head>
        <body>
            <div class="page">
        """

        # 1. SEKSI JUDUL
        jd = self.data.get("A_JUDUL", {})
        html += f'<div class="judul">{jd.get("teks", "")}</div>'

        # 2. SEKSI PEMBUKAAN
        pb = self.data.get("B_PEMBUKAAN", {})
        html += f'<p class="centered-bold">{pb.get("frasa_religius", "")}</p>'
        html += f'<p class="centered-bold">{pb.get("jabatan_pembentuk", "")}</p>'

        html += f'<div class="legal-row"><div class="legal-label">Menimbang</div><div class="legal-sep">:</div>'
        html += f'<div class="legal-content">{self._render_rincian(pb.get("konsiderans", []))}</div></div>'

        html += f'<div class="legal-row"><div class="legal-label">Mengingat</div><div class="legal-sep">:</div>'
        html += f'<div class="legal-content">{self._render_rincian(pb.get("dasar_hukum", []))}</div></div>'

        html += '<div style="margin: 30px 0;">'
        for part in pb.get("diktum", []):
            html += f'<p class="centered-bold">{part}</p>'
        html += '</div>'

        # 3. SEKSI BATANG TUBUH
        for bab in self.data.get("C_BATANG_TUBUH", []):
            html += f'<div class="bab">{bab["bab"]}<br>{bab["judul"]}</div>'
            for pasal in bab.get("pasal", []):
                html += f'<div class="pasal-container"><span class="pasal-header">Pasal {pasal["nomor"]}</span>'
                html += self._render_ayat_atau_rincian(pasal["teks"])
                html += '</div>'

        # 4. SEKSI PENUTUP (Revisi Render Publikasi)
        pn = self.data.get("D_PENUTUP", {})
        pub_data = pn.get("publikasi", [])
        sah = pn.get("pengesahan", {})
        und = pn.get("pengundangan", {})

        # Tambahkan Perintah Pengundangan di atas blok TTD
        perintah = pn.get("perintah_pengundangan", "")
        if perintah and perintah != "NONE":
            html += f'<div class="perintah-pengundangan" style="margin-top: 40px; text-align: justify;">{perintah}</div>'

        html += '<div class="penutup-container">'
        
        # Pengesahan (Blok Kanan)
        html += f"""
        <div class="pengesahan-block">
            <p>Ditetapkan di {sah.get("tempat", "...")}<br>pada tanggal {sah.get("tanggal", "...")}</p>
            <p><b>{sah.get("nama_jabatan", "")},</b></p>
            <p style="margin-top:15px">ttd.</p>
            <span class="signature-name">{sah.get("nama_pejabat", "")}</span>
        </div>
        """

        # Pengundangan (Blok Kiri)
        html += f"""
        <div class="pengundangan-block">
            <p>Diundangkan di {und.get("tempat", "...")}<br>pada tanggal {und.get("tanggal", "...")}</p>
            <p><b>{und.get("nama_jabatan", "")},</b></p>
            <p style="margin-top:15px">ttd.</p>
            <span class="signature-name">{und.get("nama_pejabat", "")}</span>
        </div>
        """

        # Render Publikasi per baris (List of Strings)
        html += '<div class="publikasi" style="margin-top: 40px; line-height: 1.2;">'
        if isinstance(pub_data, list):
            for line in pub_data:
                html += f'<p style="margin: 0; padding: 0;">{line}</p>'
        else:
            html += f'<p>{pub_data}</p>'
        html += '</div>'

        html += "</div></body></html>"
        return html

    def save(self, output_path):
        """Menyimpan hasil konversi ke file HTML."""
        html_content = self.convert()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return output_path