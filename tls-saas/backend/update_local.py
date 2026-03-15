import sqlite3
import sys

def run_update():
    try:
        c = sqlite3.connect('c:/Users/Younis/Desktop/tls-saas/backend/app/data/tls_saas.db')
        c.execute("UPDATE plans SET price_monthly=400 WHERE plan_type='legalization'")
        c.execute("UPDATE plans SET price_monthly=400 WHERE plan_type='visa'")
        c.execute("UPDATE plans SET price_monthly=750 WHERE plan_type='all_in_one'")
        c.commit()
        print('Local DB updated!')
    except Exception as e:
        print(f'Error local {e}')

run_update()
