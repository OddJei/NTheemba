# Ntheemba Auth Service

## Overview
The Ntheemba Auth Service is a microservice designed to handle user authentication and authorization for the Ntheemba platform. It provides functionalities such as user registration, login, OTP verification, and role management.

## Project Structure
```
ntheemba-auth-service/
├── src/
│   └── ntheemba_auth/
│       ├── api/                  # API related code
│       │   └── v1/               # Version 1 of the API
│       ├── services/              # Business logic services
│       ├── repositories/          # Data access layer
│       ├── models/                # Database models
│       ├── schemas/               # Data validation schemas
│       ├── utils/                 # Utility functions
│       ├── adapters/              # External service adapters
│       ├── middlewares/           # Middleware components
│       ├── core/                  # Core application settings
│       ├── db/                    # Database setup
│       └── main.py                # Entry point for the application
├── migrations/                     # Database migration scripts
├── tests/                          # Test suite
├── .env.example                    # Example environment variables
├── .gitignore                      # Git ignore file
├── alembic.ini                     # Alembic configuration
├── pyproject.toml                  # Project metadata
└── requirements.txt                # Project dependencies
```

## Features
- **User Management**: Register and manage user accounts, including roles and permissions.
- **Authentication**: Secure login and OTP verification for user sessions.
- **Role-Based Access**: Different access levels for users, staff, and affiliates.
- **Integration**: Ability to integrate with external messaging services for OTP delivery.

## Getting Started
1. Clone the repository:
   ```
   git clone <repository-url>
   cd ntheemba-auth-service
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up the environment variables:
   - Copy `.env.example` to `.env` and fill in the required values.

5. Run the application:
   ```
   uvicorn src.ntheemba_auth.main:app --reload
   ```

## Testing
To run the tests, use:
```
pytest tests/
```

## License
This project is licensed under the MIT License. See the LICENSE file for details.