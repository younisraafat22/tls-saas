with open("backend/app/models.py", "r", encoding="utf-8") as f:
    text = f.read()

new_models = """

class AppRating(Base):
    __tablename__ = "app_ratings"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True, nullable=True)
    rating = Column(Integer, nullable=False) # 1 to 5
    comment = Column(Text, nullable=True)
    source = Column(String, default="website") # website or desktop
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class AppDownload(Base):
    __tablename__ = "app_downloads"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, nullable=True)
    version = Column(String, nullable=True)
    platform = Column(String, nullable=True) # windows, mac, linux
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class FoundAppointment(Base):
    __tablename__ = "found_appointments"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True, nullable=True)
    branch = Column(String, nullable=True)
    service_type = Column(String, nullable=True)
    found_at = Column(DateTime(timezone=True), default=datetime.utcnow)
"""

if "class AppRating" not in text:
    with open("backend/app/models.py", "a", encoding="utf-8") as f:
        f.write(new_models)
    print("Added new models")
else:
    print("Models already exist")
