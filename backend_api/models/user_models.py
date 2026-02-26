from pydantic import BaseModel
from typing import Literal

Role = Literal["seller", "buyer"]


class UserCreate(BaseModel):
    email: str
    password: str
    role: Role
    name: str = ""


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    role: Role
    name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
