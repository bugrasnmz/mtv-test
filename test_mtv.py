import csv
import json
import os
import shlex
import statistics
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def getenv_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def getenv_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


BASE_URL = getenv_str(
    "MTV_BASE_URL",
    "https://ekip.internetsube.intisbank/ekip_retailinternet/index.aspx?M=162070985&S=159215",
)
MENU_PATH = [
    item.strip()
    for item in getenv_str("MTV_MENU_PATH", "Ödemeler|MTV/Trafik Cezası|MTV Ödeme").split("|")
    if item.strip()
]
PLATE = getenv_str("MTV_PLATE", "16Y6042")
PERIOD = getenv_str("MTV_PERIOD", "2026")
ITERATIONS = max(getenv_int("MTV_ITERATIONS", 100), 1)
WAIT_TIMEOUT = max(getenv_int("MTV_WAIT_TIMEOUT_SECONDS", 20), 1)
REPORT_FILE = Path(getenv_str("MTV_REPORT_FILE", "service_report.csv"))
CHROME_FLAGS = getenv_str("CHROME_FLAGS", "--headless=new --no-sandbox --disable-dev-shm-usage")


def build_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    for flag in shlex.split(CHROME_FLAGS):
        options.add_argument(flag)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return webdriver.Chrome(options=options)


def extract_network_events(raw_logs: list[dict], iteration: int) -> list[dict]:
    parsed_messages = []
    finished_timestamps = {}
    events = []

    for entry in raw_logs:
        try:
            msg = json.loads(entry["message"])["message"]
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
        parsed_messages.append(msg)
        if msg.get("method") == "Network.loadingFinished":
            request_id = msg.get("params", {}).get("requestId")
            timestamp = msg.get("params", {}).get("timestamp")
            if request_id is not None and isinstance(timestamp, (int, float)):
                finished_timestamps[request_id] = timestamp

    for msg in parsed_messages:
        if msg.get("method") != "Network.responseReceived":
            continue

        params = msg.get("params", {})
        response = params.get("response", {})
        request_id = params.get("requestId")
        start_time = (response.get("timing") or {}).get("requestTime")
        end_time = finished_timestamps.get(request_id)

        duration = None
        if isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
            duration = round((end_time - start_time) * 1000, 2)

        events.append(
            {
                "iteration": iteration,
                "url": response.get("url"),
                "status": response.get("status"),
                "durationMs": duration,
            }
        )

    return events


def write_report(records: list[dict]) -> None:
    with REPORT_FILE.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["iteration", "url", "status", "durationMs"])
        writer.writeheader()
        writer.writerows(records)

    durations = [rec["durationMs"] for rec in records if rec["durationMs"] is not None]
    if durations:
        print("\nOzet Istatistikler:")
        print(f"- Ortalama sure: {round(statistics.mean(durations), 2)} ms")
        print(f"- Minimum sure: {round(min(durations), 2)} ms")
        print(f"- Maksimum sure: {round(max(durations), 2)} ms")

    print(f"\nRapor olusturuldu: {REPORT_FILE.resolve()}\n")


def main() -> None:
    network_events = []
    driver = None

    try:
        driver = build_driver()
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        for i in range(1, ITERATIONS + 1):
            driver.get(BASE_URL)

            for item in MENU_PATH:
                elem = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space()='{item}']")))
                elem.click()
                time.sleep(0.3)

            plate_input = wait.until(EC.presence_of_element_located((By.ID, "plateInput")))
            period_input = driver.find_element(By.ID, "periodInput")
            plate_input.clear()
            plate_input.send_keys(PLATE)
            period_input.clear()
            period_input.send_keys(PERIOD)

            driver.find_element(By.XPATH, "//button[normalize-space()='Sorgula']").click()
            wait.until(EC.visibility_of_element_located((By.ID, "resultTable")))
            time.sleep(1)

            logs = driver.get_log("performance")
            network_events.extend(extract_network_events(logs, i))
            print(f"Iteration {i}/{ITERATIONS} tamamlandi.")

    finally:
        write_report(network_events)
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
