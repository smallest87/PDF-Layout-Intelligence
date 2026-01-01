import json
import os

class JSONToHTML:
    def __init__(self, json_data, css_url="../../../assets/styles.css"):
        """
        Inisialisasi dengan data JSON dan URL/path rujukan CSS.
        css_url: Alamat file CSS (misal: "assets/styles.css" atau "../css/styles.css").
       
        """
        self.data = json_data
        self.css_url = css_url

    def _render_rincian(self, rincian_list):
        """Render poin rincian dengan dukungan indentasi bertingkat."""
        if not rincian_list: return ""
        html = '<div class="rincian-container">'
        for item in rincian_list:
            isi = item.get("teks") or item.get("definisi")
            nomor = item.get("nomor", "")
            cls = "poin sub-poin" if nomor.isdigit() else "poin"
            if nomor == "":
                html += f'<p class="isi-paragraf">{isi}</p>'
            else:
                html += f'<div class="{cls}"><span class="nomor-poin">{nomor}.</span> <span class="teks-poin">{isi}</span></div>'
        return html + '</div>'

    def _render_ayat_atau_rincian(self, content):
        """Render ayat dengan alignment baseline dan dukungan teks_pembuka."""
        if isinstance(content, str): return f'<p class="isi-pasal">{content}</p>'
        html = ""
        if "ayat" in content and content["ayat"]:
            if content.get("teks_pembuka"):
                html += f'<p class="isi-pasal">{content["teks_pembuka"]}</p>'
            for ay in content["ayat"]:
                vd = ay["teks"]
                isi_html = f'<span class="teks-pembuka-ayat">{vd.get("teks_pembuka", "")}</span> ' + self._render_rincian(vd["rincian"])
                html += f'<div class="ayat-row"><span class="nomor-ayat">({ay["ayat"]})</span> <div class="isi-ayat">{isi_html}</div></div>'
        elif "rincian" in content:
            if content.get("teks_pembuka"):
                html += f'<p class="isi-pasal">{content["teks_pembuka"]}</p>'
            html += self._render_rincian(content["rincian"])
        return html

    def _render_pasal_list(self, pasal_list):
        """Render daftar pasal secara sekuensial."""
        html = ""
        for p in pasal_list:
            html += f'<div class="pasal-container"><span class="pasal-header">Pasal {p["nomor"]}</span>{self._render_ayat_atau_rincian(p["teks"])}</div>'
        return html

    def convert(self):
        """Fungsi utama konversi dengan rujukan CSS eksternal (link)."""
        # Menggunakan tag <link> untuk merujuk file CSS di folder terpisah
        html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="{self.css_url}">
</head>
<body>
<div class="page">"""
        
        # 1. SEKSI JUDUL
        jd = self.data.get("A_JUDUL", {})
        html += '<div class="judul-container">'
        teks_jd = jd.get("teks", [])
        if isinstance(teks_jd, list):
            for i, line in enumerate(teks_jd): 
                html += f'<div style="margin-bottom:{"15px" if i==3 else "5px"}">{line}</div>'
        else: 
            html += f'<div>{teks_jd}</div>'
        html += '</div>'

        # 2. SEKSI PEMBUKAAN
        pb = self.data.get("B_PEMBUKAAN", {})
        html += f'<p class="centered-bold">{pb.get("frasa_religius", "")}</p>'
        html += f'<p class="centered-bold">{pb.get("jabatan_pembentuk", "")}</p>'
        
        for l, k in [("Menimbang", "konsiderans"), ("Mengingat", "dasar_hukum")]:
            html += f'<div class="legal-row"><div class="legal-label">{l}</div><div>:</div><div class="legal-content">{self._render_rincian(pb.get(k, []))}</div></div>'
        
        # SEKSI DIKTUM (Perbaikan: Layout Sejajar Horizontal)
        dk = pb.get("diktum", {})
        if "memutuskan" in dk:
            html += f'<p style="margin: 35px 0 25px 0; text-align: center;">{dk["memutuskan"]}</p>'
            html += f"""<div class="legal-row">
                <div class="legal-label">{dk["menetapkan"]["label"]}</div>
                <div>:</div>
                <div class="legal-content">{dk["menetapkan"]["teks"]}</div>
            </div>"""
        else: 
            html += f'<p class="centered-bold">{dk.get("raw", "")}</p>'

        # 3. SEKSI BATANG TUBUH
        for b in self.data.get("C_BATANG_TUBUH", []):
            if b.get("bab") != "ROOT":
                html += f'<div class="bab">{b["bab"]}<br>{b["judul"]}</div>'
            html += self._render_pasal_list(b.get("pasal", []))
            for s in b.get("sections", []):
                html += f'<div class="bagian-header">{s["bagian"]}<br>{s["judul"]}</div>'
                html += self._render_pasal_list(s.get("pasal", []))
                for pg in s.get("paragraphs", []):
                    html += f'<div class="paragraf-header">{pg["paragraf"]}<br>{pg["judul"]}</div>'
                    html += self._render_pasal_list(pg.get("pasal", []))

        # 4. SEKSI PENUTUP
        pn = self.data.get("D_PENUTUP", {})
        perintah = pn.get("perintah_pengundangan", "")
        if perintah != "NONE": 
            html += f'<div style="margin-top: 40px; text-align: justify;">{perintah}</div>'
        
        sah, und = pn.get("pengesahan", {}), pn.get("pengundangan", {})
        html += f"""<div class="penutup-container">
    <div class="pengesahan-block"><p>Ditetapkan di {sah.get("tempat")}<br>pada tanggal {sah.get("tanggal")}</p><p><b>{sah.get("nama_jabatan")},</b></p><p style="margin-top:15px">ttd.</p><span class="signature-name">{sah.get("nama_pejabat")}</span></div>
    <div class="pengundangan-block"><p>Diundangkan di {und.get("tempat")}<br>pada tanggal {und.get("tanggal")}</p><p><b>{und.get("nama_jabatan")},</b></p><p style="margin-top:15px">ttd.</p><span class="signature-name">{und.get("nama_pejabat")}</span></div>
    <div class="publikasi">{"<br>".join(pn.get("publikasi", []))}</div>
</div>"""
        return html + "</div></body></html>"

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f: f.write(self.convert())