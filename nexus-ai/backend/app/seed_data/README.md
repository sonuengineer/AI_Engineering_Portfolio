# NEXUS seed corpus (synthetic)

All companies, people and events here are fictional and generated for the demo.
Text documents live in this folder; PDF/DOCX/XLSX documents are generated at seed time from
`binary_docs.py` so the real extractors (pypdf, python-docx, openpyxl) are exercised.
`suspicious_vendor_note.txt` intentionally contains a prompt-injection attempt to demonstrate
untrusted-document handling.
