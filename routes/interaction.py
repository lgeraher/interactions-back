from fastapi import APIRouter, HTTPException, Body
from database import db
from datetime import datetime
from pytz import timezone
from bson import ObjectId

router = APIRouter()

# Timezone for CST
CST = timezone('America/Mexico_City')

def serialize_interaction(interaction):
    """
    Converts interaction data to a JSON-serializable format.
    Specifically, converts ObjectId fields to strings.
    """
    for key in ["_id", "user._id", "interacting_user._id"]:
        if key in interaction:
            interaction[key] = str(interaction[key])
    return interaction

def validate_date(date_str):
    """
    Validates a date string and converts it to a datetime.date object.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use 'YYYY-MM-DD'.")

def calculate_score(interaction):
    """
    Calculate the score based on the specified rules:
    - If interactionType is 'Office' and clientIP is '177.230.219.9', score = 1.
    - If interactionType is 'Office' and clientIP is different, score = -1.
    - If interactionType is 'Remote', score = 0.
    """
    interaction_type = interaction.get("interactionType")
    client_ip = interaction.get("clientIP")

    if interaction_type == "Office":
        return 1 if client_ip == "177.230.219.9" else -1
    return 0 if interaction_type == "Remote" else 0

@router.get("/users/{user_id}/interactions/{date}")
async def get_interactions(user_id: str, date: str):
    """
    Fetch all interactions for a given user and date.
    """
    try:
        # Validate the provided date format
        target_date = validate_date(date)

        # Fetch interactions for the user and date
        interactions = await db.interactions.find(
            {"user.id": user_id, "date": str(target_date)}
        ).to_list(length=None)

        # Serialize interactions and transform to expected output
        serialized_interactions = [
            {
                "id": str(interaction["_id"]),
                "interactionType": interaction.get("interactionType"),
                "clientIP": interaction.get("clientIP"),
                "score": interaction.get("score"),
                "interacting_user": {
                    "id": interaction["interacting_user"]["id"],
                    "name": interaction["interacting_user"]["name"],
                    "mail": interaction["interacting_user"]["mail"],
                },
            }
            for interaction in interactions
        ]

        return {"user_id": user_id, "date": str(target_date), "interactions": serialized_interactions}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching interactions: {str(e)}"
        )

@router.post("/users/{user_id}/interactions")
async def save_interactions(user_id: str, interaction_input: dict = Body(...)):
    """
    Save user interactions.
    """
    try:
        user = interaction_input.get("user")
        client_ip = interaction_input.get("clientIP")
        interactions = interaction_input.get("interactions")

        if not user:
            raise HTTPException(status_code=400, detail="User object is required in the payload.")
        if not client_ip:
            raise HTTPException(status_code=400, detail="Payload is missing 'clientIP' field.")
        if not isinstance(interactions, list) or len(interactions) == 0:
            raise HTTPException(status_code=400, detail="Interactions must be a non-empty list.")

        now_cst = datetime.now(CST).strftime("%Y-%m-%d")
        created_records = []

        # Iterate over all interactions and save them
        for interaction in interactions:
            if not isinstance(interaction, dict):
                raise HTTPException(status_code=400, detail="Each interaction must be a dictionary.")

            interacting_user = interaction.get("interacting_with_user")
            if not (interacting_user and isinstance(interacting_user, dict)):
                raise HTTPException(
                    status_code=400, detail="Each interaction must include a valid interacting_with_user object."
                )

            interaction_type = interaction.get("interactionType")
            if not interaction_type:
                raise HTTPException(
                    status_code=400, detail="Interaction is missing the 'interactionType' field or it is empty."
                )

            # Calculate the score for the interaction
            score = calculate_score({"interactionType": interaction_type, "clientIP": client_ip})

            # Create interaction document
            interaction_document = {
                "user": user,
                "date": now_cst,
                "interactionType": interaction_type,
                "clientIP": client_ip,
                "interacting_user": interacting_user,
                "score": score,
            }

            # Save to database
            result = await db.interactions.insert_one(interaction_document)
            created_records.append({"id": str(result.inserted_id), "interacting_with_user": interacting_user})

        # Return all created records
        return {"message": "Interactions saved successfully.", "created_records": created_records}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving interactions: {str(e)}"
        )

@router.delete("/users/{user_id}/interactions/{interaction_id}")
async def delete_interaction(interaction_id: str):
    """
    Delete an interaction by ID if it was created today.
    """
    try:
        interaction_id_obj = ObjectId(interaction_id)
        interaction = await db.interactions.find_one({"_id": interaction_id_obj})

        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found.")

        interaction_date = datetime.strptime(interaction["date"], "%Y-%m-%d").date()
        today_cst = datetime.now(CST).date()

        if interaction_date != today_cst:
            raise HTTPException(
                status_code=403, detail="Interaction can only be deleted if it was created today."
            )

        await db.interactions.delete_one({"_id": interaction_id_obj})
        return {"message": "Interaction deleted successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting interaction: {str(e)}"
        )
