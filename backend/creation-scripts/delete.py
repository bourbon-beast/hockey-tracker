import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()

def clear_collections():
    collections = ["competitions", "teams", "games", "players", "settings"]
    for collection in collections:
        docs = db.collection(collection).stream()
        for doc in docs:
            doc.reference.delete()
        print(f"Deleted all documents in {collection}")

clear_collections()