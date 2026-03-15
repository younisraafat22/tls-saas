content = open('backend/app/main.py', encoding='utf-8').read()
content = content.replace("from app.models import (", "from app.models import (\n    AppRating, AppDownload, FoundAppointment,")
open('backend/app/main.py', 'w', encoding='utf-8').write(content)
