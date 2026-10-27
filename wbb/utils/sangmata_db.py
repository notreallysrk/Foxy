# wbb/utils/sangmata_db.py
from wbb import db

# WBB ke existing database mein 'sangmata' ka naya collection banega
matadb = db.sangmata 

async def cek_userdata(user_id: int) -> bool:
    user = await matadb.find_one({"user_id": user_id})
    return bool(user)

async def get_userdata(user_id: int):
    user = await matadb.find_one({"user_id": user_id})
    if user:
        return user.get("username"), user.get("first_name"), user.get("last_name")
    return None, None, None

async def add_userdata(user_id: int, username, first_name, last_name):
    await matadb.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "first_name": first_name, "last_name": last_name}},
        upsert=True,
    )

async def is_sangmata_on(chat_id: int) -> bool:
    chat = await matadb.find_one({"chat_id_toggle": chat_id})
    return bool(chat)

async def sangmata_on(chat_id: int):
    await matadb.update_one(
        {"chat_id_toggle": chat_id}, 
        {"$set": {"chat_id_toggle": chat_id}}, 
        upsert=True
    )

async def sangmata_off(chat_id: int):
    await matadb.delete_one({"chat_id_toggle": chat_id})
