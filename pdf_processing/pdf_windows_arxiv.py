"""Browser-automation downloader for arXiv PDFs (Windows).

The arXiv API blocks bulk PDF retrieval behind a CAPTCHA, so this module drives
the default browser's native "Save As" dialog instead, which reproduces a
human-paced download. Because it takes over the keyboard and the mouse focus,
the machine cannot be used while it runs.
"""

import os
import time
import webbrowser

import pyautogui

# Project-relative download directory, shared with the 'PDFPath' field stored in
# MongoDB. Resolved from this file so it does not depend on the shell's cwd.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(PROJECT_ROOT, "data", "pdf")

# A valid article is never this small; anything smaller is a CAPTCHA or error page.
MIN_PDF_SIZE = 100 * 1024  # 100 kB
PAGE_LOAD_DELAY = 5        # Seconds to wait for the PDF to render
DIALOG_DELAY = 0.5         # Seconds to wait for the "Save As" dialog
MAX_ATTEMPTS = 3


def download_arxiv_pdf(arxiv_url, file_number, index):
    """
    Downloads a single arXiv PDF by driving the browser's "Save As" dialog.

    Args:
        arxiv_url (str): The arXiv article URL (e.g. 'https://arxiv.org/abs/2104.12345v2').
        file_number (int): Running count of downloaded files, used for logging.
        index (int): Running count of processed files, used for logging.

    Returns:
        int: 2 if the file was already present, 1 if it was downloaded,
             0 if every attempt failed.
    """
    arxiv_id = arxiv_url.split("/")[-1]
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    file_name = f"{arxiv_id}.pdf"

    os.makedirs(SAVE_DIR, exist_ok=True)
    save_path = os.path.join(SAVE_DIR, file_name)

    if os.path.exists(save_path):
        print(f"File already exists {index}: {save_path}")
        return 2

    for attempt in range(1, MAX_ATTEMPTS + 1):
        webbrowser.open(pdf_url)
        time.sleep(PAGE_LOAD_DELAY)

        # Open the native "Save As" dialog, type the full destination path so the
        # file lands in SAVE_DIR rather than the browser's download folder.
        pyautogui.hotkey('ctrl', 's')
        time.sleep(DIALOG_DELAY)
        pyautogui.write(save_path)
        pyautogui.press('enter')
        time.sleep(DIALOG_DELAY)

        pyautogui.hotkey('ctrl', 'w')  # Close the tab

        if os.path.exists(save_path):
            if os.path.getsize(save_path) >= MIN_PDF_SIZE:
                print(f"PDF {file_number} downloaded successfully: {save_path}")
                return 1
            # Too small to be a real article: discard and try again.
            os.remove(save_path)

        print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed for {arxiv_id} "
              f"(CAPTCHA or network error).")

    print(f"File {arxiv_id} could not be downloaded after {MAX_ATTEMPTS} attempts.")
    return 0
