"""Offline structural analysis of the downloaded arXiv PDFs.

Extracts the document features used by the classifier (characters, pages,
lines, images) and stores them in a JSON file keyed by arXiv identifier.
"""

import json
import os

import fitz  # PyMuPDF
from tqdm import tqdm


def collect_pdf_files(input_dir):
    """
    Recursively collects the paths of every PDF file under a directory.

    Args:
        input_dir (str): Directory to scan.

    Returns:
        list: Paths of the PDF files found.
    """
    pdf_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files


def count_images_in_pdf(pdf_path):
    """
    Counts the images embedded in a PDF.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        int: Number of images found across all pages.
    """
    doc = fitz.open(pdf_path)
    image_count = 0

    for page in doc:
        images = page.get_images(full=True)
        image_count += len(images)

    return image_count


def extract_pdf_info(pdf_path):
    """
    Extracts information from a PDF: number of characters, pages, lines and images.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        dict or None: The extracted counts, or None if the file cannot be read.
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        num_pages = len(doc)

        for page in doc:
            text += page.get_text("text")

        num_chars = len(text)
        num_lines = text.count("\n") + 1  # Count lines

        return {
            "num_chars": num_chars,
            "num_pages": num_pages,
            "num_lines": num_lines,
            "num_image": count_images_in_pdf(pdf_path)
        }
    except Exception as e:
        print(f"Error with {pdf_path}: {e}")
        return None


def _analyze_pdfs(pdf_files, output_json, description):
    """
    Analyzes a list of PDF files and saves the results as JSON.

    Args:
        pdf_files (list): Paths of the PDF files to analyze.
        output_json (str): Path of the JSON file to write.
        description (str): Label shown on the progress bar.

    Returns:
        dict: The analysis results, keyed by file name without extension.
    """
    results = {}

    with tqdm(total=len(pdf_files), desc=description, unit="pdf") as pbar:
        for pdf_path in pdf_files:
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            info = extract_pdf_info(pdf_path)
            if info:
                results[pdf_name] = info
            pbar.update(1)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    return results


def process_pdfs(input_dir, output_json):
    """
    Recursively scans input_dir, analyzes all PDFs and saves results in a JSON file.

    Args:
        input_dir (str): Directory containing the PDF files.
        output_json (str): Path of the JSON file to write.
    """
    pdf_files = collect_pdf_files(input_dir)
    _analyze_pdfs(pdf_files, output_json, "Analyzing PDFs")
    print(f"Analysis complete. Results saved to {output_json}")


def process_limited_pdfs(input_dir, output_json, limit):
    """
    Scans input_dir, analyzes a limited number of PDFs, and saves the results.

    Args:
        input_dir (str): Directory containing the PDF files.
        output_json (str): Path of the JSON file to write.
        limit (int): Maximum number of PDF files to analyze.
    """
    pdf_files = collect_pdf_files(input_dir)[:limit]
    _analyze_pdfs(pdf_files, output_json, f"Analyzing {limit} PDFs")
    print(f"Analysis of {limit} PDFs complete. Results saved to {output_json}")


def verify_pdf_analysis(input_dir, json_file):
    """
    Checks that every PDF in a folder is present in the analysis JSON file.

    Args:
        input_dir (str): Directory containing the PDF files.
        json_file (str): Path of the JSON file produced by process_pdfs().
    """
    if not os.path.exists(json_file):
        print(f"JSON file {json_file} not found. Please run the analysis first.")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    analyzed_pdfs = set(data.keys())
    all_pdfs = {os.path.splitext(os.path.basename(path))[0]
                for path in collect_pdf_files(input_dir)}

    missing_pdfs = all_pdfs - analyzed_pdfs  # PDFs not in JSON
    extra_pdfs = analyzed_pdfs - all_pdfs    # PDFs in JSON but not in the folder

    if missing_pdfs:
        print("\n MISSING PDFs IN JSON:")
        for pdf in missing_pdfs:
            print(f"- {pdf}.pdf")

    if extra_pdfs:
        print("\n PDFs RECORDED IN JSON BUT NOT FOUND IN FOLDER:")
        for pdf in extra_pdfs:
            print(f"- {pdf}.pdf (exists in {json_file} but not in {input_dir})")

    if not missing_pdfs and not extra_pdfs:
        print("\n All PDFs are correctly recorded in the JSON file.")
