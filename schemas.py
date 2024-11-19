from pydantic import BaseModel, EmailStr
from typing import List

# Schema for a User
class User(BaseModel):
    id: str
    name: str
    last_name: str
    email: EmailStr

# Schema for an Interaction
class Interaction(BaseModel):
    interactionType: str
    clientIP: str
    interacting_with_user_id: str

# Schema for Interaction Input
class InteractionInput(BaseModel):
    date: str
    interactions: List[Interaction]
