import io

with open("backend/app/main.py", "r", encoding="utf-8") as f:
    content = f.read()

import_statement = "from app.api.desktop_routes import router as desktop_router"
new_import = "from app.api.desktop_routes import router as desktop_router\nfrom app.api.metrics_routes import router as metrics_router"

include_statement = "app.include_router(desktop_router)"
new_include = "app.include_router(desktop_router)\napp.include_router(metrics_router)"

if "metrics_router" not in content:
    content = content.replace(import_statement, new_import)
    content = content.replace(include_statement, new_include)
    with open("backend/app/main.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Added metrics_router")
else:
    print("Already added")
