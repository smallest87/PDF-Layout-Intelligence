import json
import os

class JSONToHTML:
    def __init__(self, json_data):
        self.data = json_data

    def _render_rincian(self, rincian_list):
        if not rincian_list: return ""
        html = '<div class="rincian-container">'
        for item in rincian_list:
            isi = item.get("teks") or item.get("definisi"); nomor = item.get("nomor", "")
            if nomor == "": html += f'<p class="isi-paragraf">{isi}</p>'
            else: html += f'<div class="poin"><span class="nomor-poin">{nomor}.</span> <span class="teks-poin">{isi}</span></div>'
        return html + '</div>'

    def _render_ayat_atau_rincian(self, content):
        if isinstance(content, str): return f'<p class="isi-pasal">{content}</p>'
        html = ""
        if "ayat" in content and content["ayat"]:
            if content.get("teks_pembuka"): html += f'<p class="isi-pasal">{content["teks_pembuka"]}</p>'
            for ay in content["ayat"]:
                vd = ay["teks"]; isi_html = f'<span class="teks-pembuka-ayat">{vd.get("teks_pembuka", "")}</span> ' + self._render_rincian(vd["rincian"])
                html += f'<div class="ayat-row"><span class="nomor-ayat">({ay["ayat"]})</span> <div class="isi-ayat">{isi_html}</div></div>'
        elif "rincian" in content:
            if content.get("teks_pembuka"): html += f'<p class="isi-pasal">{content["teks_pembuka"]}</p>'
            html += self._render_rincian(content["rincian"])
        return html

    def _render_pasal_list(self, pasal_list):
        html = ""
        for p in pasal_list: html += f'<div class="pasal-container"><span class="pasal-header">Pasal {p["nomor"]}</span>{self._render_ayat_atau_rincian(p["teks"])}</div>'
        return html

    def convert(self):
        """Render HTML dengan Diktum horizontal dan Granular Judul."""
        html = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
            body { font-family: 'Bookman Old Style', serif; line-height: 1.5; padding: 50px 80px; font-size: 11pt; }
            .page { background: white; padding: 80px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 900px; margin: auto; }
            .judul-container { text-align: center; font-weight: bold; margin-bottom: 40px; text-transform: uppercase; }
            .legal-row { display: flex; margin-bottom: 10px; align-items: flex-start; }
            .legal-label { min-width: 110px; font-weight: normal; }
            .legal-sep { padding-right: 10px; }
            .legal-content { flex: 1; text-align: justify; }
            .centered-bold { text-align: center; font-weight: bold; margin: 10px 0; text-transform: uppercase; }
            .poin { display: flex; margin-bottom: 5px; text-align: justify; }
            .nomor-poin { min-width: 25px; }
            .bab { text-align: center; margin-top: 45px; font-weight: bold; text-transform: uppercase; }
            .pasal-header { display: block; text-align: center; margin-bottom: 10px; margin-top: 24px; }
            .ayat-row { display: flex; margin-top: 8px; align-items: baseline; }
            .nomor-ayat { min-width: 35px; }
            .penutup-container { margin-top: 50px; position: relative; width: 100%; }
            .pengesahan-block { margin-left: auto; width: 45%; }
            .pengundangan-block { width: 45%; margin-top: 20px; }
            .signature-name { font-weight: bold; margin-top: 50px; display: block; text-transform: uppercase; }
        </style></head><body><div class="page">"""

        # Render Judul (List of strings dari aggregator)
        jd = self.data.get("A_JUDUL", {})
        html += '<div class="judul-container">'
        for i, line in enumerate(jd.get("teks", [])):
            html += f'<div style="margin-bottom:{"15px" if i==3 else "5px"}">{line}</div>'
        html += '</div>'

        pb = self.data.get("B_PEMBUKAAN", {})
        html += f'<p class="centered-bold">{pb.get("frasa_religius", "")}</p><p class="centered-bold">{pb.get("jabatan_pembentuk", "")}</p>'
        
        # Render Menimbang & Mengingat
        for label, key in [("Menimbang", "konsiderans"), ("Mengingat", "dasar_hukum")]:
            html += f'<div class="legal-row"><div class="legal-label">{label}</div><div class="legal-sep">:</div><div class="legal-content">{self._render_rincian(pb.get(key, []))}</div></div>'
        
        # Render Diktum (Fixed Horizontal Alignment)
        dk = pb.get("diktum", {})
        if "memutuskan" in dk:
            html += f'<p style="margin: 35px 0 25px 0; text-align: center;">{dk["memutuskan"]}</p>'
            html += f"""<div class="legal-row" style="margin-bottom: 30px;">
                <div class="legal-label">{dk["menetapkan"]["label"]}</div>
                <div class="legal-sep">:</div>
                <div class="legal-content">{dk["menetapkan"]["teks"]}</div>
            </div>"""
        else:
            html += f'<p class="centered-bold">{dk.get("raw", "")}</p>'

        # Render Batang Tubuh
        for b in self.data.get("C_BATANG_TUBUH", []):
            html += f'<div class="bab">{b["bab"]}<br>{b["judul"]}</div>'
            html += self._render_pasal_list(b.get("pasal", []))
            for s in b.get("sections", []):
                html += f'<div class="centered-bold" style="margin-top:25px;">{s["bagian"]}<br>{s["judul"]}</div>'
                html += self._render_pasal_list(s.get("pasal", []))

        # Render Penutup
        pn = self.data.get("D_PENUTUP", {})
        perintah = pn.get("perintah_pengundangan", "")
        if perintah != "NONE": html += f'<div style="margin-top:40px; text-align:justify;">{perintah}</div>'
        sah, und = pn.get("pengesahan", {}), pn.get("pengundangan", {})
        html += f"""<div class="penutup-container">
            <div class="pengesahan-block"><p>Ditetapkan di {sah.get("tempat")}<br>pada tanggal {sah.get("tanggal")}</p><p><b>{sah.get("nama_jabatan")},</b></p><p style="margin-top:15px">ttd.</p><span class="signature-name">{sah.get("nama_pejabat")}</span></div>
            <div class="pengundangan-block"><p>Diundangkan di {und.get("tempat")}<br>pada tanggal {und.get("tanggal")}</p><p><b>{und.get("nama_jabatan")},</b></p><p style="margin-top:15px">ttd.</p><span class="signature-name">{und.get("nama_pejabat")}</span></div>
            <div style="margin-top:40px;">{"<br>".join(pn.get("publikasi", []))}</div>
        </div>"""
        return html + "</div></body></html>"

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f: f.write(self.convert())