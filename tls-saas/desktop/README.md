# TLS Appointment Checker - Windows Application

A modern Windows desktop application for monitoring TLS visa appointment availability with automatic notifications.

## Features

✨ **Key Features:**
- 🔐 User authentication with email/password
- 🎁 3-day free trial for new users
- 💎 Premium license system
- ⚙️ Customizable check intervals
- 📧 Email & Windows notifications
- 🔔 Automatic 6-hour status reports
- 📊 Activity dashboard & statistics
- 🎨 Modern glassy Material Design UI
- 🔒 Secure credential storage

## Installation

### 1. Setup Environment

```powershell
# Create .env file from template
copy .env.example .env

# Edit .env and add your admin email credentials
notepad .env
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Initialize Database

```powershell
python -c "from database import init_db; init_db()"
```

### 4. Generate License Keys (Optional)

```powershell
python -c "from database import create_admin_licenses; create_admin_licenses(10)"
```

## Running the Application

```powershell
python main.py
```

## Usage

### First Time Setup

1. **Create Account**: Click "Create New Account" on login screen
2. **Login**: Use your credentials to login
3. **Configure Settings**: Go to Settings and enter:
   - Your TLS email & password
   - Check interval (minutes)
   - Notification preferences
4. **Start Monitoring**: Click "Start Monitoring" on dashboard

### Premium Activation

- Go to Settings
- Enter your license key
- Click "Activate License"

## Configuration (.env file)

```env
# Admin Email for sending notifications
ADMIN_EMAIL=your_email@gmail.com
ADMIN_EMAIL_PASSWORD=your_gmail_app_password

# SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# App Settings
TRIAL_DAYS=3
```

## Building Executable

To create a standalone .exe file:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name="TLS Appointment Checker" --icon=icon.ico main.py
```

The .exe will be in the `dist/` folder.

## Mobile App (Future)

This app uses **Flet** framework, which means the **exact same code** can be compiled for:
- 📱 Android (APK)
- 🍎 iOS (IPA)
- 🌐 Web App

Just change the build target!

## Project Structure

```
TLSAppointmentApp/
├── main.py                    # Main application entry
├── auth_service.py            # Authentication logic
├── checker_service.py         # Background checking service
├── notification_service.py    # Notification handlers
├── database.py                # Database models
├── config.py                  # Configuration
├── requirements.txt           # Dependencies
├── .env                       # Environment variables
└── README.md                  # This file
```

## Troubleshooting

### Email Notifications Not Working
- Make sure you're using a Gmail App Password, not your regular password
- Enable "Less secure app access" if using regular Gmail

### Windows Notifications Not Showing
- Make sure Windows notifications are enabled for Python
- Check Windows notification settings

### Chrome Driver Issues
- The app uses undetected-chromedriver which auto-updates
- If issues persist, manually update Chrome browser

## Security

- All passwords are hashed with bcrypt
- TLS credentials are encrypted in database
- Admin email credentials are never exposed to users
- Database is SQLite (local file)

## License

This is proprietary software. License keys required for commercial use after trial period.

## Support

For issues or questions, contact the developer.
