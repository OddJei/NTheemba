import os
from dotenv import load_dotenv
load_dotenv()

AUDIT_DATABASE_URL = os.getenv('AUDIT_DATABASE_URL', 'sqlite:///./audit.db')
RETENTION_DAYS = int(os.getenv('AUDIT_RETENTION_DAYS', '90'))
OBJECT_STORAGE_URL = os.getenv('OBJECT_STORAGE_URL')
PORT = int(os.getenv('PORT', os.getenv('AUDIT_PORT', '8290')))
