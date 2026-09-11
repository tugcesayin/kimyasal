from flask import Flask, render_template, request, jsonify
import pubchempy as pcp
import unicodedata

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ara", methods=["POST"])
def ara():
    try:
        data = request.get_json()
        kimyasal = data.get("kimyasal", "").strip()

        if not kimyasal:
            return jsonify({"hata": "Kimyasal adı boş olamaz."})

        compounds = pcp.get_compounds(kimyasal, "name")

        if not compounds:
            return jsonify({"hata": "Kimyasal bulunamadı."})

        c = compounds[0]
        cid = c.cid

        yapi_url = (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            f"compound/cid/{cid}/PNG"
        )

        return jsonify({
            "isim": c.iupac_name or kimyasal,
            "formul": c.molecular_formula,
            "agirlik": str(c.molecular_weight),
            "cid": cid,
            "yapi_url": yapi_url,
            "h_kodlari": [],
            "piktogramlar": []
        })

    except Exception as e:
        return jsonify({"hata": str(e)})


# ----------------------------------------------------
# KARIŞIM GÜVENLİĞİ
# ----------------------------------------------------

def normalize(metin):
    ceviri = str.maketrans({
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "İ": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u"
    })

    return metin.strip().translate(ceviri).casefold()


KIMYASAL_GRUPLARI = {
    "camasir_suyu": {
        "camasir suyu",
        "sodyum hipoklorit",
        "sodium hypochlorite",
        "naocl"
    },

    "asit": {
        "tuz ruhu",
        "hidroklorik asit",
        "hydrochloric acid",
        "hcl",
        "sulfurik asit",
        "sulfuric acid",
        "h2so4",
        "nitrik asit",
        "nitric acid",
        "hno3"
    },

    "amonyak": {
        "amonyak",
        "ammonia",
        "nh3"
    }
}


def kimyasal_grubu_bul(kimyasal):
    kimyasal = normalize(kimyasal)

    for grup, isimler in KIMYASAL_GRUPLARI.items():
        if kimyasal in isimler:
            return grup

    return None


@app.route("/uyumluluk", methods=["POST"])
def uyumluluk():
    try:
        data = request.get_json() or {}

        kimyasal1 = data.get("kimyasal1", "").strip()
        kimyasal2 = data.get("kimyasal2", "").strip()

        if not kimyasal1 or not kimyasal2:
            return jsonify({
                "durum": "uyari",
                "baslik": "Eksik bilgi",
                "mesaj": "Lütfen iki kimyasal adı da girin."
            })

        if normalize(kimyasal1) == normalize(kimyasal2):
            return jsonify({
                "durum": "uyari",
                "baslik": "Aynı kimyasal seçildi",
                "mesaj": "İki alana da aynı kimyasal girildi."
            })

        grup1 = kimyasal_grubu_bul(kimyasal1)
        grup2 = kimyasal_grubu_bul(kimyasal2)

        gruplar = {grup1, grup2}

        # Çamaşır suyu + asit
        if gruplar == {"camasir_suyu", "asit"}:
            return jsonify({
                "durum": "tehlikeli",
                "baslik": "Birlikte kullanılmamalı",
                "mesaj": (
                    "Çamaşır suyu ile asitlerin birlikte kullanılması "
                    "tehlikeli gaz oluşumu riski taşır. "
                    "Bu maddeleri karıştırmayın."
                )
            })

        # Çamaşır suyu + amonyak
        if gruplar == {"camasir_suyu", "amonyak"}:
            return jsonify({
                "durum": "tehlikeli",
                "baslik": "Birlikte kullanılmamalı",
                "mesaj": (
                    "Çamaşır suyu ile amonyak birlikte kullanılmamalıdır. "
                    "Tehlikeli gaz oluşumu riski vardır."
                )
            })

        return jsonify({
            "durum": "bilinmiyor",
            "baslik": "Yeterli uyumluluk verisi yok",
            "mesaj": (
                "Bu iki madde için uygulamanın mevcut veri tabanında "
                "kesin bir uyumluluk kuralı bulunamadı. "
                "Bu sonuç karışımın güvenli olduğu anlamına gelmez. "
                "Ürünlerin SDS/Güvenlik Bilgi Formlarını kontrol edin."
            )
        })

    except Exception as e:
        return jsonify({
            "durum": "hata",
            "baslik": "Hata",
            "mesaj": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=False)