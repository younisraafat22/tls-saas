import re

with open('desktop/checker_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

# In run_check, we want to set self._slots_found_in_current_run = slots_available
old_return = '''            # Keep browser alive — don't call _cleanup_driver() here.
            # The same Chrome session will be reused on the next check cycle
            # so we skip login + CAPTCHA entirely.
            return True  # Check completed successfully'''

new_return = '''            # Keep browser alive — don't call _cleanup_driver() here.
            # The same Chrome session will be reused on the next check cycle
            # so we skip login + CAPTCHA entirely.
            self._slots_found_in_current_run = slots_available
            return True  # Check completed successfully'''
text = text.replace(old_return, new_return)

old_loop_check = '''                # Run check and wait for it to complete
                check_successful = self.run_check(headless_override=None, is_retry=is_retry)

                # Signal UI that check finished (reset before sleep/retry)'''

new_loop_check = '''                # Run check and wait for it to complete
                check_successful = self.run_check(headless_override=None, is_retry=is_retry)

                if getattr(self, '_slots_found_in_current_run', False):
                    self._log("🎉 Session halted because appointments were found!")
                    
                    # Schedule 12-hour reminder timer
                    import threading
                    def send_reminder():
                        db_n = SessionLocal()
                        try:
                            s = db_n.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
                            if s and s.notification_email:
                                notification_service.send_monitoring_reminder(s.notification_email, "Reminder: Appointments are still available.")
                        finally:
                            db_n.close()
                    
                    t = threading.Timer(12 * 3600, send_reminder)
                    t.daemon = True
                    t.start()
                    self._log("🕒 12-hour reminder scheduled in background.")
                    
                    # Store stopped state in DB
                    try:
                        db_s = SessionLocal()
                        s2 = db_s.query(UserSettings).filter(UserSettings.user_id == self.user_id).first()
                        if s2:
                            s2.is_monitoring = False
                            db_s.commit()
                        db_s.close()
                    except Exception as e:
                        pass
                    
                    # Actually stop
                    self.is_running = False
                    
                    # Force UI update if UI callback exists
                    if hasattr(self, 'on_countdown_update') and self.on_countdown_update:
                        self.on_countdown_update(0, 0)
                    self._update_progress("Stopped (Found)", 1.0)
                    break

                # Signal UI that check finished (reset before sleep/retry)'''
text = text.replace(old_loop_check, new_loop_check)

with open('desktop/checker_service.py', 'w', encoding='utf-8') as f:
    f.write(text)
    
print("Modified checker_service.py successfully.")
