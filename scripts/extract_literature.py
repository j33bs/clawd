import sys
import os
from pypdf import PdfReader

def extract_text(pdf_path, output_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        print(f"Extracting from {pdf_path} ({len(reader.pages)} pages)...")
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        
        # Basic cleanup
        # (Could add more heuristics here to remove headers/footers)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error extracting {pdf_path}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 extract_literature.py <pdf_path> <output_path>")
        sys.exit(1)
    
    extract_text(sys.argv[1], sys.argv[2])
