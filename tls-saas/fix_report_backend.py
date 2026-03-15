import re

with open('desktop/checker_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_report = '''            # Report result to backend so dashboard shows recent checks
            self._report_to_backend(
                branch_name=getattr(settings, 'branch', '') or '',
                service_type=service_type,
                slots_available=slots_available,
                slot_details=message,
            )'''

new_report = '''            # Report result to backend so dashboard shows recent checks
            self._report_to_backend(
                branch_name=getattr(settings, 'branch', '') or '',
                service_type=service_type,
                slots_available=slots_available,
                slot_details=message,
            )
            
            # Additional ping to metrics endpoint if found
            if slots_available:
                try:
                    import requests
                    requests.post(
                        f"{Config.BACKEND_API_URL}/metrics/appointment-found",
                        json={
                            "user_email": settings.notification_email if settings else "",
                            "branch": getattr(settings, 'branch', '') or '',
                            "service_type": service_type
                        },
                        timeout=5
                    )
                except Exception as e:
                    pass'''
text = text.replace(old_report, new_report)
with open('desktop/checker_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated report backend.")
