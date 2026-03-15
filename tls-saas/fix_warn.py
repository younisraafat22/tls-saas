content = open('backend/app/api/admin_routes.py', encoding='utf-8').read()
content = content.replace('deleted\_%', r'deleted\_%')
open('backend/app/api/admin_routes.py', 'w', encoding='utf-8').write(content)
