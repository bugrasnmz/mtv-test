import csv, time, json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://ekip.internetsube.intisbank/ekip_retailinternet/index.aspx?M=162070985&S=159215"
MENU_PATH = ["Ödemeler", "MTV/Trafik Cezası", "MTV Ödeme"]
PLATE = "16Y6042"
PERIOD = "2026"
ITERATIONS = 100
REPORT_FILE = Path("service_report.csv")

options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

network_events = []

try:
    for i in range(1, ITERATIONS + 1):
        driver.get(BASE_URL)

        for item in MENU_PATH:
            elem = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space()='{item}']")))
            elem.click()
            time.sleep(0.3)

        plate_input = wait.until(EC.presence_of_element_located((By.ID, "plateInput")))
        period_input = driver.find_element(By.ID, "periodInput")
        plate_input.clear(); plate_input.send_keys(PLATE)
        period_input.clear(); period_input.send_keys(PERIOD)

        driver.find_element(By.XPATH, "//button[normalize-space()='Sorgula']").click()
        wait.until(EC.visibility_of_element_located((By.ID, "resultTable")))
        time.sleep(1)

        # Performans loglarını al ve timeout sürelerini hesapla
        logs = driver.get_log("performance")
        for entry in logs:
            msg = json.loads(entry["message"])["message"]
            if msg["method"] == "Network.responseReceived":
                url = msg["params"]["response"]["url"]
                status = msg["params"]["response"]["status"]
                request_id = msg["params"]["requestId"]
                start_time = msg["params"]["response"]["timing"]["requestTime"]

                # loadingFinished event ile duration hesapla
                duration = None
                for e in logs:
                    m = json.loads(e["message"])["message"]
                    if m["method"] == "Network.loadingFinished" and m["params"]["requestId"] == request_id:
                        end_time = m["params"]["timestamp"]
                        duration = round((end_time - start_time) * 1000, 2)
                        break

                network_events.append({
                    "iteration": i,
                    "url": url,
                    "status": status,
                    "durationMs": duration
                })

        print(f"✅ Iteration {i}/{ITERATIONS} tamamlandı.")

finally:
    with REPORT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "url", "status", "durationMs"])
        writer.writeheader()
        for rec in network_events:
            writer.writerow(rec)

    print(f"\n📊 Rapor oluşturuldu: {REPORT_FILE.resolve()}\n")
    driver.quit()
