import json
import os

class JSONToHTML:
    def __init__(self, json_data):
        self.data = json_data

    def _render_rincian(self, rincian_list):
        """Me-render daftar rincian atau definisi."""
        html = '<ul class="rincian-list">'
        for item in rincian_list:
            # Menggunakan key 'definisi' jika ada (fitur auto-labeling)
            isi = item.get("teks") or item.get("definisi")
            html += f'<li><span class="nomor">{item["nomor"]}.</span> {isi}</li>'
        html += '</ul>'
        return html

    def _render_ayat(self, content):
        """Me-render ayat dan rincian di bawahnya secara rekursif."""
        if isinstance(content, str):
            return f'<p>{content}</p>'
        
        html = ""
        if content.get("teks_pembuka"):
            html += f'<p class="pembuka">{content["teks_pembuka"]}</p>'
        
        if "ayat" in content:
            html += '<div class="ayat-container">'
            for a in content["ayat"]:
                html += f'<div class="ayat"><span class="nomor">({a["ayat"]})</span> '
                html += self._render_ayat(a["teks"])
                html += '</div>'
            html += '</div>'
        elif "rincian" in content:
            html += self._render_rincian(content["rincian"])
            
        return html

    def convert(self):
        """Fungsi utama konversi seluruh bagian dokumen."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Bookman Old Style', serif; line-height: 1.6; padding: 40px; color: #333; }}
                .judul {{ text-align: center; font-weight: bold; margin-bottom: 30px; text-transform: uppercase; }}
                .bab {{ text-align: center; margin-top: 40px; border-top: 2px solid #000; padding-top: 20px; }}
                .bagian {{ text-align: center; font-weight: bold; margin-top: 20px; }}
                .paragraf {{ text-align: center; font-style: italic; margin-top: 15px; }}
                .pasal {{ font-weight: bold; margin-top: 25px; display: block; }}
                .ayat {{ margin-left: 20px; margin-top: 5px; }}
                .rincian-list {{ list-style: none; margin-left: 20px; }}
                .nomor {{ font-weight: bold; margin-right: 5px; }}
                .penutup {{ margin-top: 50px; border-top: 1px solid #ccc; padding-top: 20px; }}
                .meta-box {{ background: #f9f9f9; padding: 15px; border: 1px solid #ddd; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
        """

        # A. JUDUL
        jd = self.data.get("A_JUDUL", {})
        html += f'<div class="judul">{jd.get("teks", "")}</div>'

        # B. PEMBUKAAN
        pb = self.data.get("B_PEMBUKAAN", {})
        html += f'<div class="pembukaan">'
        html += f'<p style="text-align:center"><b>{pb.get("frasa_religius", "")}</b></p>'
        html += f'<p style="text-align:center"><b>{pb.get("jabatan_pembentuk", "")}</b></p>'
        html += f'<p><b>Menimbang:</b></p>{self._render_rincian(pb.get("konsiderans", []))}'
        html += f'<p><b>Mengingat:</b></p>{self._render_rincian(pb.get("dasar_hukum", []))}'
        html += f'<p style="text-align:center"><b>MEMUTUSKAN:</b></p>'
        html += f'<p><b>Menetapkan:</b> {pb.get("diktum", "")}</p>'
        html += '</div>'

        # C. BATANG TUBUH
        for bab in self.data.get("C_BATANG_TUBUH", []):
            html += f'<div class="bab"><b>{bab["bab"]}</b><br>{bab["judul"]}</div>'
            for p in bab.get("pasal", []):
                html += f'<span class="pasal">Pasal {p["nomor"]}</span>'
                html += self._render_ayat(p["teks"])
            
            for sec in bab.get("sections", []):
                html += f'<div class="bagian">{sec["bagian"]}<br>{sec["judul"]}</div>'
                for p in sec.get("pasal", []):
                    html += f'<span class="pasal">Pasal {p["nomor"]}</span>'
                    html += self._render_ayat(p["teks"])
                
                for para in sec.get("paragraphs", []):
                    html += f'<div class="paragraf">{para["paragraf"]}<br>{para["judul"]}</div>'
                    for p in para.get("pasal", []):
                        html += f'<span class="pasal">Pasal {p["nomor"]}</span>'
                        html += self._render_ayat(p["teks"])

        # D. PENUTUP
        pt = self.data.get("D_PENUTUP", {})
        html += f'<div class="penutup"><p>{pt.get("teks", "")}</p></div>'
        
        html += "</body></html>"
        return html