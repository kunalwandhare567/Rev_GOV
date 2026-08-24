"""
Database & Storage Reset Utility
Deletes the existing SQLite database and uploaded data, then re-initializes
a clean, fresh schema with baseline seed data.
"""
import os
import shutil
import sys

# Ensure backend root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
from main import _seed_database, settings


def reset_database():
    print("🧹 Starting Database and Storage Reset...")

    # 1. Remove SQLite database file
    db_file = "revenue_services.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print(f"  ❌ Deleted database file: {db_file}")
        except Exception as e:
            print(f"  ⚠️ Could not delete {db_file}: {e}")

    # 2. Clean uploaded data folders
    folders_to_clean = [
        settings.STORAGE_PATH,
        settings.RECEIPT_PATH,
        settings.CERTIFICATE_PATH,
        settings.AUDIO_PATH,
        "data/audio/ivr",
        "data/audio/whatsapp",
        "data/uploads",
        "data/ocr_cache",
    ]

    for folder in folders_to_clean:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"  ⚠️ Error clearing {file_path}: {e}")
            print(f"  🧹 Cleared directory: {folder}")
        else:
            os.makedirs(folder, exist_ok=True)
            print(f"  📁 Created directory: {folder}")

    # 3. Re-create all tables
    print("🛠️ Re-creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("  ✅ Database schema created!")

    # 4. Seed baseline data (Admin user, Officer user, Service Catalogue)
    print("🌱 Seeding baseline data...")
    _seed_database()
    print("  ✅ Baseline seed data created!")

    print("\n✨ Database reset COMPLETE! Ready for a fresh start.")


if __name__ == "__main__":
    reset_database()
