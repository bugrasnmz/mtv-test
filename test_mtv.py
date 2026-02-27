# test_mtv.py (Chrome‑uyumlu, minimal driver tanımı)
import csv, time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------------------------------------
# 1️⃣ Konfigürasyon (kendi değerlerinizi girin)
# -------------------------------------------------
BASE_URL = "https://ekip.internetsube.intisbank/ekip_retailinternet/index.aspx?M=162070985&S=159215"          # test ortamı URL'si
MENU_PATH = ["Ödemeler", "MTV/Trafik Cezası", "MTV Ödeme"]    # menü hiyerarşisi (link metni)
PLATE = "16Y6042"
PERIOD = "2026"
ITERATIONS = 100                                      # kaç kez çalıştırılacak
REPORT_FILE = Path("service_report.csv")

# -------------------------------------------------
# 2️⃣ Chrome (headless) driver başlatma
# -------------------------------------------------
options = webdriver.ChromeOptions()
options.add_argument("--headless")               # headless mod
options.add_argument("--no-sandbox")             # CI ortamı için gerekli
options.add_argument("--disable-dev-shm-usage")  # bellek sınırlaması
driver = webdriver.Chrome(options=options)      # PATH’te chromedriver bulunduğu için ek parametre gerekmez

# CDP üzerinden network izleme (Chrome da aynı API)
driver.execute_cdp_cmd("Network.enable", {})

network_events = []   # her iteration’da toplanacak
current_iter = 0

def _log_request(event):
    network_events.append({
        "iteration": current_iter,
        "requestId": event["requestId"],
        "url": event["request"]["url"],
        "method": event["request"]["method"],
        "startTime": event["timestamp"],
        "status": None,
        "endTime": None,
        "durationMs": None
    })

def _log_response(event):
    req_id = event["requestId"]
    for rec in network_events:
        if rec["requestId"] == req_id and rec["iteration"] == current_iter:
            rec["status"] = event["response"]["status"]
            rec["endTime"] = event["timestamp"]
            rec["durationMs"] = round((rec["endTime"] - rec["startTime"]) * 1000, 2)
            break

driver.execute_cdp_cmd("Network.addRequestWillBeSentListener", {"listener": _log_request})
driver.execute_cdp_cmd("Network.addResponseReceivedListener", {"listener": _log_response})

wait = WebDriverWait(driver, 20)

# -------------------------------------------------
# 3️⃣ 100 Tekrar Döngüsü
# -------------------------------------------------
try:
    for current_iter in range(1, ITERATIONS + 1):
        driver.get(BASE_URL)

        # Menü gezin
        for item in MENU_PATH:
            elem = wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space()='{item}']"))
            )
            elem.click()
            time.sleep(0.3)

        # Form doldur
        plate_input = wait.until(EC.presence_of_element_located((By.ID, "plateInput")))
        period_input = driver.find_element(By.ID, "periodInput")
        plate_input.clear(); plate_input.send_keys(PLATE)
        period_input.clear(); period_input.send_keys(PERIOD)

        # Sorgula
        driver.find_element(By.XPATH, "//button[normalize-space()='Sorgula']").click()
        wait.until(EC.visibility_of_element_located((By.ID, "resultTable")))
        time.sleep(1)   # ağ trafiği tamamlanması için

        print(f"✅ Iteration {current_iter}/{ITERATIONS} tamamlandı.")
finally:
    # -------------------------------------------------
    # 4️⃣ CSV raporu oluştur
    # -------------------------------------------------
    with REPORT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f,
                                fieldnames=["iteration", "url", "method", "status", "durationMs"])
        writer.writeheader()
        for rec in network_events:
            if rec["url"].startswith(BASE_URL):
                writer.writerow({
                    "iteration": rec["iteration"],
                    "url": rec["url"],
                    "method": rec["method"],
                    "status": rec["status"],
                    "durationMs": rec["durationMs"]
                })

    print(f"\n📊 Rapor oluşturuldu: {REPORT_FILE.resolve()}\n")
    driver.quit()