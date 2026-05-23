import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.utils import secure_filename
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.platypus.tables import TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "gizli_sifre_123"

DB_NAME = "stok.db"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def tablo_olustur():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS urunler(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_adi TEXT,
        stok INTEGER,
        kritik_stok INTEGER,
        foto TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS satislar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri TEXT,
        urun_adi TEXT,
        adet INTEGER,
        tutar REAL
    )
    """)

    try:
        c.execute("ALTER TABLE urunler ADD COLUMN foto TEXT")
    except:
        pass

    conn.commit()
    conn.close()

tablo_olustur()

def giris_kontrol():
    return "kullanici" in session

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["kullanici"] == "admin" and request.form["sifre"] == "1234":
            session["kullanici"] = "admin"
            return redirect("/")
        return render_template("login.html", hata="Kullanıcı adı veya şifre hatalı")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    c = conn.cursor()
    toplam_urun = c.execute("SELECT COUNT(*) FROM urunler").fetchone()[0]
    toplam_stok = c.execute("SELECT SUM(stok) FROM urunler").fetchone()[0] or 0
    kritik = c.execute("SELECT COUNT(*) FROM urunler WHERE stok <= kritik_stok").fetchone()[0]
    conn.close()

    return render_template("index.html", toplam_urun=toplam_urun, toplam_stok=toplam_stok, kritik=kritik)

@app.route("/urunler", methods=["GET", "POST"])
def urunler():
    if not giris_kontrol():
        return redirect("/login")

    if request.method == "POST":
        urun_adi = request.form["urun_adi"]
        stok = int(request.form["stok"])
        kritik_stok = int(request.form["kritik_stok"])

        foto_adi = ""
        foto = request.files.get("foto")

        if foto and foto.filename:
            foto_adi = secure_filename(foto.filename)
            foto.save(os.path.join(app.config["UPLOAD_FOLDER"], foto_adi))

        conn = db()
        conn.execute(
            "INSERT INTO urunler (urun_adi, stok, kritik_stok, foto) VALUES (?, ?, ?, ?)",
            (urun_adi, stok, kritik_stok, foto_adi)
        )
        conn.commit()
        conn.close()

        return redirect("/urunler")

    conn = db()
    urunler = conn.execute("SELECT * FROM urunler ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("urunler.html", urunler=urunler)

@app.route("/ekle", methods=["POST"])
def ekle():
    return urunler()

@app.route("/sil/<int:id>")
def sil(id):
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    conn.execute("DELETE FROM urunler WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect("/urunler")

@app.route("/satis")
def satis():
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    urunler = conn.execute("SELECT * FROM urunler ORDER BY urun_adi ASC").fetchall()
    satislar = conn.execute("SELECT * FROM satislar ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("satis.html", urunler=urunler, satislar=satislar)

@app.route("/satis_ekle", methods=["POST"])
def satis_ekle():
    if not giris_kontrol():
        return redirect("/login")

    urun_id = request.form["urun_id"]
    adet = int(request.form["adet"])
    fiyat = float(request.form["fiyat"])
    musteri = request.form["musteri"]

    conn = db()
    urun = conn.execute("SELECT * FROM urunler WHERE id = ?", (urun_id,)).fetchone()

    if urun and urun["stok"] >= adet:
        conn.execute(
            "INSERT INTO satislar (musteri, urun_adi, adet, tutar) VALUES (?, ?, ?, ?)",
            (musteri, urun["urun_adi"], adet, fiyat)
        )

        conn.execute(
            "UPDATE urunler SET stok = stok - ? WHERE id = ?",
            (adet, urun_id)
        )

        conn.commit()

    conn.close()
    return redirect("/satis")

@app.route("/stok")
def stok():
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    urunler = conn.execute("SELECT * FROM urunler ORDER BY urun_adi ASC").fetchall()
    conn.close()

    return render_template("stok.html", urunler=urunler)

@app.route("/raporlar")
def raporlar():
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    c = conn.cursor()
    toplam_urun = c.execute("SELECT COUNT(*) FROM urunler").fetchone()[0]
    toplam_stok = c.execute("SELECT SUM(stok) FROM urunler").fetchone()[0] or 0
    kritik = c.execute("SELECT COUNT(*) FROM urunler WHERE stok <= kritik_stok").fetchone()[0]
    conn.close()

    return render_template("raporlar.html", toplam_urun=toplam_urun, toplam_stok=toplam_stok, kritik=kritik)

@app.route("/excel_indir")
def excel_indir():
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    df = pd.read_sql_query("""
        SELECT urun_adi AS Ürün, stok AS Stok, kritik_stok AS Kritik
        FROM urunler
    """, conn)

    dosya = "stok_raporu.xlsx"
    df.to_excel(dosya, index=False)
    conn.close()

    return send_file(dosya, as_attachment=True)

@app.route("/pdf_rapor")
def pdf_rapor():
    if not giris_kontrol():
        return redirect("/login")

    conn = db()
    urunler = conn.execute("SELECT * FROM urunler ORDER BY id ASC").fetchall()
    conn.close()

    dosya = "stok_raporu.pdf"
    pdf = SimpleDocTemplate(dosya)
    stiller = getSampleStyleSheet()

    elemanlar = []
    elemanlar.append(Paragraph("VİZYON STOK RAPORU", stiller["Title"]))
    elemanlar.append(Spacer(1, 20))

    veri = [["ID", "Ürün", "Stok", "Kritik"]]

    for u in urunler:
        veri.append([u["id"], u["urun_adi"], u["stok"], u["kritik_stok"]])

    tablo = Table(veri)
    tablo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.gold),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    elemanlar.append(tablo)
    pdf.build(elemanlar)

    return send_file(dosya, as_attachment=True)

@app.route("/uretim")
def uretim():
    if not giris_kontrol():
        return redirect("/login")
    return render_template("uretim.html")

@app.route("/sevkiyat")
def sevkiyat():
    if not giris_kontrol():
        return redirect("/login")
    return render_template("sevkiyat.html")

@app.route("/cari")
def cari():
    if not giris_kontrol():
        return redirect("/login")
    return render_template("cari.html")

if __name__ == "__main__":
    app.run(debug=True)