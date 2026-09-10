from flask import Flask, render_template, request, jsonify
import pubchempy as pcp
import requests

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


if __name__ == "__main__":
    app.run(debug=False)
    