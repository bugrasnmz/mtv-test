# test_mtv.py
import csv
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------------------------------------
# 1️⃣ Konfigürasyon (değiştirmeniz yeterli)
# -------------------------------------------------
BASE_URL = "https://test-ortam.example.com"          # test ortamı URL'si
MENU_PATH = ["Ana Menü", "Alt Menü", "MTV Sorgu"]    # menü hiyerarşisi (link metni)
PLATE = "34ABC123"
PERIOD = "2024-01"
ITERATIONS = 100                                      # kaç kez çalıştırılacak
REPORT_FILE = Path("service_report.csv")

# -------------------------------------------------
# 2️⃣ Firefox + CDP (Network) başlatma
# -------------------------------------------------
options = Options()
options.headless = True          # GitHub‑Actions’da UI göstermeye gerek yok
driver = webdriver.Firefox(options=options)

# CDP (Chrome‑DevTools‑Protocol) üzerinden network izleme
driver.execute_cdp_cmd("Network.enable", {})

# İstek‑yanıtları tutacak yapı
network_events = []   # her iteration sonunda toplar, sonra CSV’ye yazar

def _log_request(event):
    """requestWillBeSent olayı – başlangıç zamanını kaydet"""
    network_events.append({
        "iteration": current_iter,
        "requestId": event["requestId"],
        "url": event["request"]["url"],
        "method": event["request"]["method"],
        "startTime": event["timestamp"],   # saniye cinsinden
        "status": None,
        "endTime": None,
        "durationMs": None
    })

def _log_response(event):
    """responseReceived + loadingFinished → süreyi hesapla"""
    req_id = event["requestId"]
    for rec in network_events:
        if rec["requestId"] == req_id and rec["iteration"] == current_iter:
            rec["status"] = event["response"]["status"]
            rec["endTime"] = event["timestamp"]
            rec["durationMs"] = round((rec["endTime"] - rec["startTime"]) * 1000, 2)
            break

# Dinleyicileri kaydet (Firefox 115+ CDP destekli)
driver.execute_cdp_cmd("Network.setRequestInterception", {"patterns": [{"urlPattern": "*"}]})
driver.execute_cdp_cmd("Network.addRequestWillBeSentListener", {"listener": _log_request})
driver.execute_cdp_cmd("Network.addResponseReceivedListener", {"listener": _log_response})

wait = WebDriverWait(driver, 20)

# -------------------------------------------------
# 3️⃣ 100 Tekrarı Çalıştır
# -------------------------------------------------
try:
    for current_iter in range(1, ITERATIONS + 1):
        # ---- 3.1 Ana sayfaya git ----
        driver.get(BASE_URL)

        # ---- 3.2 Menü yolunu takip et ----
        for item in MENU_PATH:
            elem = wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space()='{item}']"))
            )
            elem.click()
            time.sleep(0.3)   # UI animasyonları için kısa bekleme

        # ---- 3.3 Sorgu ekranındaki alanları doldur ----
        plate_input = wait.until(
            EC.presence_of_element_located((By.ID, "plateInput"))
        )
        period_input = driver.find_element(By.ID, "periodInput")

        plate_input.clear()
        plate_input.send_keys(PLATE)

        period_input.clear()
        period_input.send_keys(PERIOD)

        # ---- 3.4 Sorgula butonuna tıkla ----
        submit_btn = driver.find_element(
            By.XPATH, "//button[normalize-space()='Sorgula']"
        )
        submit_btn.click()

        # ---- 3.5 Sonuçların gelmesini bekle ----
        wait.until(EC.visibility_of_element_located((By.ID, "resultTable")))
        time.sleep(1)   # ekstra bekleme, ağ trafiğinin tamamlanması için

        # ---- 3.6 Bu iterasyondaki network kayıtlarını CSV’ye ekle ----
        # (network_events listesi zaten iteration numarasıyla doldurulmuş)
        # Bir sonraki iterasyona geçmeden önce kısa temizlik
        # (aynı requestId'ler tekrar kullanılabilir, bu yüzden listede tutuyoruz)
        # İsterseniz burada bir `del network_events[:]` yapıp sadece
        # bir iterasyonun verisini tutabilir, ardından CSV'ye ekleyebilirsiniz.
        # Ancak raporu tek dosyada toplamak istediğimiz için hepsini biriktiriyoruz.

        # (Opsiyonel) her iterasyondan sonra bir log satırı yazdır:
        print(f"✅ Iteration {current_iter}/{ITERATIONS} tamamlandı.")
finally:
    # -------------------------------------------------
    # 4️⃣ Raporu CSV’ye yaz (tek dosyada 100 iterasyon)
    # -------------------------------------------------
    with REPORT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["iteration", "url", "method", "status", "durationMs"]
        )
        writer.writeheader()
        for rec in network_events:
            # Sadece test ortamına ait istekleri tut (BASE_URL ile başlayan)
            if rec["url"].startswith(BASE_URL):
                writer.writerow({
                    "iteration": rec["iteration"],
                    "url": rec["url"],
                    "method": rec["method"],
                    "status": rec["status"],
                    "durationMs": rec["durationMs"]
                })

    print(f"\n📊 Ağ raporu oluşturuldu: {REPORT_FILE.resolve()}\n")
    driver.quit()