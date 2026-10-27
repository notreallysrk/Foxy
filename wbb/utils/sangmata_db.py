# File Location: wbb/utils/sangmata_db.py

from wbb import db

# WBB ke existing database mein 'sangmata' ka naya collection banega
matadb = db.sangmata 

# Yahan hum RAM cache bana rahe hain jisse bot 10x fast ho jayega
sangmata_chats_cache = {}
user_data_cache = {}

async def is_sangmata_on(chat_id: int) -> bool:
    # Agar cache mein hai, toh direct wahi se return kardo (DB call bachega)
    if chat_id in sangmata_chats_cache:
        return sangmata_chats_cache[chat_id]
        
    chat = await matadb.find_one({"chat_id_toggle": chat_id})
    is_on = bool(chat)
    sangmata_chats_cache[chat_id] = is_on
    return is_on

async def sangmata_on(chat_id: int):
    sangmata_chats_cache[chat_id] = True
    await matadb.update_one({"chat_id_toggle": chat_id}, {"$set": {"chat_id_toggle": chat_id}}, upsert=True)

async def sangmata_off(chat_id: int):
    sangmata_chats_cache[chat_id] = False
    await matadb.delete_one({"chat_id_toggle": chat_id})

async def cek_userdata(user_id: int) -> bool:
    if user_id in user_data_cache:
        return True
    user = await matadb.find_one({"user_id": user_id})
    if user:
        user_data_cache[user_id] = user
    return bool(user)

async def get_userdata(user_id: int):
    user = user_data_cache.get(user_id)
    if not user:
        user = await matadb.find_one({"user_id": user_id})
        if user:
            user_data_cache[user_id] = user
            
    if user:
        return user.get("username"), user.get("first_name"), user.get("last_name")
    return None, None, None

async def add_userdata(user_id: int, username, first_name, last_name):
    # Cache aur DB dono ek sath update karenge
    user_data_cache[user_id] = {"user_id": user_id, "username": username, "first_name": first_name, "last_name": last_name}
    await matadb.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "first_name": first_name, "last_name": last_name}},
        upsert=True,
    )
