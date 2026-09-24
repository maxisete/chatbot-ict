from pathlib import Path
from pypdf import PdfReader

def ver_texto_pdf(pdf_path: Path, paginas: range):
    reader = PdfReader(pdf_path)
    for i in paginas:
        print(f"\n{'='*60}")
        print(f"PÁGINA {i+1}")
        print('='*60)
        print(reader.pages[i].extract_text())

if __name__ == "__main__":
    # Miramos las páginas donde están las tablas del R.D.
    ver_texto_pdf(
        Path("data/pdfs/R.D. 346 2011 de 11 de Marzo.pdf"),
        range(60, 65)
    )
