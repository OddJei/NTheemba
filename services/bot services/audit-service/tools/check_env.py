from dotenv import find_dotenv, load_dotenv
import os
p = find_dotenv()
print('find_dotenv ->', repr(p))
if p:
    load_dotenv(p)
print('PG_USER=', repr(os.getenv('PG_USER')))
print('PG_PASSWORD=', repr(os.getenv('PG_PASSWORD')))
print('PG_DB=', repr(os.getenv('PG_DB')))
print('PG_HOST=', repr(os.getenv('PG_HOST')))
print('AUDIT_DATABASE_URL=', repr(os.getenv('AUDIT_DATABASE_URL')))
print('CWD=', repr(os.getcwd()))
