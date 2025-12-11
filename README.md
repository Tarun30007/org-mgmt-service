# Organization Management Service

A FastAPI + MongoDB backend for managing multi-tenant organizations with secure admin access and dynamic data isolation.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.124.2-green)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)
---
## Features
- Create, update, delete organizations
- Admin login with JWT authentication
- Password hashing with bcrypt
- Dynamic MongoDB collections per organization
- Email validation for admin registration
- Slugified organization names for clean URLs
- Interactive API docs via Swagger UI
---
## 🛠 Tech Stack

| Layer        | Technology       |
|--------------|------------------|
| Backend      | FastAPI          |
| Database     | MongoDB + Motor  |
| Auth         | JWT + Passlib    |
| Validation   | Pydantic         |
| Utilities    | Slugify, Email-validator |
| Server       | Uvicorn          |

---

##  Setup Instructions

### 1. Clone the repo

git clone https://github.com/Tarun30007/org-mgmt-service.git
cd org-mgmt-service

**### 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt

4. Run the server
uvicorn main:app --reload

API Documentation
Visit http://localhost:8000/docs for Swagger UI.

License
This project is licensed under the Apache 2.0 License.





