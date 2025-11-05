# database.py

import pymongo
import os
from datetime import datetime

# --- MongoDB Connection ---
# Environment Variables များကို os module ဖြင့် import လုပ်ပါ
try:
    MONGO_URL = os.environ.get("MONGO_URL")
    ADMIN_ID = int(os.environ.get("ADMIN_ID"))
    
    if not MONGO_URL or not ADMIN_ID:
        print("Error: MONGO_URL or ADMIN_ID environment variable မတွေ့ပါ။")
        exit()
        
except Exception as e:
    print(f"Error: Environment variables load လုပ်ရာတွင် အမှားဖြစ်နေပါသည်: {e}")
    exit()


try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client["mlbb_bot_db"] # Database နာမည်
    
    users_collection = db["users"]
    prices_collection = db["prices"]
    auth_collection = db["authorized_users"]
    admins_collection = db["admins"]
    settings_collection = db["settings"]
    clone_bots_collection = db["clone_bots"]

    print("✅ MongoDB database နှင့် အောင်မြင်စွာ ချိတ်ဆက်ပြီးပါပြီ။")
except Exception as e:
    print(f"❌ MongoDB ချိတ်ဆက်ရာတွင် Error ဖြစ်နေပါသည်: {e}")
    client = None

# --- User Functions ---

def get_user(user_id):
    """User တစ်ယောက်၏ data ကို user_id ဖြင့် ရှာဖွေပါ။"""
    if not client: return None
    return users_collection.find_one({"user_id": str(user_id)})
    
def get_all_users():
    """User တွေအားလုံးရဲ့ data ကို list အဖြစ် ယူပါ။"""
    if not client: return []
    return list(users_collection.find({}))

def create_user(user_id, name, username):
    """User အသစ်ကို database တွင် ထည့်သွင်းပါ။"""
    if not client: return None
    user_data = {
        "user_id": str(user_id),
        "name": name,
        "username": username,
        "balance": 0,
        "orders": [],
        "topups": [],
        "joined_at": datetime.now().isoformat()
    }
    users_collection.update_one(
        {"user_id": str(user_id)},
        {"$setOnInsert": user_data},
        upsert=True
    )

def get_balance(user_id):
    """User ၏ balance ကိုသာ ရယူပါ။"""
    user = get_user(user_id)
    return user.get("balance", 0) if user else 0

def update_balance(user_id, amount_change):
    """User ၏ balance ကို တိုး/လျော့ ပါ။ (User ရှိပြီးသားဖြစ်ရမည်)"""
    if not client: return None
    users_collection.update_one(
        {"user_id": str(user_id)},
        {"$inc": {"balance": amount_change}}
        # upsert=True ကို ဖြုတ်လိုက်ပါ
    )

# --- Order & Topup Functions ---

def add_order(user_id, order_data):
    if not client: return None
    users_collection.update_one(
        {"user_id": str(user_id)},
        {"$push": {"orders": order_data}}
    )

def add_topup(user_id, topup_data):
    if not client: return None
    users_collection.update_one(
        {"user_id": str(user_id)},
        {"$push": {"topups": topup_data}}
    )

def find_and_update_order(order_id, updates):
    """Order ID ဖြင့် order ကိုရှာပြီး update လုပ်ပါ။"""
    if not client: return None
    filter_query = {"orders.order_id": order_id, "orders.status": "pending"}
    update_fields = {}
    for key, value in updates.items():
        update_fields[f"orders.$.{key}"] = value
        
    result = users_collection.find_one_and_update(
        filter_query, {"$set": update_fields}
    )
    return result.get("user_id") if result else None

def find_and_update_topup(topup_id, updates):
    """Topup ID ဖြင့် topup ကိုရှာပြီး update လုပ်ပါ။"""
    if not client: return None
    filter_query = {"topups.topup_id": topup_id, "topups.status": "pending"}
    update_fields = {}
    for key, value in updates.items():
        update_fields[f"topups.$.{key}"] = value
        
    result = users_collection.find_one_and_update(
        filter_query, {"$set": update_fields}
    )
    
    if result:
        user_id = result.get("user_id")
        # Topup approve ဖြစ်ရင် balance ပါ တစ်ခါတည်း တိုးပေး
        if updates.get("status") == "approved":
            # Find the exact amount from the matched topup
            topup_amount = 0
            for topup in result.get("topups", []):
                if topup.get("topup_id") == topup_id:
                    topup_amount = topup.get("amount", 0)
                    break
            if topup_amount > 0:
                update_balance(user_id, topup_amount)
        return user_id
    return None

def get_user_orders(user_id, limit=5):
    user = get_user(user_id)
    if not user: return []
    # Sort descending by timestamp and get latest 5
    orders = sorted(user.get("orders", []), key=lambda x: x.get('timestamp', ''), reverse=True)
    return orders[:limit]

def get_user_topups(user_id, limit=5):
    user = get_user(user_id)
    if not user: return []
    # Sort descending by timestamp and get latest 5
    topups = sorted(user.get("topups", []), key=lambda x: x.get('timestamp', ''), reverse=True)
    return topups[:limit]

def get_order_by_id(order_id):
    """Nested array ထဲက order ကို ID နဲ့ဆွဲထုတ်ပါ။"""
    if not client: return None
    result = users_collection.find_one(
        {"orders.order_id": order_id},
        {"_id": 0, "orders.$": 1}
    )
    return result.get("orders", [{}])[0] if result else None

def get_topup_by_id(topup_id):
    """Nested array ထဲက topup ကို ID နဲ့ဆွဲထုတ်ပါ။"""
    if not client: return None
    result = users_collection.find_one(
        {"topups.topup_id": topup_id},
        {"_id": 0, "topups.$": 1}
    )
    return result.get("topups", [{}])[0] if result else None

# --- Price Functions ---

def load_prices():
    if not client: return {}
    price_doc = prices_collection.find_one({"_id": "custom_prices"})
    return price_doc.get("prices", {}) if price_doc else {}

def save_prices(prices_dict):
    if not client: return
    prices_collection.update_one(
        {"_id": "custom_prices"},
        {"$set": {"prices": prices_dict}},
        upsert=True
    )

# --- Authorization Functions ---

def load_authorized_users():
    if not client: return set()
    doc = auth_collection.find_one({"_id": "auth_list"})
    return set(doc.get("users", [])) if doc else set()

def add_authorized_user(user_id):
    if not client: return
    auth_collection.update_one(
        {"_id": "auth_list"},
        {"$addToSet": {"users": str(user_id)}},
        upsert=True
    )

def remove_authorized_user(user_id):
    if not client: return
    auth_collection.update_one(
        {"_id": "auth_list"},
        {"$pull": {"users": str(user_id)}}
    )

# --- Admin Functions ---

def load_admin_ids(default_owner_id):
    if not client: return [default_owner_id]
    doc = admins_collection.find_one({"_id": "admin_list"})
    if doc:
        admin_list = doc.get("admins", [])
        if default_owner_id not in admin_list:
            admin_list.append(default_owner_id)
        return admin_list
    admins_collection.insert_one({"_id": "admin_list", "admins": [default_owner_id]})
    return [default_owner_id]

def add_admin(admin_id):
    if not client: return
    admins_collection.update_one(
        {"_id": "admin_list"},
        {"$addToSet": {"admins": int(admin_id)}},
        upsert=True
    )

def remove_admin(admin_id):
    if not client: return
    admins_collection.update_one(
        {"_id": "admin_list"},
        {"$pull": {"admins": int(admin_id)}}
    )

# --- Settings Collection Functions (For Render) ---

def load_settings(default_payment, default_maintenance):
    """
    Global settings များကို DB မှ load လုပ်ပါ။
    မရှိသေးပါက default value များဖြင့် အသစ်ဆောက်ပါ။
    """
    if not client:
        return {"payment_info": default_payment, "maintenance": default_maintenance}
    
    config = settings_collection.find_one({"_id": "global_config"})
    
    if not config:
        print("Creating default settings in MongoDB...")
        config = {
            "_id": "global_config",
            "payment_info": default_payment,
            "maintenance": default_maintenance
        }
        try:
            settings_collection.insert_one(config)
        except Exception as e:
            print(f"Failed to create default settings: {e}")
            
    # Check for missing keys and add them
    if "payment_info" not in config:
        config["payment_info"] = default_payment
        update_setting("payment_info", default_payment)
    if "maintenance" not in config:
        config["maintenance"] = default_maintenance
        update_setting("maintenance", default_maintenance)
    
    # Ensure all sub-keys exist for payment_info
    for key, value in default_payment.items():
        if key not in config["payment_info"]:
            config["payment_info"][key] = value
            update_setting(f"payment_info.{key}", value)

    # Ensure all sub-keys exist for maintenance
    for key, value in default_maintenance.items():
        if key not in config["maintenance"]:
            config["maintenance"][key] = value
            update_setting(f"maintenance.{key}", value)
            
    return config

def update_setting(key, value):
    """
    Setting တစ်ခုကို dot notation သုံးပြီး update လုပ်ပါ။
    ဥပမာ: "payment_info.kpay_number"
    """
    if not client: return
    try:
        settings_collection.update_one(
            {"_id": "global_config"},
            {"$set": {key: value}},
            upsert=True
        )
    except Exception as e:
        print(f"Failed to update setting '{key}': {e}")

# --- Clone Bot DB Functions ---

def load_clone_bots():
    """DB မှ clone bot အားလုံးကို dict အဖြစ် ယူပါ။"""
    if not client: return {}
    bots = {}
    for bot in clone_bots_collection.find():
        bots[str(bot["_id"])] = bot
    return bots

def save_clone_bot(bot_id, bot_data):
    """Clone bot data ကို DB မှာ သိမ်း/update လုပ်ပါ။"""
    if not client: return
    # bot_id ကို _id အဖြစ် သုံးပါမယ်
    bot_data_with_id = bot_data.copy()
    bot_data_with_id["_id"] = bot_id
    clone_bots_collection.update_one(
        {"_id": bot_id},
        {"$set": bot_data_with_id},
        upsert=True
    )

def remove_clone_bot(bot_id):
    """Clone bot ကို DB မှ ဖျက်ပါ။"""
    if not client: return False
    result = clone_bots_collection.delete_one({"_id": bot_id})
    return result.deleted_count > 0

def get_clone_bot_by_admin(admin_id):
    """Admin ID ဖြင့် clone bot ကို ရှာပါ။"""
    if not client: return None
    return clone_bots_collection.find_one({"owner_id": admin_id})

def update_clone_bot_balance(bot_id, amount_change):
    """Clone bot ၏ balance ကို တိုး/လျော့ ပါ။"""
    if not client: return
    clone_bots_collection.update_one(
        {"_id": bot_id},
        {"$inc": {"balance": amount_change}}
    )

# database.py (File အောက်ဆုံးမှာ ဒါကို ထပ်ထည့်ပါ)

def clear_user_history(user_id):
    """
    User တစ်ယောက်၏ orders နှင့် topups list များကို ဖျက်ပြီး empty array [] အဖြစ် ပြန်ထားပါ။
    """
    if not client: 
        return False
        
    try:
        result = users_collection.update_one(
            {"user_id": str(user_id)},
            {"$set": {"orders": [], "topups": []}}
        )
        # user_id ရှိပြီး update ဖြစ်သွားရင် True ပြန်ပေးပါ
        return result.modified_count > 0 or result.matched_count > 0
    except Exception as e:
        print(f"Error clearing history for {user_id}: {e}")
        return False

# database.py (File အောက်ဆုံးမှာ ဒါကို ထပ်ထည့်ပါ)

def wipe_all_data():
    """
    !!! အလွန်အန္တရာယ်များသော FUNCTION !!!
    Database ထဲရှိ Collection များ (users, settings, prices, etc.) အားလုံးကို ဖျက်ဆီးပါသည်။
    """
    if not client:
        return False
    try:
        print("\n" + "="*30)
        print("WARNING: MongoDB WIPE INITIATED...")
        print("="*30 + "\n")
        
        collections_to_wipe = [
            users_collection,
            prices_collection,
            auth_collection,
            admins_collection,
            settings_collection,
            clone_bots_collection
        ]
        
        for collection in collections_to_wipe:
            collection_name = collection.name
            count = collection.count_documents({})
            collection.delete_many({})
            print(f"WIPED: {collection_name} (Deleted {count} documents)")
            
        print("\n✅ All collections have been successfully wiped.")
        return True
    
    except Exception as e:
        print(f"❌ Error during MongoDB wipe: {e}")
        return False
