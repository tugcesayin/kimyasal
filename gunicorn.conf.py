# Render'daki gunicorn bu dosyayı proje klasöründe otomatik olarak bulur ve kullanır.

# Her işçi birden fazla isteği aynı anda karşılayabilsin; böylece yapay zeka
# cevap yazarken site (arama, sayfalar) beklemeye girmez.
worker_class = "gthread"
workers = 1
threads = 8

# Yapay zeka cevapları akış halinde geldiği için uzun sürebilir; 30 sn'de kesilmesin
timeout = 120
keepalive = 5
