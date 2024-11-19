from fastapi import APIRouter, HTTPException
from schemas import User
from typing import List
from database import db

router = APIRouter()

@router.get("/users/{search_string}", response_model=List[User])
async def search_users(search_string: str):
    """
    Search for users by name, last name, or the concatenation of both
    using a case-insensitive substring match.
    """
    if len(search_string) < 3:
        raise HTTPException(status_code=400, detail="Search string must be at least 3 characters.")
    
    # MongoDB query to match 'name', 'last_name', or concatenation of both
    users_cursor = db.users.find({
        "$or": [
            {"name": {"$regex": search_string, "$options": "i"}},
            {"last_name": {"$regex": search_string, "$options": "i"}},
            {"$expr": {"$regexMatch": {
                "input": {"$concat": ["$name", " ", "$last_name"]},
                "regex": search_string,
                "options": "i"
            }}}
        ]
    })
    
    # Limit the result to 10 users
    users = await users_cursor.to_list(10)
    
    return [
        {"id": str(user["_id"]), "name": user["name"], "last_name": user["last_name"], "email": user["email"]}
        for user in users
    ]