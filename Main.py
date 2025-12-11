import os
import re
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from slugify import slugify
from bson import ObjectId

# -----------------------------
# Config
# -----------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MASTER_DB_NAME = os.getenv("MASTER_DB_NAME", "master_db")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# -----------------------------
# DB
# -----------------------------
client = AsyncIOMotorClient(MONGO_URI)
master_db = client[MASTER_DB_NAME]

# -----------------------------
# Schemas
# -----------------------------
class CreateOrgRequest(BaseModel):
    organization_name: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)

class UpdateOrgRequest(BaseModel):
    organization_name: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str

class DeleteOrgRequest(BaseModel):
    organization_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OrgResponse(BaseModel):
    id: str
    organization_name: str
    organization_slug: str
    collection_name: str
    admin_email: EmailStr

# -----------------------------
# Utils
# -----------------------------
def org_slug(name: str) -> str:
    s = slugify(name).lower()
    if not s or not re.match(r"^[a-z0-9-]+$", s):
        raise ValueError("Invalid organization name")
    return s

def org_collection_name(slug: str) -> str:
    return f"org_{slug}"

# -----------------------------
# Auth Service
# -----------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, password: str, hashed: str) -> bool:
        return pwd_context.verify(password, hashed)

    def create_token(self, admin_id: str, org_id: str, email: str) -> str:
        exp = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
        payload = {"sub": admin_id, "org_id": org_id, "email": email, "exp": exp}
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

    def decode_token(self, token: str):
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

auth_service = AuthService()

# -----------------------------
# Organization Service
# -----------------------------
class OrganizationService:
    def __init__(self, client):
        self.client = client
        self.orgs = master_db["organizations"]
        self.admins = master_db["admins"]

    async def get_by_name(self, name: str):
        slug = org_slug(name)
        return await self.orgs.find_one({"slug": slug})

    async def create(self, name: str, email: str, password_hash: str):
        slug = org_slug(name)
        if await self.orgs.find_one({"slug": slug}):
            raise ValueError("Organization already exists")

        collection_name = org_collection_name(slug)
        org_collection = self.client[master_db.name][collection_name]
        await org_collection.insert_one({"_schema_version": 1, "_created_at": datetime.utcnow()})

        admin_doc = {
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
        }
        admin_result = await self.admins.insert_one(admin_doc)

        org_doc = {
            "name": name,
            "slug": slug,
            "collection_name": collection_name,
            "admin_id": admin_result.inserted_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        org_result = await self.orgs.insert_one(org_doc)

        await self.admins.update_one(
            {"_id": admin_result.inserted_id},
            {"$set": {"organization_id": org_result.inserted_id}},
        )

        return {
            "id": str(org_result.inserted_id),
            "organization_name": name,
            "organization_slug": slug,
            "collection_name": collection_name,
            "admin_email": email,
        }

    async def update(self, current_slug: str, new_name: str):
        new_slug = org_slug(new_name)
        if await self.orgs.find_one({"slug": new_slug}):
            raise ValueError("New organization name already exists")

        org = await self.orgs.find_one({"slug": current_slug})
        if not org:
            raise ValueError("Organization not found")

        old_collection = org["collection_name"]
        new_collection = org_collection_name(new_slug)

        src = self.client[master_db.name][old_collection]
        dst = self.client[master_db.name][new_collection]

        cursor = src.find({})
        async for doc in cursor:
            doc.pop("_id", None)
            await dst.insert_one(doc)

        await self.orgs.update_one(
            {"_id": org["_id"]},
            {"$set": {"name": new_name, "slug": new_slug, "collection_name": new_collection, "updated_at": datetime.utcnow()}},
        )

        return {"old_collection": old_collection, "new_collection": new_collection, "organization_slug": new_slug}

    async def delete(self, slug: str, requester_admin_id: str):
        org = await self.orgs.find_one({"slug": slug})
        if not org:
            raise ValueError("Organization not found")

        if str(org["admin_id"]) != requester_admin_id:
            raise PermissionError("Not authorized to delete this organization")

        await self.client[master_db.name].drop_collection(org["collection_name"])
        await self.admins.delete_one({"_id": org["admin_id"]})
        await self.orgs.delete_one({"_id": org["_id"]})
        return True

org_service = OrganizationService(client)

# -----------------------------
# Admin Service
# -----------------------------
class AdminService:
    def __init__(self):
        self.admins = master_db["admins"]

    async def get_by_email(self, email: str):
        return await self.admins.find_one({"email": email})

admin_service = AdminService()

# -----------------------------
# Dependencies
# -----------------------------
async def get_current_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = auth_service.decode_token(token)
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# -----------------------------
# FastAPI Routes
# -----------------------------
app = FastAPI(title="Organization Management Service")

@app.post("/org/create", response_model=OrgResponse)
async def create_org(payload: CreateOrgRequest):
    try:
        hashed = auth_service.hash_password(payload.password)
        data = await org_service.create(payload.organization_name, payload.email, hashed)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/org/get", response_model=OrgResponse)
async def get_org(organization_name: str):
    org = await org_service.get_by_name(organization_name)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    admin_doc = await master_db["admins"].find_one({"_id": org["admin_id"]})
    return {
        "id": str(org["_id"]),
        "organization_name": org["name"],
        "organization_slug": org["slug"],
        "collection_name": org["collection_name"],
        "admin_email": admin_doc["email"] if admin_doc else "",
    }

@app.put("/org/update")
async def update_org(payload: UpdateOrgRequest, current=Depends(get_current_admin)):
    admin_doc = await admin_service.get_by_email(payload.email)
    if not admin_doc or not auth_service.verify_password(payload.password, admin_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    if current["sub"] != str(admin_doc["_id"]):
        raise HTTPException(status_code=403, detail="Forbidden")

    org = await master_db["organizations"].find_one({"_id": ObjectId(current["org_id"])})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        result = await org_service.update(org["slug"], payload.organization_name)
        return {"message": "Organization updated", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/org/delete")
async def delete_org(payload: DeleteOrgRequest, current=Depends(get_current_admin)):
    org = await master_db["organizations"].find_one({"_id": ObjectId(current["org_id"])})
    if not org or org["slug"] != org_slug(payload.organization_name):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        await org_service.delete(org["slug"], requester_admin_id=current["sub"])
        return {"message": "Organization deleted"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
