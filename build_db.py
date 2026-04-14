import json
import base64
import sqlite3
from datetime import datetime
from pathlib import Path


# =========================
# Configuration
# =========================

BASE_DIR = Path(__file__).resolve().parent
RBOT_DIR = next((p for p in BASE_DIR.iterdir() if p.is_dir() and p.name.startswith("RBOT-")), None)
if RBOT_DIR is None:
    raise FileNotFoundError("No RBOT-* folder found in BASE_DIR")
ROBOTS_DIR = RBOT_DIR / "robots_json"
DB_PATH = RBOT_DIR / "robot.db"

print(BASE_DIR)
print(DB_PATH)
print(ROBOTS_DIR)

DEFAULT_DATA_TYPE = ""
DEFAULT_VERSION = "2015.10.15"

# =========================
# Initialize Database
# =========================

def init_db(conn: sqlite3.Connection) -> None:

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            data_type TEXT,
            description TEXT,
            version TEXT,
            father INTEGER
        )
    """)

# =========================
# Normalize the modules
# =========================

def normalize_modules(robot_json: dict) -> None:
    # Retrieve the modules of the project
    modules = robot_json.get("project", {}).get("modules", [])

    # For each module last_version = version (for simplification) 
    for module in modules:
        if "last_version" not in module:
            module["last_version"] = module.get("version", DEFAULT_VERSION)

# =========================
# Read and decode json
# =========================

def load_and_encode_robot(json_path: Path) -> tuple[str, dict]:
    with json_path.open("r", encoding="utf-8") as f:
        robot_json = json.load(f)
    
    # Adjust modules so they are the same as what Rocketbot does (adds last_version)
    normalize_modules(robot_json)

    # Retrieve the json
    raw_json = json.dumps(
        robot_json,
        ensure_ascii=False,
        separators=(",", ":")
    )

    # Encode the json in b64
    encoded = base64.b64encode(
        raw_json.encode("utf-8")
    ).decode("utf-8")

    return encoded, robot_json

# =========================
# Extract metadata
# =========================

def extract_metadata(robot_json: dict, json_path: Path) -> tuple[str, str]:
    # Extract name and description from the porfile
    profile = robot_json.get("project", {}).get("profile", {})

    name = profile.get("name") or json_path.stem
    description = profile.get("description", "")

    return name, description

# =========================
# Insert a robot
# =========================

def insert_robot(
        conn: sqlite3.Connection, 
        name: str, 
        encoded_data: str, 
        description: str,
        created_at: str
) -> None:
    cursor = conn.cursor()

    # Execute query
    cursor.execute("""
        INSERT INTO bots (
            name,
            data,
            created_at,
            data_type,
            description,
            version,
            father
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        encoded_data,
        created_at,
        DEFAULT_DATA_TYPE,
        description,
        DEFAULT_VERSION,
        None
    ))

# =========================
# Main
# =========================

def main():

    # Check if necessary directories exist
    if not ROBOTS_DIR.exists() or not ROBOTS_DIR.is_dir():
        raise NotADirectoryError(f"No existe el directorio {ROBOTS_DIR}")
    
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Retrieve all the .json files from folder
    json_files = list(ROBOTS_DIR.glob("*.json"))

    # Check if there are no .json files
    if not json_files:
        print("There are no .json files in the folder")
        print(f"Folder path: {ROBOTS_DIR}")
        return

    print(f"Importing {len(json_files)} robots...\n")

    created_at = datetime.now().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)

        # For each robot: encode in b64, returve metadata and insert into database
        for json_path in json_files:
            encoded_data, robot_json = load_and_encode_robot(json_path)
            name, description = extract_metadata(robot_json, json_path)

            insert_robot(
                conn=conn,
                name=name,
                encoded_data=encoded_data,
                description=description,
                created_at=created_at
            )

            print(f"Inserting: {name} into database")

        conn.commit()

    print("\nImport completed successfully")

if __name__ == "__main__":
    main()
