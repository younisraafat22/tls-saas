import re

with open("backend/app/schemas.py", "r", encoding="utf-8") as f:
    text = f.read()

new_props = """    pending_license_payments: int = 0
    total_downloads: int = 0
    total_appointments_found: int = 0
    average_rating: float = 0.0"""

text = re.sub(r'    pending_license_payments: int = 0', new_props, text)

with open("backend/app/schemas.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated schemas.")
