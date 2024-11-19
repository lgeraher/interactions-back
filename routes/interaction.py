from fastapi import APIRouter, HTTPException, Body
from schemas import InteractionInput
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
    if "_id" in interaction:
        interaction["_id"] = str(interaction["_id"])
    if "user" in interaction and "_id" in interaction["user"]:
        interaction["user"]["_id"] = str(interaction["user"]["_id"])
    if "interacting_user" in interaction and "_id" in interaction["interacting_user"]:
        interaction["interacting_user"]["_id"] = str(interaction["interacting_user"]["_id"])
    return interaction


@router.get("/users/{user_id}/interactions/{date}")
async def get_interactions(user_id: str, date: str):
    """
    Fetch all interactions for a given user and date.
    """
    try:
        # Validate the provided date format
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use 'YYYY-MM-DD'.")

        # Fetch interactions for the user and date
        interactions = await db.interactions.find(
            {"user._id": user_id, "date": date}
        ).to_list(length=None)

        # Serialize interactions if found, otherwise return an empty list
        serialized_interactions = [serialize_interaction(interaction) for interaction in interactions]

        return {"user_id": user_id, "date": date, "interactions": serialized_interactions}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching interactions: {str(e)}"
        )


@router.post("/users/{user_id}/interactions")
async def save_interactions(user_id: str, interaction_input: InteractionInput = Body(...)):
    # Fetch the full user object for the main user
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        created_records = []
        # Prepare and insert each interaction as a separate document
        for interaction in interaction_input.interactions:
            # Calculate score based on the given rules
            score = calculate_score(interaction)

            # Convert the date to CST and format it
            now_cst = datetime.now(CST).strftime("%Y-%m-%d")

            # Fetch the full user object for interacting_with_user_id
            interacting_user = await db.users.find_one({"_id": interaction.interacting_with_user_id})
            if not interacting_user:
                raise HTTPException(
                    status_code=404,
                    detail=f"Interacting user with ID {interaction.interacting_with_user_id} not found."
                )

            # Create a document for this interaction
            interaction_document = {
                "user": user,  # Store the full user object
                "date": now_cst,  # Save date in CST
                "interactionType": interaction.interactionType,
                "clientIP": interaction.clientIP,
                "interacting_user": interacting_user,  # Store the full interacting user object
                "score": score,
            }
            result = await db.interactions.insert_one(interaction_document)

            # Append the created record with the id and interacting_with_user_id
            created_records.append({
                "id": str(result.inserted_id),
                "interacting_with_user_id": interaction.interacting_with_user_id,
            })

        return {
            "message": "Interactions saved successfully.",
            "created_records": created_records
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving interactions: {str(e)}")


@router.delete("/users/{user_id}/interactions/{interaction_id}")
async def delete_interaction(interaction_id: str):
    try:
        # Convert the interaction_id to an ObjectId
        interaction_id_obj = ObjectId(interaction_id)

        # Fetch the interaction
        interaction = await db.interactions.find_one({"_id": interaction_id_obj})
        if not interaction:
            raise HTTPException(
                status_code=404, detail="Interaction not found.")

        # Validate if the interaction's date matches today's date in CST
        interaction_date = datetime.strptime(
            interaction["date"], "%Y-%m-%d").replace(tzinfo=CST)
        today_cst = datetime.now(CST).replace(
            hour=0, minute=0, second=0, microsecond=0)
        if interaction_date.date() != today_cst.date():
            raise HTTPException(
                status_code=403, detail="Interaction can only be deleted if it was created today.")

        # Delete the interaction
        await db.interactions.delete_one({"_id": interaction_id_obj})
        return {"message": "Interaction deleted successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting interaction: {str(e)}")


def calculate_score(interaction):
    """
    Calculate the score based on the specified rules:
    - If interactionType is 'Office' and clientIP is '177.230.219.9', score = 1.
    - If interactionType is 'Office' and clientIP is different, score = -1.
    - If interactionType is 'Remote', score = 0.
    """
    if interaction.interactionType == "Office":
        if interaction.clientIP == "177.230.219.9":
            return 1
        else:
            return -1
    elif interaction.interactionType == "Remote":
        return 0
    return 0
