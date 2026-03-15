import re

with open("backend/app/api/admin_routes.py", "r", encoding="utf-8") as f:
    text = f.read()

import_pattern = "from app.models import ("
new_import_pattern = "from app.models import (\n    AppRating,\n    AppDownload,\n    FoundAppointment,"
if "AppRating" not in text:
    text = text.replace(import_pattern, new_import_pattern)

stats_query = """    # Desktop license stats"""

new_stats_query = """
    # Platform metrics additions
    total_downloads = (await db.execute(select(func.count(AppDownload.id)))).scalar() or 0
    total_appointments_found = (await db.execute(select(func.count(FoundAppointment.id)))).scalar() or 0
    avg_rating = (await db.execute(select(func.avg(AppRating.rating)))).scalar() or 0.0

    # Desktop license stats"""

text = text.replace(stats_query, new_stats_query)

stats_return = """        pending_license_payments=pending_license_payments,"""

new_stats_return = """        pending_license_payments=pending_license_payments,
        total_downloads=total_downloads,
        total_appointments_found=total_appointments_found,
        average_rating=float(avg_rating),"""

text = text.replace(stats_return, new_stats_return)

with open("backend/app/api/admin_routes.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated admin_routes.py.")
