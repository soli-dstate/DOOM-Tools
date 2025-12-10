version = "0.0.0"

import os
import logging
from datetime import datetime
import zipfile
import glob
import requests
import platform
import pygame
import customtkinter
import base64
import pickle
import json
import shutil
import psutil
import locale
import random
import math
import time

pygame.init()

pygame.mixer.init(channels=4096)

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

os.makedirs("logs", exist_ok=True)
os.makedirs("logs/archive", exist_ok=True)

log_files = glob.glob("logs/*.log")
if len(log_files) >= 50:
    archive_name = f"logs/archive/logs_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for log_file in log_files:
            zipf.write(log_file, os.path.basename(log_file))
            os.remove(log_file)

existing_logs = glob.glob("logs/log_*.log")
log_number = len(existing_logs) + 1

log_filename = f"logs/log_{log_number}_{datetime.now().strftime('%A_%B_%d_%Y_%H_%M_%S_%f')[:-3]}.log"

file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')

file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
import warnings
logging.captureWarnings(True)
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
import sys
sys.excepthook = handle_exception

os.system('cls' if os.name == 'nt' else 'clear')

logging.info(f"DOOM Tools, version {version}")
try:
    response = requests.get("https://uselessfacts.jsph.pl/random.json?language=en")
    response.raise_for_status()
    fact = response.json().get("text", "No fact retrieved")
    logging.info(f"{fact}")
except requests.RequestException as e:
    logging.warning(f"Failed to fetch random fact: {e}")
logging.info(f"Logging initialized at {log_filename}, log number {log_number}.")
logging.info(f"Python version: {os.sys.version}")
logging.info(f"Platform: {os.sys.platform}")
logging.info(f"Working directory: {os.getcwd()}")
logging.info(f"Executable: {os.sys.executable}")
logging.info(f"Script: {os.path.abspath(__file__)}")
logging.info(f"Arguments: {os.sys.argv}")
logging.info(f"Process ID: {os.getpid()}")
logging.info(f"Parent Process ID: {os.getppid()}")
logging.info(f"User: {os.getlogin()}")
logging.info(f"Machine: {platform.machine()}")
logging.info(f"Processor: {platform.processor()}")
logging.info(f"Cores: {os.cpu_count()}")
logging.info(f"System: {platform.system()} {platform.release()}")
if platform.system() == "Linux":
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME"):
                    distribution_info = line.split('=')[1].strip().strip('"')
                    logging.info(f"Linux distribution: {distribution_info}")
                    break
    except Exception as e:
        logging.warning(f"Failed to read Linux distribution info: {e}")
logging.info(f"Architecture: {platform.architecture()[0]}")
logging.info(f"RAM: {round(psutil.virtual_memory().total / (1024. ** 2), 2)} MB")
logging.info(f"Python Implementation: {platform.python_implementation()}")

global_variables = {
    "devmode": {"value": False, "forced": False},
    "dmmode": {"value": False, "forced": False},
    "debugmode": {"value": False, "forced": False},
    "current_table": None,
    "ide": False,
    "table_extension": ".sldtbl",
    "save_extension": ".sldsv",
    "lootcrate_extension": ".sldlct",
    "transfer_extension": ".sldtrf",
    "enemyloot_extension": ".sldenlt",
}

possible_flags = ["--dev", "--dm", "--debug", "--force", "-debug"]

for flag in possible_flags:
    if flag in os.sys.argv:
        if flag == "--dev":
            global_variables["devmode"]["value"] = True
            logging.info("Development mode activated via command-line flag.")
        elif flag == "--dm":
            global_variables["dmmode"]["value"] = True
            logging.info("DM mode activated via command-line flag.")
        elif flag in ("--debug", "-debug"):
            global_variables["debugmode"]["value"] = True
            logging.info("Debug mode activated via command-line flag.")
        elif flag == "--force":
            for var in global_variables:
                if isinstance(global_variables[var], dict) and "forced" in global_variables[var]:
                                    global_variables[var]["forced"] = True
            logging.info("Force flag applied to all modes.")

if global_variables["debugmode"]["value"]:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Debug mode enabled. Logging level set to DEBUG.")

appearance_settings = {
    "appearance_mode": "system",
    "color_theme": "dark-blue",
    "resolution": "1920x1080",
    "fullscreen": False,
    "borderless": False,
    "units": "imperial",
    "auto_set_units": False,
    "sound_volume": 100
}

folders = [
    {"name": "logs", "ignore_gitignore": False},
    {"name": "sounds", "ignore_gitignore": False},
    {"name": "tables", "ignore_gitignore": True},
    {"name": "transfers", "ignore_gitignore": False},
    {"name": "lootcrates", "ignore_gitignore": False},
    {"name": "enemyloot", "ignore_gitignore": False},
    {"name": "themes", "ignore_gitignore": False}
]

themes_dir = "themes"
os.makedirs(themes_dir, exist_ok=True)

try:
    if not any(os.scandir(themes_dir)):
        logging.info("Themes folder is empty. Downloading CTkThemesPack...")
        tmp_zip = "CTkThemesPack.zip"
        extract_dir = "CTkThemesPack_src"

        response = requests.get("https://github.com/a13xe/CTkThemesPack/archive/refs/heads/main.zip", timeout=30)
        response.raise_for_status()
        with open(tmp_zip, "wb") as f:
            f.write(response.content)

        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(tmp_zip, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        extracted_roots = [d for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
        if extracted_roots:
            src_theme_dir = os.path.join(extract_dir, extracted_roots[0], "themes")
            if os.path.isdir(src_theme_dir):
                for entry in os.listdir(src_theme_dir):
                    src_path = os.path.join(src_theme_dir, entry)
                    dst_path = os.path.join(themes_dir, entry)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dst_path)
                logging.info("Themes downloaded and installed successfully.")
            else:
                logging.warning("No 'themes' directory found in downloaded package.")
        else:
            logging.warning("Failed to locate extracted CTkThemesPack directory.")
except Exception as e:
    logging.error(f"Failed to populate themes: {e}")
finally:
    try:
        shutil.rmtree(extract_dir, ignore_errors=True)
    except Exception:
        pass
    try:
        os.remove(tmp_zip)
    except Exception:
        pass

ide_indicators = [
    'PYCHARM_HOSTED',
    'VSCODE_PID',
    'SPYDER_KERNELS_NAMESPACE',
    'PYDEVD_USE_FRAME_EVAL',
    'TERM_PROGRAM',
    'JUPYTER_RUNTIME_DIR',
    'JPY_PARENT_PID',
    'IPYTHONDIR',
    'PYCHARM_MATPLOTLIB_INTERACTIVE',
    'PYCHARM_DISPLAY_PORT',
    'INTELLIJ_ENVIRONMENT_READER',
    'IDEA_INITIAL_DIRECTORY',
    'PYTHONIOENCODING',
    'PYDEV_CONSOLE_ENCODING',
    'VSCODE_CLI',
    'VSCODE_GIT_ASKPASS_NODE',
    'VSCODE_INJECTION'
]

dm_users = ["bGlseQ==", "amFjemk=", "cGhvbmU="]

if any(indicator in os.environ for indicator in ide_indicators):
    if not global_variables["devmode"]["value"] and not global_variables["devmode"]["forced"]:
        global_variables["devmode"]["value"] = True
        logging.info("Development mode activated due to IDE environment detection.")
    elif global_variables["devmode"]["value"]:
        logging.info("IDE environment detected, but development mode is already set.")
    else:
        logging.info("IDE environment detected, but development mode is forced off.")
    logging.info(f"Trigger: {[key for key in os.environ if key in ide_indicators]}")
    global_variables["ide"] = True
    for folder_entry in folders:
        folder = folder_entry["name"]
        ignore_gitignore = folder_entry.get("ignore_gitignore", False)
        
        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info(f"Created missing folder: {folder}")
        if ignore_gitignore:
            logging.info(f"Skipped .gitignore addition for '{folder}' (ignore_gitignore=True)")
            continue
        
        with open('.gitignore', 'a') as gitignore:
            existing_gitignore = set()
            try:
                with open('.gitignore', 'r') as read_gitignore:
                    existing_gitignore = set(line.strip() for line in read_gitignore)
            except FileNotFoundError:
                pass
            entry = f'/{folder}/'
            if entry not in existing_gitignore:
                gitignore.write(f'{entry}\n')
                logging.info(f"Added '{entry}' to .gitignore")
            else:
                logging.info(f"'{entry}' already exists in .gitignore")
    try:
        import subprocess
        result = subprocess.run([os.sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True)
        current_packages = set(result.stdout.strip().split('\n'))

        existing_packages = set()
        try:
            with open('requirements.txt', 'r') as f:
                existing_packages = set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            pass
        all_packages = existing_packages | current_packages
        all_packages.discard('')
        with open('requirements.txt', 'w') as f:
            for package in sorted(all_packages):
                f.write(f'{package}\n')
        logging.info(f"Updated requirements.txt with {len(all_packages)} packages")
    except Exception as e:
        logging.warning(f"Failed to update requirements.txt: {e}")

if not global_variables["devmode"]["value"]:
    logging.info("Running in production mode.")
    if os.name == 'nt':
        saves_folder = os.path.join(os.getenv('LOCALAPPDATA'), 'DOOM Tools', 'saves')
    else:
        saves_folder = os.path.expanduser('~/.local/share/DOOM Tools/saves')
else:
    logging.info("Running in development mode.")
    saves_folder = "saves"
    folders.append(saves_folder)
    with open('.gitignore', 'a') as gitignore:
        existing_gitignore = set()
        try:
            with open('.gitignore', 'r') as read_gitignore:
                existing_gitignore = set(line.strip() for line in read_gitignore)
        except FileNotFoundError:
            pass
        entry = '/saves/'
        if entry not in existing_gitignore:
            gitignore.write(f'{entry}\n')
            logging.info(f"Added '{entry}' to .gitignore")
        else:
            logging.info(f"'{entry}' already exists in .gitignore")

os.makedirs(saves_folder, exist_ok=True)

try:
    appearance_settings_path = os.path.join(saves_folder, "appearance_settings.sldsv")
    if os.path.exists(appearance_settings_path):
        with open(appearance_settings_path, 'r') as f:
            loaded_settings = json.load(f)
        appearance_settings.update(loaded_settings)
        logging.info(f"Appearance settings loaded from {appearance_settings_path}")
except Exception as e:
    logging.warning(f"Failed to load appearance settings: {e}")

try:
    settings_path = os.path.join(saves_folder, "settings.sldsv")
    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            loaded_globals = json.load(f)
        # Merge loaded settings into global_variables, preserving structure
        for key, value in loaded_globals.items():
            if key in global_variables:
                if isinstance(global_variables[key], dict) and isinstance(value, dict):
                    global_variables[key].update(value)
                else:
                    global_variables[key] = value
            else:
                global_variables[key] = value
        logging.info(f"Global settings loaded from {settings_path}")
except Exception as e:
    logging.warning(f"Failed to load global settings: {e}")

# Validate table IDs are sequential
def validate_table_ids():
    """Check each .sldtbl file for sequential IDs across all subtables."""
    tables_dir = "tables"
    if not os.path.isdir(tables_dir):
        logging.warning(f"Tables directory '{tables_dir}' not found, skipping validation.")
        return
    
    table_files = [f for f in os.listdir(tables_dir) if f.endswith(".sldtbl")]
    
    if not table_files:
        logging.info("No table files found to validate.")
        return
    
    for table_file in sorted(table_files):
        try:
            table_path = os.path.join(tables_dir, table_file)
            with open(table_path, 'r') as f:
                table_data = json.load(f)
            
            table_name = table_data.get("prettyname", table_file)
            tables = table_data.get("tables", {})
            
            # Extract ALL IDs from all subtables in this file
            all_ids = []
            for subtable_name, items in tables.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict) and "id" in item:
                        all_ids.append(item["id"])
            
            if not all_ids:
                logging.info(f"Table '{table_name}': No items with IDs found.")
                continue
            
            all_ids.sort()
            min_id = all_ids[0]
            max_id = all_ids[-1]
            next_id = max_id + 1
            
            # Check for sequential IDs across all subtables
            expected_ids = set(range(min_id, max_id + 1))
            actual_ids = set(all_ids)
            
            if expected_ids == actual_ids:
                logging.info(f"Table '{table_name}': IDs valid (sequential from {min_id} to {max_id}). Next ID: {next_id}")
            else:
                missing_ids = sorted(expected_ids - actual_ids)
                logging.error(f"Table '{table_name}': ID sequence broken! Missing IDs: {missing_ids}. Last ID: {max_id}, Next ID: {next_id}")
        
        except Exception as e:
            logging.error(f"Failed to validate table '{table_file}': {e}")

validate_table_ids()

currentsave = None

emptysave = {
    "charactername": "",
    "stats": {
        "Aim": 0,
        "Strength": 0,
        "Agility": 0,
        "Intelligence": 0,
        "Charisma": 0,
        "Perception": 0,
        "Resistance": 0,
        "Stealth": 0,
        "Luck": 0
    },
    "hands": {
        "encumbrance_modifier": 0.5,
        "capacity": 50,
        "items": []
    },
    "equipment": {
        "head": None,
        "torso": None,
        "left wrist": None,
        "right wrist": None,
        "left hand": None,
        "right hand": None,
        "legs": None,
        "feet": None,
        "neck": None,
        "chest": None,
        "back": None,
        "waist": None,
        "waistband": None,
        "left shoulder": None,
        "right shoulder": None,
        "left arm": None,
        "right arm": None,
        "left leg": None,
        "right leg": None
    },
    "encumbrance": 0,
    "encumbered_threshold": 50,
    "encumbered": {"value": False, "level": 0},
    "storage": [],
    "money": 0
}

# Function to populate equipment items with their subslots from table
def populate_equipment_with_subslots(save_data):
    """Populate equipment items with subslots from the current table."""
    try:
        table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
        if not table_files:
            return save_data
        
        with open(table_files[0], 'r') as f:
            table_data = json.load(f)
        
        equipment_items = table_data.get("tables", {}).get("equipment", [])
        equipment_map = {item.get("id"): item for item in equipment_items}
        
        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            if equipped_item and isinstance(equipped_item, dict):
                item_id = equipped_item.get("id")
                if item_id is not None and item_id in equipment_map:
                    table_item = equipment_map[item_id]
                    if "subslots" in table_item and "subslots" not in equipped_item:
                        equipped_item["subslots"] = [{
                            "name": subslot.get("name"),
                            "slot": subslot.get("slot"),
                            "current": subslot.get("current", None)
                        } for subslot in table_item["subslots"]]
                        logging.debug(f"Added {len(equipped_item['subslots'])} subslots to equipped item ID {item_id} in slot {slot_name}")
        
        # Also check items in containers (storage, hands, equipment subcontainers)
        for item in save_data.get("storage", []):
            if isinstance(item, dict):
                add_subslots_to_item(item)
        
        if "hands" in save_data and "items" in save_data["hands"]:
            for item in save_data["hands"]["items"]:
                if isinstance(item, dict):
                    add_subslots_to_item(item)
        
        # Check equipment slots for nested containers
        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            if equipped_item and isinstance(equipped_item, dict) and "items" in equipped_item:
                for item in equipped_item["items"]:
                    if isinstance(item, dict):
                        add_subslots_to_item(item)
                        
    except Exception as e:
        logging.warning(f"Failed to populate equipment subslots: {e}")
    
    return save_data

def add_subslots_to_item(item):
    """Add subslots to an item if it has them in the table."""
    try:
        if not item:
            return item
        
        # Don't re-add if already present
        if "subslots" in item:
            return item
        
        table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
        if not table_files:
            return item
        
        with open(table_files[0], 'r') as f:
            table_data = json.load(f)
        
        equipment_items = table_data.get("tables", {}).get("equipment", [])
        equipment_map = {it.get("id"): it for it in equipment_items}
        
        item_id = item.get("id")
        if item_id is not None and item_id in equipment_map:
            table_item = equipment_map[item_id]
            if "subslots" in table_item:
                item["subslots"] = [{
                    "name": subslot.get("name"),
                    "slot": subslot.get("slot"),
                    "current": subslot.get("current", None)
                } for subslot in table_item["subslots"]]
                logging.debug(f"Added {len(item['subslots'])} subslots to item ID {item_id} ({item.get('name')})")
    except Exception as e:
        logging.warning(f"Failed to add subslots to item: {e}")
    
    return item

def update_item_keys_from_table(save_data):
    """Update item keys from table data, preserving variable keys (quantity, current state, etc.)"""
    try:
        table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
        if not table_files:
            logging.warning("No table files found for item key update")
            return save_data
        
        with open(table_files[0], 'r') as f:
            table_data = json.load(f)
        
        # Build item map from all tables
        all_items_map = {}
        for table_name, items in table_data.get("tables", {}).items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "id" in item:
                        all_items_map[item["id"]] = item
        
        # Variable keys that should be preserved from save data (not overwritten from table)
        variable_keys = {
            "quantity", "current", "items", "subslots", "uses_left", "hits_left",
            "battery_life", "loaded", "chambered", "rounds", "belt_rounds"
        }
        
        def update_item(item):
            """Update a single item's keys from table"""
            if not isinstance(item, dict) or "id" not in item:
                return item
            
            item_id = item.get("id")
            if item_id not in all_items_map:
                return item
            
            table_item = all_items_map[item_id]
            
            # Store variable data
            preserved_data = {key: item[key] for key in variable_keys if key in item}
            
            # Update with table data
            for key, value in table_item.items():
                if key not in variable_keys:
                    item[key] = value
            
            # Restore variable data
            for key, value in preserved_data.items():
                item[key] = value
            
            # Recursively update items in subslots if present
            if "subslots" in item:
                for subslot in item["subslots"]:
                    if isinstance(subslot, dict) and subslot.get("current"):
                        update_item(subslot["current"])
            
            # Recursively update items in containers
            if "items" in item and isinstance(item["items"], list):
                for contained_item in item["items"]:
                    update_item(contained_item)
            
            return item
        
        # Update items in storage
        for item in save_data.get("storage", []):
            update_item(item)
        
        # Update items in hands
        if "hands" in save_data and "items" in save_data["hands"]:
            for item in save_data["hands"]["items"]:
                update_item(item)
        
        # Update equipped items
        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            if equipped_item and isinstance(equipped_item, dict):
                update_item(equipped_item)
        
        logging.info("Item keys updated from table data")
        
    except Exception as e:
        logging.error(f"Failed to update item keys from table: {e}")
    
    return save_data

persistentdata = {
    "last_loaded_save": None,
    "save_uuids": {},
    "lootcrate_uuids": {},
    "transfer_uuids": {}
}

dm_users = [base64.b64decode(user).decode('utf-8').lower() for user in dm_users]

for user in dm_users:
    if user in os.getlogin().lower():
        if not global_variables["dmmode"]["value"] and not global_variables["dmmode"]["forced"]:
            global_variables["dmmode"]["value"] = True
            logging.info(f"DM user '{user}' detected. DM mode toggled on.")
        elif global_variables["dmmode"]["value"]:
            logging.info(f"DM user '{user}' detected. DM mode already active.")
        else:
            logging.info(f"DM user '{user}' detected. DM mode is forced off.")

class App:
    def _save_persistent_data(self):
        """Persist metadata like last_loaded_save and UUID map."""
        try:
            persistent_path = os.path.join(saves_folder, "persistent_data.sldsv")
            pickled_persistent = pickle.dumps(persistentdata)
            encoded_persistent = base64.b85encode(pickled_persistent).decode('utf-8')
            with open(persistent_path, 'w') as f:
                f.write(encoded_persistent)
            logging.info(f"Persistent data saved to {persistent_path}")
        except Exception as e:
            logging.error(f"Failed to save persistent data: {e}")
    def _save_file(self, data):
        if currentsave is None:
            logging.error("No current save file to save data to.")
            return
        else:
            # Build absolute path and ensure extension
            if os.path.isabs(currentsave):
                save_path = currentsave
            else:
                save_path = os.path.join(saves_folder, currentsave)
            if not save_path.endswith(".sldsv"):
                save_path += ".sldsv"
            try:
                with open(save_path, 'w') as f:
                    json.dump(data, f, indent=4)
                logging.info(f"Data saved to {save_path}")
            except Exception as e:
                logging.error(f"Failed to save data to {currentsave}: {e}")
        self._save_persistent_data()
    def _load_file(self, save_filename):
        # Load persistent data (base85+pickle) first
        try:
            persistent_path = os.path.join(saves_folder, "persistent_data.sldsv")
            if os.path.exists(persistent_path):
                with open(persistent_path, 'r') as f:
                    encoded_persistent = f.read()
                pickled_persistent = base64.b85decode(encoded_persistent.encode('utf-8'))
                loaded_persistent = pickle.loads(pickled_persistent)
                if isinstance(loaded_persistent, dict):
                    persistentdata.update(loaded_persistent)
                    logging.info(f"Persistent data loaded from {persistent_path}")
                else:
                    logging.warning(f"Persistent data in {persistent_path} is not a dict; got {type(loaded_persistent)}")
            else:
                logging.info("No persistent data file found, using defaults")
        except Exception as e:
            logging.warning(f"Failed to load persistent data: {e}")

        # If no specific save requested, we're done
        if save_filename is None:
            return None

        # Build absolute path and ensure extension
        if os.path.isabs(save_filename):
            save_path = save_filename
        else:
            save_path = os.path.join(saves_folder, save_filename)
        if not save_path.endswith('.sldsv'):
            save_path += '.sldsv'
        if not os.path.exists(save_path):
            logging.error(f"Save file '{save_path}' does not exist.")
            return None

        try:
            with open(save_path, 'r') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logging.error(f"Loaded data from {save_path} is not a dict; got {type(data)}")
                return None
            logging.info(f"Data loaded from {save_path}")
            if save_path.endswith('.sldsv'):
                parts = os.path.basename(save_path).rsplit('_', 1)
                if len(parts) == 2:
                    uuid_part = parts[1].replace('.sldsv', '')
                    persistentdata["last_loaded_save"] = uuid_part
                    logging.info(f"Updated last_loaded_save to UUID: {uuid_part}")
            # Populate equipment with subslots from table
            data = populate_equipment_with_subslots(data)
            # Update item keys from table (preserve variable keys)
            data = update_item_keys_from_table(data)
            return data
        except Exception as e:
            logging.error(f"Failed to load data from '{save_path}': {e}")
            return None
    def __init__(self):
        customtkinter.set_appearance_mode(appearance_settings["appearance_mode"])
        
        # Load the correct theme path (handle custom themes)
        theme_name = appearance_settings["color_theme"]
        builtin_themes = ["dark-blue", "blue", "green"]
        if theme_name not in builtin_themes:
            # It's a custom theme, build the full path
            custom_theme_path = os.path.join(os.getcwd(), "themes", f"{theme_name}.json")
            if os.path.exists(custom_theme_path):
                customtkinter.set_default_color_theme(custom_theme_path)
            else:
                logging.warning(f"Custom theme '{custom_theme_path}' not found, falling back to dark-blue")
                appearance_settings["color_theme"] = "dark-blue"
                customtkinter.set_default_color_theme("dark-blue")
        else:
            customtkinter.set_default_color_theme(theme_name)
        self.root = customtkinter.CTk()
        self.root.title("DOOM Tools")
        self.root.geometry(appearance_settings["resolution"])
        self.root.resizable(False, False)
        if appearance_settings["borderless"]:
            self.root.overrideredirect(True)
        self.root.attributes('-fullscreen', appearance_settings["fullscreen"])
        self._load_file(None)
        if persistentdata.get("last_loaded_save"):
            last_save_uuid = persistentdata["last_loaded_save"]
            last_save_name = persistentdata.get("save_uuids", {}).get(last_save_uuid)
            if not last_save_name:
                # Fallback: find a matching file on disk
                pattern = os.path.join(saves_folder, f"*_{last_save_uuid}.sldsv")
                matches = glob.glob(pattern)
                if matches:
                    last_save_name = os.path.basename(matches[0]).replace(f"_{last_save_uuid}.sldsv", "")
                    persistentdata["save_uuids"][last_save_uuid] = last_save_name
                    self._save_persistent_data()
                else:
                    logging.warning(f"Last save UUID {last_save_uuid} not found in save_uuids")
            if last_save_name:
                save_filename = f"{last_save_name}_{last_save_uuid}.sldsv"
                loaded_data = self._load_file(save_filename)
                if loaded_data:
                    global currentsave
                    currentsave = save_filename.replace(".sldsv", "")
                    logging.info(f"Automatically loaded last save: {save_filename}")
                else:
                    logging.warning(f"Failed to load last save: {save_filename}")
        self._build_main_menu()
        self.root.mainloop()
    def _play_ui_sound(self, sound_filename):
        sound_path = os.path.join("sounds", "ui", sound_filename + ".ogg")
        if os.path.exists(sound_path):
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                logging.debug(f"Played UI sound: {sound_filename}")
            except Exception as e:
                logging.warning(f"Failed to play sound '{sound_filename}': {e}")
    def _create_sound_button(self, parent, text, command, **kwargs):
        def safe_command():
            try:
                self._play_ui_sound("click")
                command()
            except Exception as e:
                logging.exception("Button command failed for '%s': %s", text, e)
        button = customtkinter.CTkButton(
            parent, text=text, command=safe_command, **kwargs
        )
        def on_hover(e):
            if button.cget("state") != "disabled":
                self._play_ui_sound("hover")
        button.bind("<Enter>", on_hover)
        return button
    def _safe_sound_play(self, directory, sound_filename):
        """Play a sound safely. Accepts either a bare name (without extension) or a full path."""
        # If a full path with extension is passed, use it directly
        if os.path.isabs(sound_filename) or sound_filename.endswith((".wav", ".ogg")):
            sound_path = sound_filename
        else:
            sound_path = os.path.join("sounds", directory, sound_filename + ".ogg")

        if os.path.exists(sound_path):
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                logging.debug(f"Played sound file: {sound_path}")
            except Exception as e:
                logging.warning(f"Failed to play sound '{sound_path}': {e}")
    def _popup_show_info(self, title, message, sound="popup"):
        self._play_ui_sound(sound)
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("450x200")
        popup.transient(self.root)
        
        label = customtkinter.CTkLabel(popup, text=message, wraplength=400, font=customtkinter.CTkFont(size=13))
        label.pack(pady=30, padx=20)
        
        def close_popup():
            self._play_ui_sound("click")
            popup.destroy()
        
        ok_button = customtkinter.CTkButton(popup, text="OK", command=close_popup, width=120, height=35)
        ok_button.pack(pady=10)
        
        popup.update_idletasks()
        popup.deiconify()
        popup.grab_set()
        popup.lift()
        popup.focus()
    
    def _popup_confirm(self, title, message, on_confirm):
        self._play_ui_sound("popup")
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("450x220")
        popup.transient(self.root)
        
        label = customtkinter.CTkLabel(popup, text=message, wraplength=400, font=customtkinter.CTkFont(size=13))
        label.pack(pady=30, padx=20)
        
        button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=10)
        
        def confirm():
            self._play_ui_sound("click")
            popup.destroy()
            on_confirm()
        
        def cancel():
            self._play_ui_sound("click")
            popup.destroy()
        
        yes_button = customtkinter.CTkButton(button_frame, text="Yes", command=confirm, width=120, height=35)
        yes_button.pack(side="left", padx=10)
        no_button = customtkinter.CTkButton(button_frame, text="No", command=cancel, width=120, height=35)
        no_button.pack(side="left", padx=10)
        
        popup.update_idletasks()
        popup.deiconify()
        popup.grab_set()
        popup.lift()
        popup.focus()
    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        logging.debug("Cleared window called")
    def _build_main_menu(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        title_label = customtkinter.CTkLabel(main_frame, text="DOOM Tools", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        version_label = customtkinter.CTkLabel(main_frame, text=f"Version: {version}", font=customtkinter.CTkFont(size=16))
        version_label.pack()
        current_character = customtkinter.CTkLabel(main_frame, text=f"Current Character: {currentsave if currentsave else 'None'}", font=customtkinter.CTkFont(size=14))
        current_character.pack(pady=10)
        loot_button = self._create_sound_button(main_frame, "Looting", self._open_loot_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        loot_button.pack(pady=10)
        business_button = self._create_sound_button(main_frame, "Businesses", self._open_business_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        business_button.pack(pady=10)
        inventoryman_button = self._create_sound_button(main_frame, "Inventory Manager", self._open_inventory_manager_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        inventoryman_button.pack(pady=10)
        combatmode_button = self._create_sound_button(main_frame, "Combat Mode", self._open_combat_mode_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        combatmode_button.pack(pady=10)
        exitb_button = self._create_sound_button(main_frame, "Exit", self._safe_exit, width=500, height=50, font=customtkinter.CTkFont(size=16))
        exitb_button.pack(pady=10)
        settings_button = self._create_sound_button(main_frame, "Settings", self._open_settings, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        settings_button.pack(pady=10)
        if global_variables["devmode"]["value"]:
            devtools_button = self._create_sound_button(main_frame, "Developer Tools", self._open_dev_tools, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
            devtools_button.pack(pady=10)
        else:
            devtools_button = customtkinter.CTkButton(main_frame, text="Developer Tools", width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled")
            devtools_button.pack(pady=10)
        if global_variables["dmmode"]["value"]:
            dmmode_button = self._create_sound_button(main_frame, "DM Tools", self._open_dm_tools, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
            dmmode_button.pack(pady=10)
        else:
            dmmode_button = customtkinter.CTkButton(main_frame, text="DM Tools", width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled")
            dmmode_button.pack(pady=10)
        if currentsave is None:
            currentsave_label = customtkinter.CTkLabel(main_frame, text="No save loaded. Please load a save to enable tools.", font=customtkinter.CTkFont(size=14), text_color="red")
            currentsave_label.pack(pady=20)
    def _open_loot_tool(self):
        logging.info("Looting definition called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="Looting", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table files found.", sound="error")
                return
            
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
            
            lootcrates = table_data.get("lootcrates", [])

            # Also load DM-created loot crates from the lootcrates folder (base85+pickle)
            crate_files = glob.glob(os.path.join("lootcrates", f"*{global_variables['lootcrate_extension']}"))
            for crate_file in crate_files:
                try:
                    with open(crate_file, 'r') as cf:
                        encoded_data = cf.read()
                    pickled_data = base64.b85decode(encoded_data.encode('utf-8'))
                    crate_data = pickle.loads(pickled_data)
                    crate_data["_file_path"] = crate_file  # Track file path for deletion
                    lootcrates.append(crate_data)
                    logging.info(f"Loaded custom loot crate: {crate_data.get('name', os.path.basename(crate_file))}")
                except Exception as e:
                    logging.warning(f"Failed to load loot crate file {crate_file}: {e}")
            if not lootcrates:
                error_label = customtkinter.CTkLabel(main_frame, text="No loot crates defined in table.", font=customtkinter.CTkFont(size=14), text_color="orange")
                error_label.pack(pady=20)
                back_button = self._create_sound_button(main_frame, "Back", lambda: [self._clear_window(), self._build_main_menu()], width=500, height=50, font=customtkinter.CTkFont(size=16))
                back_button.pack(pady=20)
                return
            
            # Create scrollable frame for loot crates
            scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
            scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            def loot_crate(crate, crate_file_path=None):
                """Open loot crate selection menu"""
                try:
                    # Check if locked (TODO: implement lockpicking check)
                    if crate.get("locked", False):
                        logging.info(f"Crate '{crate.get('name')}' is locked but lockpicking not implemented yet")
                        self._popup_show_info("Locked", "This crate is locked. Lockpicking not implemented yet.", sound="error")
                        return
                    
                    save_path = os.path.join(saves_folder, currentsave + ".sldsv")
                    with open(save_path, 'r') as f:
                        save_data = json.load(f)
                    
                    # Resolve all items from loot_table entries dynamically
                    available_items = []
                    for entry in crate.get("loot_table", []):
                        items_to_add = self._resolve_loot_entry(entry, table_data, save_data)
                        for item in items_to_add:
                            item_copy = {k: v for k, v in item.items() if k != "table_category"}
                            item_copy = add_subslots_to_item(item_copy)
                            available_items.append(item_copy)
                    
                    # Open selection menu
                    self._open_loot_selection_menu(crate, available_items, save_data, save_path, crate_file_path, table_data)
                    
                except Exception as e:
                    logging.error(f"Failed to open loot crate: {e}")
                    self._popup_show_info("Error", f"Failed to open loot crate: {e}", sound="error")
            
            # Display each loot crate
            for crate in lootcrates:
                crate_frame = customtkinter.CTkFrame(scroll_frame)
                crate_frame.pack(fill="x", pady=10, padx=10)
                crate_frame.grid_columnconfigure(1, weight=1)
                
                # Crate header
                header_frame = customtkinter.CTkFrame(crate_frame, fg_color="transparent")
                header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
                header_frame.grid_columnconfigure(0, weight=1)
                
                name_label = customtkinter.CTkLabel(
                    header_frame,
                    text=crate.get("name", "Unknown Crate"),
                    font=customtkinter.CTkFont(size=14, weight="bold"),
                    anchor="w"
                )
                name_label.grid(row=0, column=0, sticky="w")
                
                rarity_label = customtkinter.CTkLabel(
                    header_frame,
                    text=f"Rarity: {crate.get('rarity', 'N/A')}",
                    font=customtkinter.CTkFont(size=11),
                    text_color="gray",
                    anchor="e"
                )
                rarity_label.grid(row=0, column=1, sticky="e", padx=(10, 0))
                
                # Description
                if "description" in crate and crate["description"]:
                    desc_label = customtkinter.CTkLabel(
                        crate_frame,
                        text=crate["description"],
                        font=customtkinter.CTkFont(size=11),
                        text_color="gray",
                        wraplength=400,
                        justify="left",
                        anchor="w"
                    )
                    desc_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10), padx=10)
                
                # Loot contents preview
                contents_text = self._get_loot_crate_contents_preview(crate, table_data)
                if contents_text:
                    contents_label = customtkinter.CTkLabel(
                        crate_frame,
                        text=contents_text,
                        font=customtkinter.CTkFont(size=10),
                        text_color="orange",
                        wraplength=400,
                        justify="left",
                        anchor="w"
                    )
                    contents_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10), padx=10)
                
                # Loot button
                crate_file = crate.get("_file_path")
                loot_button = self._create_sound_button(
                    crate_frame,
                    "Loot Crate",
                    lambda c=crate, f=crate_file: loot_crate(c, f),
                    width=150,
                    height=40,
                    font=customtkinter.CTkFont(size=12)
                )
                loot_button.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
            
            back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda: [self._clear_window(), self._build_main_menu()], width=500, height=50, font=customtkinter.CTkFont(size=16))
            back_button.pack(pady=20)
            
        except Exception as e:
            logging.error(f"Failed to load loot tool: {e}")
            self._popup_show_info("Error", f"Failed to load loot tool: {e}", sound="error")
    
    def _resolve_loot_entry(self, entry, table_data, save_data=None):
        """Resolve a loot table entry to actual items with rarity weighting and luck effects"""
        items = []
        try:
            if entry.get("type") == "table":
                # Entry references a table (e.g., "equipment", "pistols")
                table_name = entry.get("table")
                requested_rarity = entry.get("rarity")
                table = table_data.get("tables", {}).get(table_name, [])
                
                # Get luck stat from save data for weight modification
                luck_stat = 0
                if save_data:
                    luck_stat = save_data.get("stats", {}).get("luck", 0)
                
                # Get rarity weights and special chance from table_data
                rarity_weights = table_data.get("rarity_weights", {})
                special_chance = rarity_weights.get("Special Chance", 0)
                luck_effect = rarity_weights.get("Luck Effect", 1.5)
                
                # Check for special item override
                special_roll = random.random() * 100
                if special_roll < special_chance:
                    # Pull from special_items table instead
                    special_table = table_data.get("tables", {}).get("special_items", [])
                    if special_table:
                        # Filter by rarity if specified
                        if requested_rarity:
                            special_items = [item for item in special_table if item.get("rarity") == requested_rarity]
                        else:
                            special_items = special_table
                        
                        if special_items:
                            selected_item = random.choice(special_items)
                            item_copy = selected_item.copy()
                            item_copy["table_category"] = "special_items"
                            items.append(item_copy)
                            return items
                
                # Normal rarity-weighted selection
                # Build weighted selection pool based on rarity_weights
                if requested_rarity:
                    # Filter table to only items with requested rarity
                    matching_items = [item for item in table if item.get("rarity") == requested_rarity]
                    
                    # Apply rarity weight for the requested rarity
                    weight = rarity_weights.get(requested_rarity, 1)
                    
                    # Apply luck modifier (increases rarer item weights)
                    if luck_stat > 0:
                        weight = weight * (1 + (luck_stat * luck_effect / 100))
                    
                    if matching_items:
                        selected_item = random.choice(matching_items)
                        item_copy = selected_item.copy()
                        item_copy["table_category"] = table_name
                        items.append(item_copy)
                else:
                    # No specific rarity requested - use weighted distribution
                    # Build weighted pool of all items based on their rarity
                    weighted_pool = []
                    for item in table:
                        item_rarity = item.get("rarity", "Common")
                        weight = rarity_weights.get(item_rarity, 1)
                        
                        # Apply luck modifier
                        if luck_stat > 0:
                            weight = weight * (1 + (luck_stat * luck_effect / 100))
                        
                        # Add item to pool multiple times based on weight
                        weighted_pool.extend([item] * int(weight))
                    
                    if weighted_pool:
                        selected_item = random.choice(weighted_pool)
                        item_copy = selected_item.copy()
                        item_copy["table_category"] = table_name
                        items.append(item_copy)
                    
            elif entry.get("type") == "id":
                # Entry references a specific item by ID
                item_id = entry.get("id")
                # Search all tables for the item with matching ID
                for table_name, table_items in table_data.get("tables", {}).items():
                    for item in table_items:
                        if item.get("id") == item_id:
                            item_copy = item.copy()
                            item_copy["table_category"] = table_name
                            items.append(item_copy)
                            return items  # Found it, return early
        except Exception as e:
            logging.error(f"Failed to resolve loot entry {entry}: {e}")
        
        return items
    
    def _get_loot_crate_contents_preview(self, crate, table_data):
        """Generate a preview of what could be looted from a crate"""
        info_lines = []
        try:
            # Show locked status and pulls
            locked_status = "Locked" if crate.get("locked", False) else "Unlocked"
            pulls = crate.get("pulls", 3)
            if isinstance(pulls, dict):
                pulls_text = f"{pulls.get('min')}-{pulls.get('max')}"
            else:
                pulls_text = str(pulls)
            info_lines.append(f"{locked_status} | Pulls: {pulls_text}")
            
            # Show number of loot table entries (items determined at loot time)
            num_entries = len(crate.get("loot_table", []))
            info_lines.append(f"Loot entries: {num_entries}")
        except Exception as e:
            logging.error(f"Failed to generate loot preview: {e}")
        
        if info_lines:
            return "\n".join(info_lines)
        return ""
    
    def _open_loot_selection_menu(self, crate, available_items, save_data, save_path, crate_file_path, table_data):
        """Display items from a loot crate and allow selection with encumbrance checking"""
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(
            main_frame,
            text=f"Loot: {crate.get('name', 'Unknown Crate')}",
            font=customtkinter.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=20)
        
        # Create scrollable frame for items
        scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Track selected items and their checkboxes
        selected_items_checkboxes = {}
        
        def update_weight_display():
            """Update total weight display based on selected items"""
            selected_weight = 0.0
            for idx, checkbox in selected_items_checkboxes.items():
                if checkbox.get():
                    item = available_items[idx]
                    qty = item.get("quantity", 1)
                    weight = item.get("weight", 0) * qty
                    selected_weight += weight
            
            current_encumbrance = self._calculate_encumbrance_status(save_data)
            new_total_weight = current_encumbrance["total_weight"] + selected_weight
            new_encumbrance = max(new_total_weight - current_encumbrance["total_reduction"], 0.0)
            
            threshold = save_data.get("encumbered_threshold", 50)
            
            weight_text = f"Selected Weight: {self._format_weight(selected_weight)}\n"
            weight_text += f"New Total: {self._format_weight(new_total_weight)}\n"
            weight_text += f"Encumbrance: {self._format_weight(new_encumbrance)} / {self._format_weight(threshold)}"
            
            if new_encumbrance > threshold:
                weight_text += " ⚠️ ENCUMBERED"
                weight_label.configure(text_color="red")
            else:
                weight_label.configure(text_color="white")
            
            weight_label.configure(text=weight_text)
        
        # Display each available item
        for i, item in enumerate(available_items):
            item_frame = customtkinter.CTkFrame(scroll_frame)
            item_frame.pack(fill="x", pady=10, padx=10)
            item_frame.grid_columnconfigure(0, weight=1)
            
            # Checkbox for selection
            checkbox = customtkinter.CTkCheckBox(
                item_frame,
                text="",
                command=update_weight_display
            )
            checkbox.grid(row=0, column=0, sticky="w", padx=(0, 10))
            checkbox.select()  # Selected by default
            selected_items_checkboxes[i] = checkbox
            
            # Item info
            item_info_text = f"{item.get('name', 'Unknown')} - {self._format_weight(item.get('weight', 0))}"
            if item.get("quantity", 1) > 1:
                item_info_text += f" x{item.get('quantity')}"
            if item.get("value"):
                item_info_text += f" [${item.get('value')}]"
            
            item_label = customtkinter.CTkLabel(
                item_frame,
                text=item_info_text,
                font=customtkinter.CTkFont(size=12),
                anchor="w"
            )
            item_label.grid(row=0, column=1, sticky="ew", padx=10)
            
            # Item description
            if item.get("description"):
                desc_label = customtkinter.CTkLabel(
                    item_frame,
                    text=item.get("description"),
                    font=customtkinter.CTkFont(size=10),
                    text_color="gray",
                    wraplength=600,
                    justify="left",
                    anchor="w"
                )
                desc_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 0))
        
        # Weight display frame
        weight_frame = customtkinter.CTkFrame(main_frame)
        weight_frame.pack(fill="x", padx=20, pady=10)
        
        weight_label = customtkinter.CTkLabel(
            weight_frame,
            text="",
            font=customtkinter.CTkFont(size=12),
            justify="left",
            anchor="w"
        )
        weight_label.pack(fill="x", padx=10, pady=10)
        
        # Button frame
        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=20)
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        def take_selected():
            """Add selected items to hands and handle remaining items"""
            try:
                taken_items = []
                remaining_items = []
                
                for idx, checkbox in selected_items_checkboxes.items():
                    if checkbox.get():
                        item = available_items[idx]
                        save_data["hands"]["items"].append(item)
                        taken_items.append(item)
                    else:
                        remaining_items.append(available_items[idx])
                
                # Save
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
                # Handle crate file: delete only if all items taken, otherwise save remaining items
                if crate_file_path and os.path.exists(crate_file_path):
                    if remaining_items:
                        # Save remaining items back to the crate file
                        updated_crate = crate.copy()
                        updated_crate["loot_table"] = []  # Clear the loot table
                        for item in remaining_items:
                            updated_crate["loot_table"].append({"type": "id", "id": item.get("id"), "rarity": item.get("rarity")})
                        
                        pickled_crate = pickle.dumps(updated_crate)
                        encoded_crate = base64.b85encode(pickled_crate).decode('utf-8')
                        with open(crate_file_path, 'w') as cf:
                            cf.write(encoded_crate)
                        logging.info(f"Updated crate file with {len(remaining_items)} remaining items: {crate_file_path}")
                    else:
                        # All items taken, delete the crate file
                        os.remove(crate_file_path)
                        logging.info(f"Deleted used loot crate file: {crate_file_path}")
                
                item_summary = ", ".join([f"{item.get('name', 'Unknown')}" for item in taken_items])
                logging.info(f"Looted crate '{crate.get('name')}': {item_summary}")
                self._popup_show_info("Success", f"Took {len(taken_items)} item(s): {item_summary}", sound="success")
                self._open_loot_tool()
            except Exception as e:
                logging.error(f"Failed to take items: {e}")
                self._popup_show_info("Error", f"Failed to take items: {e}", sound="error")
        
        def take_none():
            """Close without taking anything"""
            self._open_loot_tool()
        
        take_button = self._create_sound_button(
            button_frame,
            "Take Selected Items",
            take_selected,
            width=250,
            height=50,
            font=customtkinter.CTkFont(size=14)
        )
        take_button.grid(row=0, column=0, padx=(0, 10))
        
        cancel_button = self._create_sound_button(
            button_frame,
            "Leave Crate",
            take_none,
            width=250,
            height=50,
            font=customtkinter.CTkFont(size=14)
        )
        cancel_button.grid(row=0, column=1, padx=(10, 0))
        
        # Initial weight display
        update_weight_display()
    
    def _open_business_tool(self):
        logging.info("Business definition called")
        self._popup_show_info("Businesses", "Businesses are under development.")
    def _open_inventory_manager_tool(self):
        logging.info("Inventory Manager definition called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="Inventory Manager", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        character_management_button = self._create_sound_button(main_frame, "Character Management", lambda: [self._clear_window(), self._open_character_management()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        character_management_button.pack(pady=20)
        inventory_management_button = self._create_sound_button(main_frame, "Inventory Management", lambda: [self._clear_window(), self._open_inventory_management()], width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        inventory_management_button.pack(pady=20)
        item_equip_button = self._create_sound_button(main_frame, "Item Equipping", lambda: [self._clear_window(), self._open_item_equipping()], width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        item_equip_button.pack(pady=20)
        back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda: [self._clear_window(), self._build_main_menu()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        back_button.pack(pady=20)
        
        if currentsave is None:
            warning_label = customtkinter.CTkLabel(main_frame, text="Load or create a character to access inventory features.", font=customtkinter.CTkFont(size=14), text_color="orange")
            warning_label.pack(pady=10)
    def _open_character_management(self):
        logging.info("Character Management definition called")
        create_new_character_button = self._create_sound_button(self.root, "Create New Character", lambda: [self._clear_window(), self._create_new_character()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        create_new_character_button.pack(pady=20)
        load_existing_character_button = self._create_sound_button(
            self.root,
            "Load Existing Character",
            lambda: [self._clear_window(), self._load_existing_character()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16),
            state="disabled" if not os.listdir(saves_folder) or all(
                f in ["persistent_data.sldsv", "settings.sldsv"] or f.endswith(".sldsv.sldsv")
                for f in os.listdir(saves_folder)
            ) else "normal"
        )
        load_existing_character_button.pack(pady=20)
        
        view_stats_button = self._create_sound_button(
            self.root,
            "View Loaded Character Stats",
            self._view_character_stats,
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16),
            state="disabled" if currentsave is None else "normal"
        )
        view_stats_button.pack(pady=20)
        
        return_button = self._create_sound_button(self.root, "Return to Inventory Manager", lambda: [self._clear_window(), self._open_inventory_manager_tool()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        return_button.pack(pady=20)
    
    def _view_character_stats(self):
        logging.info("View Character Stats called")
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        save_filename = currentsave + ".sldsv"
        save_data = self._load_file(save_filename)
        
        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound="error")
            return
        
        # Calculate encumbrance status
        encumbrance_info = self._calculate_encumbrance_status(save_data)
        
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title = customtkinter.CTkLabel(main_frame, text=f"Character: {save_data.get('charactername', 'Unknown')}", font=customtkinter.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=(0, 20))
        
        scroll = customtkinter.CTkScrollableFrame(main_frame, width=800, height=500)
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)
        
        # Stats section
        stats_label = customtkinter.CTkLabel(scroll, text="Base Stats", font=customtkinter.CTkFont(size=16, weight="bold"))
        stats_label.pack(pady=(10, 15), anchor="w", padx=20)
        
        stats = save_data.get("stats", {})
        for stat_name, stat_value in stats.items():
            # Calculate agility penalty based on encumbrance
            display_value = stat_value
            agility_penalty_text = ""
            
            if stat_name == "Agility" and encumbrance_info["encumbrance_level"] > 0:
                display_value = stat_value - encumbrance_info["encumbrance_level"]
                agility_penalty_text = f" (Base: {stat_value}, Penalty: -{encumbrance_info['encumbrance_level']})"
            
            stat_frame = customtkinter.CTkFrame(scroll, fg_color="transparent")
            stat_frame.pack(fill="x", pady=5, padx=30)
            
            stat_label = customtkinter.CTkLabel(
                stat_frame,
                text=f"{stat_name}: {display_value:+d}{agility_penalty_text}",
                font=customtkinter.CTkFont(size=12),
                anchor="w"
            )
            stat_label.pack(fill="x")
        
        # Encumbrance section
        enc_label = customtkinter.CTkLabel(scroll, text="Encumbrance Status", font=customtkinter.CTkFont(size=16, weight="bold"))
        enc_label.pack(pady=(20, 15), anchor="w", padx=20)
        
        enc_items = [
            ("Total Weight", self._format_weight(encumbrance_info["total_weight"])),
            ("Encumbrance", self._format_weight(encumbrance_info['encumbrance'])),
            ("Encumbrance Threshold", self._format_weight(encumbrance_info['threshold'])),
            ("Encumbrance Level", f"{encumbrance_info['encumbrance_level']}"),
            ("Status", "Encumbered" if encumbrance_info["is_encumbered"] else "Not Encumbered")
        ]
        
        for label_text, value_text in enc_items:
            enc_frame = customtkinter.CTkFrame(scroll, fg_color="transparent")
            enc_frame.pack(fill="x", pady=3, padx=30)
            
            label = customtkinter.CTkLabel(
                enc_frame,
                text=f"{label_text}: {value_text}",
                font=customtkinter.CTkFont(size=12),
                anchor="w"
            )
            label.pack(fill="x")
        
        # Other info
        other_label = customtkinter.CTkLabel(scroll, text="Other Info", font=customtkinter.CTkFont(size=16, weight="bold"))
        other_label.pack(pady=(20, 15), anchor="w", padx=20)
        
        other_items = [
            ("Money", f"${save_data.get('money', 0)}"),
            ("Equipment Slots", f"{len([s for s in save_data.get('equipment', {}).values() if s is not None])}/{len(save_data.get('equipment', {}))}"),
            ("Storage Items", f"{len(save_data.get('storage', []))}")
        ]
        
        for label_text, value_text in other_items:
            other_frame = customtkinter.CTkFrame(scroll, fg_color="transparent")
            other_frame.pack(fill="x", pady=3, padx=30)
            
            label = customtkinter.CTkLabel(
                other_frame,
                text=f"{label_text}: {value_text}",
                font=customtkinter.CTkFont(size=12),
                anchor="w"
            )
            label.pack(fill="x")
        
        # Button frame for Save and Back buttons
        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=10)
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        def save_character():
            try:
                self._save_file(save_data)
                self._popup_show_info("Success", "Character saved successfully!", sound="success")
            except Exception as e:
                logging.error(f"Failed to save character: {e}")
                self._popup_show_info("Error", f"Failed to save: {e}", sound="error")
        
        save_button = self._create_sound_button(
            button_frame,
            "Save",
            save_character,
            width=200,
            height=40
        )
        save_button.grid(row=0, column=0, padx=(0, 10))
        
        back_button = self._create_sound_button(
            button_frame,
            "Back",
            lambda: [self._clear_window(), self._open_character_management()],
            width=200,
            height=40
        )
        back_button.grid(row=0, column=1, padx=(10, 0))
    def _create_new_character(self):
        import uuid
        import json
        stat_clamp = 20
        slot_disable_points = 6
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if table_files:
                with open(table_files[0], 'r') as f:
                    table_data = json.load(f)
                    stat_clamp = table_data.get("additional_settings", {}).get("stat_clamp", 20)
                    slot_disable_points = table_data.get("additional_settings", {}).get("slot_disable_points", 1)
                    logging.info(f"Loaded stat_clamp from table: {stat_clamp}")
                    logging.info(f"Loaded slot_disable_points from table: {slot_disable_points}")
        except Exception as e:
            logging.warning(f"Failed to load table settings, using default clamp: {e}")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_container = customtkinter.CTkFrame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        canvas_bg = customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"][1]
        canvas = customtkinter.CTkCanvas(main_container, bg=canvas_bg, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        frame = customtkinter.CTkFrame(canvas, width=650)
        def center_window(event=None):
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            canvas.create_window(canvas_width/2, canvas_height/2, window=frame, anchor="center")
        canvas.bind("<Configure>", center_window)
        main_container.update_idletasks()
        frame.grid_columnconfigure(0, weight=1)
        title = customtkinter.CTkLabel(frame, text="Create New Character", font=customtkinter.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=(0, 20))
        name_label = customtkinter.CTkLabel(frame, text="Character Name:", font=customtkinter.CTkFont(size=14))
        name_label.grid(row=1, column=0, sticky="w", pady=5)
        name_entry = customtkinter.CTkEntry(frame, placeholder_text="Enter character name")
        name_entry.grid(row=2, column=0, sticky="ew", pady=(0, 15), padx=10)
        stats_frame = customtkinter.CTkFrame(frame)
        stats_frame.grid(row=3, column=0, sticky="ew", pady=10, padx=10)
        stats_frame.grid_columnconfigure((1, 2, 3), weight=1)
        stats_label = customtkinter.CTkLabel(stats_frame, text="Initial Stats (Sum must be ≤ 0)", font=customtkinter.CTkFont(size=14, weight="bold"))
        stats_label.grid(row=0, column=0, columnspan=4, pady=(0, 15))
        stat_names = list(emptysave["stats"].keys())
        stat_sliders = {}
        stat_value_labels = {}
        for i, stat in enumerate(stat_names):
            stat_label = customtkinter.CTkLabel(stats_frame, text=f"{stat}:", font=customtkinter.CTkFont(size=12), width=100)
            stat_label.grid(row=i+1, column=0, sticky="w", padx=(0, 10), pady=8)
            value_label = customtkinter.CTkLabel(stats_frame, text="0", font=customtkinter.CTkFont(size=12, weight="bold"), width=30)
            value_label.grid(row=i+1, column=1, sticky="e", padx=(0, 10), pady=8)
            stat_value_labels[stat] = value_label
            def make_slider_callback(stat_name, value_lbl):
                def on_slider_change(val):
                    value_lbl.configure(text=str(int(float(val))))
                return on_slider_change
            if stat == "Luck":
                stat_min, stat_max = -4, 4
                stat_steps = 8
            else:
                stat_min, stat_max = -20, stat_clamp
                stat_steps = 40 + stat_clamp
            slider = customtkinter.CTkSlider(
                stats_frame,
                from_=stat_min,
                to=stat_max,
                number_of_steps=stat_steps,
                command=make_slider_callback(stat, value_label)
            )
            slider.set(0)
            slider.grid(row=i+1, column=2, sticky="ew", padx=10, pady=8)
            stat_sliders[stat] = slider
            range_label = customtkinter.CTkLabel(stats_frame, text=f"[{stat_min}, +{stat_max}]", font=customtkinter.CTkFont(size=10), text_color="gray")
            range_label.grid(row=i+1, column=3, sticky="w", padx=(10, 0), pady=8)
        
        # Equipment Slots Section
        equipment_frame = customtkinter.CTkFrame(frame)
        equipment_frame.grid(row=4, column=0, sticky="ew", pady=10, padx=10)
        equipment_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        equipment_label = customtkinter.CTkLabel(equipment_frame, text=f"Equipment Slots (Disable for -{slot_disable_points} point{'s' if slot_disable_points != 1 else ''} each)", font=customtkinter.CTkFont(size=14, weight="bold"))
        equipment_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        equipment_slots = list(emptysave["equipment"].keys())
        slot_checkboxes = {}
        
        for i, slot in enumerate(equipment_slots):
            row = (i // 3) + 1
            col = i % 3
            
            checkbox = customtkinter.CTkCheckBox(
                equipment_frame,
                text=slot.title(),
                font=customtkinter.CTkFont(size=11)
            )
            checkbox.select()  # All slots enabled by default
            checkbox.grid(row=row, column=col, sticky="w", padx=10, pady=5)
            slot_checkboxes[slot] = checkbox
        
        sum_frame = customtkinter.CTkFrame(frame)
        sum_frame.grid(row=5, column=0, sticky="ew", pady=15, padx=10)
        sum_frame.grid_columnconfigure(1, weight=1)
        sum_label = customtkinter.CTkLabel(sum_frame, text="Total Points:", font=customtkinter.CTkFont(size=12, weight="bold"))
        sum_label.grid(row=0, column=0, sticky="w", padx=(0, 10))
        sum_value_label = customtkinter.CTkLabel(sum_frame, text="0", font=customtkinter.CTkFont(size=12, weight="bold"))
        sum_value_label.grid(row=0, column=1, sticky="w")
        
        def update_sum(*args):
            stat_total = sum(int(float(stat_sliders[stat].get())) for stat in stat_names)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items() if not checkbox.get())
            bonus_points = disabled_slots * slot_disable_points * -1
            total = stat_total + bonus_points
            
            sum_value_label.configure(text=f"{stat_total} + {bonus_points} = {total}")
            if total > 0:
                sum_value_label.configure(text_color="red")
                create_button.configure(state="disabled")
            else:
                sum_value_label.configure(text_color="white")
                create_button.configure(state="normal")
        
        for stat in stat_names:
            stat_sliders[stat].configure(command=lambda val, s=stat: [
                stat_value_labels[s].configure(text=str(int(float(stat_sliders[s].get())))),
                update_sum()
            ])
        
        # Bind checkboxes to update sum
        for slot in equipment_slots:
            slot_checkboxes[slot].configure(command=update_sum)
        
        button_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=6, column=0, sticky="ew", pady=(20, 0), padx=10)
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        def perform_character_creation():
            char_name = name_entry.get().strip()
            stat_total = sum(int(float(stat_sliders[stat].get())) for stat in stat_names)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items() if not checkbox.get())
            bonus_points = disabled_slots * slot_disable_points * -1
            total = stat_total + bonus_points
            
            try:
                new_save = emptysave.copy()
                new_save["charactername"] = char_name
                for stat in stat_names:
                    new_save["stats"][stat] = int(float(stat_sliders[stat].get()))
                
                # Remove disabled equipment slots
                for slot, checkbox in slot_checkboxes.items():
                    if not checkbox.get():
                        del new_save["equipment"][slot]
                char_uuid = str(uuid.uuid4())
                save_filename = f"{saves_folder}/{char_name}_{char_uuid}.sldsv"
                with open(save_filename, 'w') as f:
                    json.dump(new_save, f, indent=4)
                persistentdata["save_uuids"][char_uuid] = char_name
                persistentdata["last_loaded_save"] = char_uuid
                self._save_persistent_data()
                logging.info(f"Character '{char_name}' created successfully with UUID: {char_uuid}")
                self._popup_show_info("Success", f"Character '{char_name}' created successfully!", sound="success")
                self._clear_window()
                self._open_character_management()
            except Exception as e:
                logging.error(f"Failed to create character: {e}")
                self._popup_show_info("Error", f"Failed to create character: {e}", sound="error")
        
        def create_character():
            char_name = name_entry.get().strip()
            if not char_name:
                self._popup_show_info("Error", "Please enter a character name.", sound="error")
                return
            
            stat_total = sum(int(float(stat_sliders[stat].get())) for stat in stat_names)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items() if not checkbox.get())
            bonus_points = disabled_slots * slot_disable_points * -1
            total = stat_total + bonus_points
            
            # If balance is negative, show warning confirmation
            if total < 0:
                self._popup_confirm(
                    "Negative Balance Warning",
                    f"Your point balance is {total} (negative). This means you have unspent points.\n\nAre you sure you want to continue?",
                    perform_character_creation
                )
            else:
                perform_character_creation()
        
        def go_back():
            self._clear_window()
            self._open_character_management()
        
        create_button = self._create_sound_button(button_frame, "Create Character", create_character, width=200, height=50, font=customtkinter.CTkFont(size=14))
        create_button.grid(row=0, column=0, padx=(0, 10))
        back_button = self._create_sound_button(button_frame, "Cancel", go_back, width=200, height=50, font=customtkinter.CTkFont(size=14))
        back_button.grid(row=0, column=1, padx=(10, 0))
    def _load_existing_character(self):
        import json
        import os
        
        logging.info("Load Existing Character definition called")
        
        # Get all save files
        save_files = []
        try:
            for filename in os.listdir(saves_folder):
                if filename.endswith(".sldsv.sldsv"):
                    continue
                if filename.endswith(".sldsv") and filename not in ["persistent_data.sldsv", "settings.sldsv"]:
                    save_path = os.path.join(saves_folder, filename)
                    try:
                        with open(save_path, 'r') as f:
                            save_data = json.load(f)
                            char_name = save_data.get("charactername", "Unknown")
                            # Extract UUID from filename
                            uuid_part = filename.replace(".sldsv", "").split("_")[-1]
                            save_files.append({
                                "filename": filename,
                                "character_name": char_name,
                                "uuid": uuid_part,
                                "data": save_data
                            })
                    except Exception as e:
                        logging.warning(f"Failed to load save file {filename}: {e}")
        except Exception as e:
            logging.error(f"Failed to read saves folder: {e}")
            self._popup_show_info("Error", f"Failed to read saves folder: {e}", sound="error")
            return
        
        if not save_files:
            self._popup_show_info("No Saves Found", "No character save files found.", sound="error")
            return
        
        # Build UI
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title = customtkinter.CTkLabel(main_frame, text="Load Existing Character", font=customtkinter.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=(0, 20))
        
        # Scrollable frame for character list
        scroll_frame = customtkinter.CTkScrollableFrame(main_frame, width=700, height=400)
        scroll_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        scroll_frame.grid_columnconfigure(0, weight=1)
        
        def load_character(save_info):
            global currentsave
            try:
                currentsave = save_info["filename"].replace(".sldsv", "")
                persistentdata["save_uuids"].setdefault(save_info["uuid"], save_info["character_name"])
                persistentdata["last_loaded_save"] = save_info["uuid"]
                self._save_persistent_data()
                logging.info(f"Loaded character '{save_info['character_name']}' with UUID: {save_info['uuid']}")
                self._popup_show_info("Success", f"Character '{save_info['character_name']}' loaded successfully!", sound="success")
                self._clear_window()
                self._build_main_menu()
            except Exception as e:
                logging.error(f"Failed to load character: {e}")
                self._popup_show_info("Error", f"Failed to load character: {e}", sound="error")
        
        # Display each save file
        for i, save_info in enumerate(save_files):
            char_frame = customtkinter.CTkFrame(scroll_frame)
            char_frame.grid(row=i, column=0, sticky="ew", pady=5, padx=10)
            char_frame.grid_columnconfigure(0, weight=1)
            
            # Character name
            name_label = customtkinter.CTkLabel(
                char_frame,
                text=save_info["character_name"],
                font=customtkinter.CTkFont(size=18, weight="bold"),
                anchor="w"
            )
            name_label.grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))
            
            # Stats display
            stats = save_info["data"].get("stats", {})
            stats_text = " | ".join([f"{stat}: {value:+d}" for stat, value in stats.items()])
            stats_label = customtkinter.CTkLabel(
                char_frame,
                text=stats_text,
                font=customtkinter.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            stats_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 5))
            
            # Equipment slots count
            equipment_count = len(save_info["data"].get("equipment", {}))
            equipment_label = customtkinter.CTkLabel(
                char_frame,
                text=f"Equipment Slots: {equipment_count}",
                font=customtkinter.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            equipment_label.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 10))
            
            # Load button
            load_button = self._create_sound_button(
                char_frame,
                "Load Character",
                lambda s=save_info: load_character(s),
                width=150,
                height=35,
                font=customtkinter.CTkFont(size=13)
            )
            load_button.grid(row=0, column=1, rowspan=3, padx=15, pady=10)
        
        # Back button
        back_button = self._create_sound_button(
            main_frame,
            "Back to Character Management",
            lambda: [self._clear_window(), self._open_character_management()],
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=14)
        )
        back_button.grid(row=2, column=0, pady=(10, 0))
    def _open_inventory_management(self):
        logging.info("Inventory Management definition called")
        
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title = customtkinter.CTkLabel(main_frame, text="Inventory Management", font=customtkinter.CTkFont(size=24, weight="bold"))
        title.pack(pady=(0, 20))
        
        # Container Management button (consolidated)
        container_management_button = self._create_sound_button(
            main_frame,
            "Manage Containers & Transfer Items",
            lambda: [self._clear_window(), self._manage_containers()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        container_management_button.pack(pady=10)
        
        # Player Transfer button
        player_transfer_button = self._create_sound_button(
            main_frame,
            "Transfer to Another Player (Export/Import)",
            lambda: [self._clear_window(), self._transfer_player()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        player_transfer_button.pack(pady=10)
        
        # Back button
        back_button = self._create_sound_button(
            main_frame,
            "Back to Inventory Manager",
            lambda: [self._clear_window(), self._open_inventory_manager_tool()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=10)
    
    def _format_weight(self, weight_kg):
        """Convert weight from kg to display format based on units setting"""
        if appearance_settings["units"] == "imperial":
            weight_lb = weight_kg * 2.20462
            return f"{weight_lb:.2f} lb"
        else:
            return f"{weight_kg:.2f} kg"
    
    def _calculate_encumbrance_status(self, save_data):
        """Calculate total encumbrance and encumbered status (excluding storage)"""
        def compute_item_weight(itm):
            """Weight of an item including contents and subslot items."""
            if not itm or not isinstance(itm, dict):
                return 0.0
            qty = itm.get("quantity", 1)
            weight = itm.get("weight", 0) * qty
            for contained in itm.get("items", []):
                weight += compute_item_weight(contained)
            if "subslots" in itm:
                for ss in itm.get("subslots", []):
                    current = ss.get("current")
                    weight += compute_item_weight(current)
            return weight

        def compute_encumbrance_reduction(itm):
            """Encumbrance reduction contributed by an item and any subslot items."""
            if not itm or not isinstance(itm, dict):
                return 0.0
            reduction = itm.get("encumbrance_reduction", 0.0)
            if "subslots" in itm:
                for ss in itm.get("subslots", []):
                    reduction += compute_encumbrance_reduction(ss.get("current"))
            return reduction

        total_weight = 0.0
        total_reduction = 0.0
        
        # NOTE: Storage items do NOT count towards encumbrance
        
        # Hands weight
        for item in save_data.get("hands", {}).get("items", []):
            total_weight += compute_item_weight(item)
            total_reduction += compute_encumbrance_reduction(item)
        
        # Equipment weight
        for slot, item in save_data.get("equipment", {}).items():
            if item and isinstance(item, dict):
                total_weight += compute_item_weight(item)
                total_reduction += compute_encumbrance_reduction(item)
        
        # Encumbrance is total weight after reduction
        encumbrance = max(total_weight - total_reduction, 0.0)

        threshold = save_data.get("encumbered_threshold", 50)
        
        # Calculate encumbrance level (how much over threshold)
        encumbrance_level = 0
        if encumbrance > threshold:
            overflow_percent = (encumbrance - threshold) / threshold
            encumbrance_level = int(overflow_percent * 10)  # Each 10% = 1 level
        
        return {
            "total_weight": total_weight,
            "total_reduction": total_reduction,
            "encumbrance": encumbrance,
            "threshold": threshold,
            "encumbrance_level": encumbrance_level,
            "is_encumbered": encumbrance_level > 0
        }
    
    def _transfer_player(self):
        import json
        import base64
        import pickle
        from datetime import datetime
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        self._clear_window()
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title = customtkinter.CTkLabel(main_frame, text="Player Transfer", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.pack(pady=(0, 20))
        
        # Export section
        export_frame = customtkinter.CTkFrame(main_frame)
        export_frame.pack(fill="x", pady=10, padx=10)
        
        export_label = customtkinter.CTkLabel(export_frame, text="Export Items/Money", font=customtkinter.CTkFont(size=16, weight="bold"))
        export_label.pack(pady=10)
        
        # Money input
        money_frame = customtkinter.CTkFrame(export_frame, fg_color="transparent")
        money_frame.pack(pady=5)
        
        money_label = customtkinter.CTkLabel(money_frame, text="Money Amount:")
        money_label.pack(side="left", padx=5)
        
        money_entry = customtkinter.CTkEntry(money_frame, placeholder_text="0", width=150)
        money_entry.pack(side="left", padx=5)
        
        # Items selection
        items_label = customtkinter.CTkLabel(export_frame, text="Select items to export from storage:", font=customtkinter.CTkFont(size=13))
        items_label.pack(pady=(10, 5))
        
        items_scroll = customtkinter.CTkScrollableFrame(export_frame, width=700, height=200)
        items_scroll.pack(pady=5, padx=10)
        
        selected_items = []  # Will store indices of selected items
        
        def refresh_export_items():
            for widget in items_scroll.winfo_children():
                widget.destroy()
            selected_items.clear()
            
            save_path = os.path.join(saves_folder, currentsave + ".sldsv")
            try:
                with open(save_path, 'r') as f:
                    save_data = json.load(f)
                
                storage_items = save_data.get("storage", [])
                
                if not storage_items:
                    empty_label = customtkinter.CTkLabel(items_scroll, text="No items in storage", text_color="gray")
                    empty_label.pack(pady=20)
                    return
                
                for idx, item in enumerate(storage_items):
                    item_frame = customtkinter.CTkFrame(items_scroll)
                    item_frame.pack(fill="x", pady=2, padx=5)
                    
                    var = customtkinter.BooleanVar(value=False)
                    
                    def on_check(index=idx, var_ref=var):
                        if var_ref.get():
                            if index not in selected_items:
                                selected_items.append(index)
                        else:
                            if index in selected_items:
                                selected_items.remove(index)
                    
                    checkbox = customtkinter.CTkCheckBox(
                        item_frame,
                        text=f"{item.get('name', 'Unknown')} x{item.get('quantity', 1)}",
                        variable=var,
                        command=on_check
                    )
                    checkbox.pack(side="left", padx=10, pady=5)
            except Exception as e:
                logging.error(f"Failed to load items: {e}")
        
        refresh_export_items()
        
        def create_export():
            try:
                save_path = os.path.join(saves_folder, currentsave + ".sldsv")
                with open(save_path, 'r') as f:
                    save_data = json.load(f)
                
                money_amount = int(money_entry.get() or 0)
                
                if money_amount > save_data.get("money", 0):
                    self._popup_show_info("Error", "Not enough money!", sound="error")
                    return
                
                # Get selected items from storage
                storage_items = save_data.get("storage", [])
                items_to_export = [storage_items[i] for i in sorted(selected_items) if i < len(storage_items)]
                
                # Create transfer package
                transfer_data = {
                    "money": money_amount,
                    "items": items_to_export,
                    "timestamp": datetime.now().isoformat(),
                    "from_character": save_data.get("charactername", "Unknown")
                }
                
                # Deduct money
                save_data["money"] = save_data.get("money", 0) - money_amount
                
                # Remove exported items from storage (in reverse order to maintain indices)
                for idx in sorted(selected_items, reverse=True):
                    if idx < len(storage_items):
                        storage_items.pop(idx)
                
                save_data["storage"] = storage_items
                
                # Save character
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
                # Create transfer file
                pickled_data = pickle.dumps(transfer_data)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                
                transfer_filename = f"transfers/transfer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sldtrf"
                with open(transfer_filename, 'w') as f:
                    f.write(encoded_data)
                
                self._popup_show_info("Success", f"Exported {len(items_to_export)} items and ${money_amount}!", sound="success")
                logging.info(f"Created transfer file: {transfer_filename}")
                refresh_export_items()
            except Exception as e:
                logging.error(f"Export failed: {e}")
                self._popup_show_info("Error", f"Export failed: {e}", sound="error")
        
        export_button = self._create_sound_button(export_frame, "Create Transfer File", create_export, width=200, height=40)
        export_button.pack(pady=10)
        
        # Import section
        import_frame = customtkinter.CTkFrame(main_frame)
        import_frame.pack(fill="x", pady=10, padx=10)
        
        import_label = customtkinter.CTkLabel(import_frame, text="Import Transfer File", font=customtkinter.CTkFont(size=16, weight="bold"))
        import_label.pack(pady=10)
        
        def list_transfers():
            try:
                transfer_files = glob.glob("transfers/*.sldtrf")
                if not transfer_files:
                    self._popup_show_info("Info", "No transfer files found.", sound="popup")
                    return
                
                # Create selection window
                select_window = customtkinter.CTkToplevel(self.root)
                select_window.title("Select Transfer File")
                select_window.geometry("500x400")
                select_window.transient(self.root)
                
                scroll_frame = customtkinter.CTkScrollableFrame(select_window, width=450, height=300)
                scroll_frame.pack(pady=10, padx=10, fill="both", expand=True)
                
                def import_transfer(filepath):
                    try:
                        with open(filepath, 'r') as f:
                            encoded_data = f.read()
                        
                        pickled_data = base64.b85decode(encoded_data.encode('utf-8'))
                        transfer_data = pickle.loads(pickled_data)
                        
                        save_path = os.path.join(saves_folder, currentsave + ".sldsv")
                        with open(save_path, 'r') as f:
                            save_data = json.load(f)
                        
                        # Add money
                        save_data["money"] = save_data.get("money", 0) + transfer_data.get("money", 0)
                        
                        # Add items to storage
                        for item in transfer_data.get("items", []):
                            save_data["storage"].append(item)
                        
                        # Save character
                        with open(save_path, 'w') as f:
                            json.dump(save_data, f, indent=4)
                        
                        # Delete transfer file
                        os.remove(filepath)
                        
                        select_window.destroy()
                        self._popup_show_info("Success", f"Received ${transfer_data.get('money', 0)} and {len(transfer_data.get('items', []))} items!", sound="success")
                    except Exception as e:
                        logging.error(f"Import failed: {e}")
                        self._popup_show_info("Error", f"Import failed: {e}", sound="error")
                
                for i, filepath in enumerate(transfer_files):
                    try:
                        with open(filepath, 'r') as f:
                            encoded_data = f.read()
                        pickled_data = base64.b85decode(encoded_data.encode('utf-8'))
                        transfer_data = pickle.loads(pickled_data)
                        
                        file_frame = customtkinter.CTkFrame(scroll_frame)
                        file_frame.pack(fill="x", pady=5, padx=5)
                        
                        info_label = customtkinter.CTkLabel(
                            file_frame,
                            text=f"From: {transfer_data.get('from_character', 'Unknown')}\nMoney: ${transfer_data.get('money', 0)} | Items: {len(transfer_data.get('items', []))}",
                            anchor="w"
                        )
                        info_label.pack(side="left", padx=10, pady=5)
                        
                        import_btn = self._create_sound_button(
                            file_frame,
                            "Import",
                            lambda f=filepath: import_transfer(f),
                            width=100,
                            height=35
                        )
                        import_btn.pack(side="right", padx=10, pady=5)
                    except Exception as e:
                        logging.warning(f"Failed to read transfer file {filepath}: {e}")
                
                select_window.update_idletasks()
                select_window.deiconify()
                select_window.grab_set()
            except Exception as e:
                logging.error(f"Failed to list transfers: {e}")
                self._popup_show_info("Error", f"Failed to list transfers: {e}", sound="error")
        
        import_button = self._create_sound_button(import_frame, "Browse Transfer Files", list_transfers, width=200, height=40)
        import_button.pack(pady=10)
        
        # Back button
        back_button = self._create_sound_button(main_frame, "Back", lambda: [self._clear_window(), self._open_inventory_management()], width=200, height=40)
        back_button.pack(pady=20)
    
    def _manage_containers(self):
        logging.info("Container Management definition called")
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        # Clear window first before any operations
        self._clear_window()
        
        # Load current save data using _load_file
        save_filename = currentsave + ".sldsv"
        save_data = self._load_file(save_filename)
        
        if save_data is None:
            logging.error(f"Failed to load save file {save_filename}")
            self._popup_show_info("Error", f"Failed to load character data", sound="error")
            return
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title = customtkinter.CTkLabel(main_frame, text="Manage Containers & Transfer Items", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, pady=(0, 10))
        
        # Create tabview
        tabview = customtkinter.CTkTabview(main_frame, width=1000, height=600)
        tabview.grid(row=1, column=0, sticky="nsew", pady=10)
        
        # Add tabs
        tabview.add("View Inventory")
        tabview.add("Transfer Items")
        # CTkTabview doesn't support tkinter-style bind; use the command callback instead
        tabview.configure(command=lambda value=None: refresh_enc_info())
        
        # Build list of all containers
        def get_containers():
            containers = []
            equipment = save_data.get("equipment", {})
            
            containers.append({"name": "Storage", "location": "storage"})
            containers.append({"name": "Hands", "location": "hands"})
            
            # Check equipped items for containers
            for slot, item in equipment.items():
                if item and isinstance(item, dict):
                    if "capacity" in item and "items" in item:
                        containers.append({
                            "name": f"{item.get('name', 'Container')} ({slot})",
                            "location": f"equipment.{slot}"
                        })
                    
                    # Check subslots for containers
                    if "subslots" in item:
                        for subslot_idx, subslot_data in enumerate(item["subslots"]):
                            subslot_item = subslot_data.get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                if "capacity" in subslot_item and "items" in subslot_item:
                                    subslot_name = subslot_data.get("name", f"Subslot {subslot_idx}")
                                    containers.append({
                                        "name": f"{subslot_item.get('name', 'Container')} ({slot} → {subslot_name})",
                                        "location": f"equipment.{slot}.subslot.{subslot_idx}"
                                    })
            
            return containers
        
        containers = get_containers()

        # Helper functions for getting/setting container items
        def get_container_items(location):
            """Get items from a container location"""
            if location == "storage":
                return save_data.get("storage", [])
            elif location == "hands":
                return save_data["hands"].get("items", [])
            elif location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                item = save_data["equipment"].get(slot)
                if item and isinstance(item, dict):
                    # Check if it's a subslot reference
                    if len(parts) > 2 and parts[2] == "subslot":
                        subslot_idx = int(parts[3])
                        if "subslots" in item and subslot_idx < len(item["subslots"]):
                            subslot_item = item["subslots"][subslot_idx].get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                return subslot_item.get("items", [])
                    else:
                        return item.get("items", [])
            return []
        
        def set_container_items(location, items):
            """Set items for a container location"""
            if location == "storage":
                save_data["storage"] = items
            elif location == "hands":
                save_data["hands"]["items"] = items
            elif location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                if slot in save_data["equipment"] and save_data["equipment"][slot]:
                    # Check if it's a subslot reference
                    if len(parts) > 2 and parts[2] == "subslot":
                        subslot_idx = int(parts[3])
                        item = save_data["equipment"][slot]
                        if "subslots" in item and subslot_idx < len(item["subslots"]):
                            subslot_item = item["subslots"][subslot_idx].get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                subslot_item["items"] = items
                    else:
                        save_data["equipment"][slot]["items"] = items

        def get_container_weight(location):
            """Total weight of all items in the container (kg)."""
            items = get_container_items(location)
            return sum(i.get("weight", 0) * i.get("quantity", 1) for i in items)

        def get_container_capacity(location):
            """Return capacity (kg) for the given container location, or None if unlimited."""
            if location == "hands":
                return save_data.get("hands", {}).get("capacity")
            if location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                equip = save_data.get("equipment", {}).get(slot)
                if equip:
                    if len(parts) > 2 and parts[2] == "subslot":
                        subslot_idx = int(parts[3])
                        if "subslots" in equip and subslot_idx < len(equip["subslots"]):
                            subslot_item = equip["subslots"][subslot_idx].get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                return subslot_item.get("capacity")
                            return None
                    return equip.get("capacity")
            # storage or unknown -> unlimited
            return None

        def rebuild_container_labels():
            """Build display labels with weight usage and capacity for view dropdown."""
            labels = []
            for c in containers:
                # Compute weight usage
                total_weight = get_container_weight(c["location"])
                # Determine capacity text
                if c["location"] == "hands":
                    capacity = save_data.get("hands", {}).get("capacity", None)
                elif c["location"].startswith("equipment."):
                    parts = c["location"].split(".")
                    slot = parts[1]
                    equip = save_data.get("equipment", {}).get(slot)
                    if equip:
                        # Check if it's a subslot reference
                        if len(parts) > 2 and parts[2] == "subslot":
                            subslot_idx = int(parts[3])
                            if "subslots" in equip and subslot_idx < len(equip["subslots"]):
                                subslot_item = equip["subslots"][subslot_idx].get("current")
                                capacity = subslot_item.get("capacity") if subslot_item else None
                            else:
                                capacity = None
                        else:
                            capacity = equip.get("capacity")
                    else:
                        capacity = None
                else:
                    capacity = None  # storage or unknown -> show infinity
                capacity_text = self._format_weight(capacity) if capacity is not None else "∞"
                c["label"] = f"{c['name']} ({self._format_weight(total_weight)}/{capacity_text})"
                labels.append(c["label"])
            return labels

        labels = rebuild_container_labels()
        
        # === VIEW INVENTORY TAB ===
        view_tab = tabview.tab("View Inventory")
        view_tab.grid_rowconfigure(1, weight=1)
        view_tab.grid_columnconfigure(0, weight=1)
        
        # Encumbrance info frame
        enc_info_frame = customtkinter.CTkFrame(view_tab, fg_color=("gray90", "gray20"))
        enc_info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        enc_info_frame.grid_columnconfigure(0, weight=1)
        
        enc_info_label = customtkinter.CTkLabel(enc_info_frame, font=customtkinter.CTkFont(size=12), anchor="w")
        enc_info_label.grid(row=0, column=0, sticky="ew", padx=15, pady=10)

        def refresh_enc_info():
            encumbrance_info = self._calculate_encumbrance_status(save_data)
            enc_info_label.configure(
                text=(
                    f"Total Weight: {self._format_weight(encumbrance_info['total_weight'])} | "
                    f"Encumbrance: {self._format_weight(encumbrance_info['encumbrance'])} / {self._format_weight(encumbrance_info['threshold'])} | "
                    f"Encumbrance level: {encumbrance_info['encumbrance_level']} | "
                    f"Status: {'ENCUMBERED' if encumbrance_info['is_encumbered'] else 'OK'}"
                )
            )

        refresh_enc_info()
        
        view_frame = customtkinter.CTkFrame(view_tab)
        view_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        view_frame.grid_rowconfigure(1, weight=1)
        view_frame.grid_columnconfigure(0, weight=1)
        
        container_selector = customtkinter.CTkOptionMenu(
            view_frame,
            values=labels,
            width=300,
            font=customtkinter.CTkFont(size=14)
        )
        container_selector.grid(row=0, column=0, pady=10)
        container_selector.set(labels[0] if labels else "")
        
        view_scroll = customtkinter.CTkScrollableFrame(view_frame, width=900, height=450)
        view_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        def refresh_view():
            # Refresh labels to keep counts/capacity current
            current_label = container_selector.get()
            new_labels = rebuild_container_labels()
            container_selector.configure(values=new_labels)
            if current_label in new_labels:
                container_selector.set(current_label)
            elif new_labels:
                container_selector.set(new_labels[0])
            refresh_enc_info()
            for widget in view_scroll.winfo_children():
                widget.destroy()
            
            selected_label = container_selector.get()
            selected_container = next((c for c in containers if c.get("label") == selected_label), None)
            
            if not selected_container:
                return
            
            location = selected_container["location"]
            items = get_container_items(location)
            
            if not items:
                empty_label = customtkinter.CTkLabel(view_scroll, text="Container is empty", font=customtkinter.CTkFont(size=14), text_color="gray")
                empty_label.pack(pady=30)
                return
            
            def show_item_details(item_data):
                detail_window = customtkinter.CTkToplevel(self.root)
                detail_window.title("Item Details")
                detail_window.geometry("500x600")
                detail_window.transient(self.root)
                
                scroll = customtkinter.CTkScrollableFrame(detail_window, width=450, height=550)
                scroll.pack(pady=10, padx=10, fill="both", expand=True)
                
                title = customtkinter.CTkLabel(scroll, text=item_data.get("name", "Unknown"), font=customtkinter.CTkFont(size=18, weight="bold"))
                title.pack(pady=(10, 20))
                
                # Display all item properties
                for key, value in item_data.items():
                    if key == "name":
                        continue
                    
                    prop_frame = customtkinter.CTkFrame(scroll, fg_color="transparent")
                    prop_frame.pack(fill="x", pady=2, padx=10)
                    
                    key_label = customtkinter.CTkLabel(
                        prop_frame,
                        text=f"{key.replace('_', ' ').title()}:",
                        font=customtkinter.CTkFont(size=12, weight="bold"),
                        anchor="w",
                        width=150
                    )
                    key_label.pack(side="left", padx=5)
                    
                    # Format value based on type
                    if isinstance(value, (list, dict)):
                        value_text = json.dumps(value, indent=2)
                    else:
                        value_text = str(value)
                    
                    value_label = customtkinter.CTkLabel(
                        prop_frame,
                        text=value_text,
                        font=customtkinter.CTkFont(size=11),
                        anchor="w",
                        wraplength=250
                    )
                    value_label.pack(side="left", padx=5, fill="x", expand=True)
                
                close_button = self._create_sound_button(scroll, "Close", detail_window.destroy, width=120, height=35)
                close_button.pack(pady=20)
                
                detail_window.update_idletasks()
                detail_window.deiconify()
                detail_window.grab_set()
            
            for item in items:
                item_frame = customtkinter.CTkFrame(view_scroll)
                item_frame.pack(fill="x", pady=5, padx=10)
                item_frame.grid_columnconfigure(0, weight=1)
                
                item_name = item.get("name", "Unknown")
                item_qty = item.get("quantity", 1)
                item_weight = item.get("weight", 0) * item_qty
                item_value = item.get("value", 0)
                
                name_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name} x{item_qty}",
                    font=customtkinter.CTkFont(size=14, weight="bold"),
                    anchor="w"
                )
                name_label.grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))
                
                info_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"Weight: {self._format_weight(item_weight)} | Value: ${item_value}",
                    font=customtkinter.CTkFont(size=11),
                    text_color="gray",
                    anchor="w"
                )
                info_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))
                
                details_button = self._create_sound_button(
                    item_frame,
                    "View Details",
                    lambda it=item: show_item_details(it),
                    width=120,
                    height=35,
                    font=customtkinter.CTkFont(size=12)
                )
                details_button.grid(row=0, column=1, rowspan=2, padx=15, pady=10)
        
        container_selector.configure(command=lambda _: refresh_view())
        refresh_view()
        
        # === TRANSFER ITEMS TAB ===
        transfer_tab = tabview.tab("Transfer Items")
        transfer_tab.grid_rowconfigure(1, weight=1)
        transfer_tab.grid_columnconfigure((0, 1), weight=1)
        
        info_label = customtkinter.CTkLabel(transfer_tab, text="Select source and destination containers to move items:", font=customtkinter.CTkFont(size=13))
        info_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        container_frame = customtkinter.CTkFrame(transfer_tab)
        container_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=10)
        container_frame.grid_rowconfigure(0, weight=1)
        container_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Source container
        source_frame = customtkinter.CTkFrame(container_frame)
        source_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        source_frame.grid_rowconfigure(2, weight=1)
        source_frame.grid_columnconfigure(0, weight=1)
        
        source_label = customtkinter.CTkLabel(source_frame, text="Source Container", font=customtkinter.CTkFont(size=16, weight="bold"))
        source_label.grid(row=0, column=0, pady=10)
        
        source_selector = customtkinter.CTkOptionMenu(source_frame, values=[c["name"] for c in containers], width=300)
        source_selector.grid(row=1, column=0, pady=5)
        source_selector.set(containers[1]["name"] if len(containers) > 1 else containers[0]["name"])  # Default to Hands
        
        source_scroll = customtkinter.CTkScrollableFrame(source_frame, width=350, height=400)
        source_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        # Destination container
        dest_frame = customtkinter.CTkFrame(container_frame)
        dest_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        dest_frame.grid_rowconfigure(2, weight=1)
        dest_frame.grid_columnconfigure(0, weight=1)
        
        dest_label = customtkinter.CTkLabel(dest_frame, text="Destination Container", font=customtkinter.CTkFont(size=16, weight="bold"))
        dest_label.grid(row=0, column=0, pady=10)
        
        dest_selector = customtkinter.CTkOptionMenu(dest_frame, values=[c["name"] for c in containers], width=300)
        dest_selector.grid(row=1, column=0, pady=5)
        dest_selector.set(containers[0]["name"])  # Default to Storage
        
        dest_scroll = customtkinter.CTkScrollableFrame(dest_frame, width=350, height=400)
        dest_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        def refresh_containers():
            # Clear displays
            for widget in source_scroll.winfo_children():
                widget.destroy()
            for widget in dest_scroll.winfo_children():
                widget.destroy()
            
            # Get selected containers
            source_name = source_selector.get()
            dest_name = dest_selector.get()

            # If source and destination are the same, swap them; if still the same, pick the first different container
            if source_name == dest_name:
                source_selector.set(dest_name)
                dest_selector.set(source_name)
                source_name = source_selector.get()
                dest_name = dest_selector.get()
                if source_name == dest_name:
                    # find first different container for dest
                    for c in containers:
                        if c["name"] != source_name:
                            dest_selector.set(c["name"])
                            dest_name = c["name"]
                            break
            
            source_container = next((c for c in containers if c["name"] == source_name), None)
            dest_container = next((c for c in containers if c["name"] == dest_name), None)
            
            if not source_container or not dest_container:
                return
            
            source_location = source_container["location"]
            dest_location = dest_container["location"]
            source_items = get_container_items(source_location)
            dest_items = get_container_items(dest_location)
            
            # Display source items
            for i, item in enumerate(source_items):
                item_frame = customtkinter.CTkFrame(source_scroll)
                item_frame.pack(fill="x", pady=2)
                
                item_name = item.get("name", "Unknown")
                item_weight = item.get("weight", 0) * item.get("quantity", 1)
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name} x{item.get('quantity', 1)} ({self._format_weight(item_weight)})",
                    anchor="w"
                )
                item_label.pack(side="left", padx=10, pady=5)
                
                move_button = self._create_sound_button(
                    item_frame,
                    "Move →",
                    lambda idx=i, src_loc=source_location, dst_loc=dest_location: move_item(idx, src_loc, dst_loc),
                    width=80,
                    height=30
                )
                move_button.pack(side="right", padx=10, pady=5)
            
            if not source_items:
                empty_label = customtkinter.CTkLabel(source_scroll, text="Container is empty", text_color="gray")
                empty_label.pack(pady=20)
            
            # Display destination items
            for item in dest_items:
                item_frame = customtkinter.CTkFrame(dest_scroll)
                item_frame.pack(fill="x", pady=2)
                
                item_name = item.get("name", "Unknown")
                item_weight = item.get("weight", 0) * item.get("quantity", 1)
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name} x{item.get('quantity', 1)} ({self._format_weight(item_weight)})",
                    anchor="w"
                )
                item_label.pack(side="left", padx=10, pady=5)
            
            if not dest_items:
                empty_label = customtkinter.CTkLabel(dest_scroll, text="Container is empty", text_color="gray")
                empty_label.pack(pady=20)
        
        def move_item(item_idx, source_location, dest_location):
            try:
                source_items = get_container_items(source_location)
                dest_items = get_container_items(dest_location)
                
                if item_idx >= len(source_items):
                    return
                
                item = source_items[item_idx]
                item_weight = item.get("weight", 0) * item.get("quantity", 1)
                
                # Check capacity of destination (supports subslot containers)
                dest_capacity = get_container_capacity(dest_location)
                if dest_capacity is not None:
                    current_dest_weight = sum(i.get("weight", 0) * i.get("quantity", 1) for i in dest_items)
                    if current_dest_weight + item_weight > dest_capacity:
                        self._popup_show_info("Error", "Not enough capacity in destination!", sound="error")
                        return
                
                # Move item
                source_items.pop(item_idx)
                item = add_subslots_to_item(item)
                dest_items.append(item)
                
                set_container_items(source_location, source_items)
                set_container_items(dest_location, dest_items)
                
                # Update global encumbrance (total weight in kg)
                encumbrance_info = self._calculate_encumbrance_status(save_data)
                save_data["encumbrance"] = encumbrance_info["total_weight"]
                
                # Save to file using _save_file
                self._save_file(save_data)
                
                refresh_containers()
                refresh_enc_info()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Move failed: {e}")
                self._popup_show_info("Error", f"Move failed: {e}", sound="error")
        
        source_selector.configure(command=lambda _: refresh_containers())
        dest_selector.configure(command=lambda _: refresh_containers())
        
        refresh_containers()
        
        # Back button (outside tabview)
        back_button = self._create_sound_button(
            main_frame,
            "Back",
            lambda: [self._clear_window(), self._open_inventory_management()],
            width=200,
            height=40
        )
        back_button.grid(row=2, column=0, pady=10)
    
    def _open_item_equipping(self):

        logging.info("Item Equipping definition called")
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        # Clear window first before any operations
        self._clear_window()
        
        # Load current save data using _load_file
        save_filename = currentsave + ".sldsv"
        save_data = self._load_file(save_filename)
        
        if save_data is None:
            logging.error(f"Failed to load save file {save_filename}")
            self._popup_show_info("Error", f"Failed to load character data", sound="error")
            return
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title = customtkinter.CTkLabel(main_frame, text="Item Equipping", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.pack(pady=(0, 20))
        
        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.pack(fill="both", expand=True)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Equipment slots column
        slots_frame = customtkinter.CTkFrame(content_frame)
        slots_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        slots_frame.grid_rowconfigure(1, weight=1)
        
        slots_label = customtkinter.CTkLabel(slots_frame, text="Equipment Slots", font=customtkinter.CTkFont(size=16, weight="bold"))
        slots_label.grid(row=0, column=0, pady=10)
        
        slots_scroll = customtkinter.CTkScrollableFrame(slots_frame, width=350, height=500)
        slots_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Available items column
        items_frame = customtkinter.CTkFrame(content_frame)
        items_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        items_frame.grid_rowconfigure(1, weight=1)
        
        items_label = customtkinter.CTkLabel(items_frame, text="Available Items (Storage & Hands)", font=customtkinter.CTkFont(size=16, weight="bold"))
        items_label.grid(row=0, column=0, pady=10)
        
        items_scroll = customtkinter.CTkScrollableFrame(items_frame, width=350, height=500)
        items_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        def refresh_display():
            # Clear displays
            for widget in slots_scroll.winfo_children():
                widget.destroy()
            for widget in items_scroll.winfo_children():
                widget.destroy()
            
            # Display equipment slots
            equipment = save_data.get("equipment", {})
            for slot, item in equipment.items():
                slot_frame = customtkinter.CTkFrame(slots_scroll)
                slot_frame.pack(fill="x", pady=5, padx=5)
                
                slot_label = customtkinter.CTkLabel(
                    slot_frame,
                    text=f"{slot.title()}:",
                    font=customtkinter.CTkFont(size=12, weight="bold"),
                    anchor="w"
                )
                slot_label.pack(side="top", anchor="w", padx=10, pady=(5, 0))
                
                if item:
                    item_name = item.get("name", "Unknown") if isinstance(item, dict) else str(item)
                    item_label = customtkinter.CTkLabel(
                        slot_frame,
                        text=f"  {item_name}",
                        anchor="w",
                        text_color="lightblue"
                    )
                    item_label.pack(side="top", anchor="w", padx=10)
                    
                    unequip_button = self._create_sound_button(
                        slot_frame,
                        "Unequip",
                        lambda s=slot: unequip_item(s),
                        width=80,
                        height=30
                    )
                    unequip_button.pack(side="right", padx=10, pady=5)
                    
                    # Display subslots provided by this item
                    if isinstance(item, dict) and "subslots" in item:
                        for subslot_data in item["subslots"]:
                            subslot_name = subslot_data.get("name", "Unknown Subslot")
                            subslot_type = subslot_data.get("slot", "unknown")
                            current_item = subslot_data.get("current")
                            
                            subslot_frame = customtkinter.CTkFrame(slots_scroll)
                            subslot_frame.pack(fill="x", pady=2, padx=5)
                            
                            subslot_label = customtkinter.CTkLabel(
                                subslot_frame,
                                text=f"  ↳ {subslot_name}:",
                                font=customtkinter.CTkFont(size=11),
                                anchor="w",
                                text_color="#FFA500"
                            )
                            subslot_label.pack(side="top", anchor="w", padx=20, pady=(5, 0))
                            
                            if current_item:
                                subitem_name = current_item.get("name", "Unknown") if isinstance(current_item, dict) else str(current_item)
                                
                                # Check if it's a container
                                is_container = isinstance(current_item, dict) and current_item.get("container", False)
                                if is_container:
                                    total_weight = sum(i.get("weight", 0) * i.get("quantity", 1) for i in current_item.get("items", []))
                                    capacity = current_item.get("capacity", 0)
                                    subitem_text = f"    {subitem_name} [{self._format_weight(total_weight)}/{self._format_weight(capacity)}]"
                                else:
                                    subitem_text = f"    {subitem_name}"
                                
                                subitem_label = customtkinter.CTkLabel(
                                    subslot_frame,
                                    text=subitem_text,
                                    anchor="w",
                                    text_color="lightgreen"
                                )
                                subitem_label.pack(side="top", anchor="w", padx=20)
                                
                                button_container = customtkinter.CTkFrame(subslot_frame, fg_color="transparent")
                                button_container.pack(side="right", padx=10, pady=5)
                                
                                unequip_sub_button = self._create_sound_button(
                                    button_container,
                                    "Unequip",
                                    lambda s=slot, ss=subslot_data: unequip_from_subslot(s, ss),
                                    width=80,
                                    height=25
                                )
                                unequip_sub_button.pack(side="left", padx=2)
                                
                                if is_container:
                                    view_button = self._create_sound_button(
                                        button_container,
                                        "View",
                                        lambda ci=current_item: view_container_contents(ci),
                                        width=60,
                                        height=25
                                    )
                                    view_button.pack(side="left", padx=2)
                            else:
                                empty_sub_label = customtkinter.CTkLabel(
                                    subslot_frame,
                                    text=f"    (empty - accepts: {subslot_type})",
                                    anchor="w",
                                    text_color="gray",
                                    font=customtkinter.CTkFont(size=10)
                                )
                                empty_sub_label.pack(side="top", anchor="w", padx=20, pady=(0, 5))
                else:
                    empty_label = customtkinter.CTkLabel(
                        slot_frame,
                        text="  (empty)",
                        anchor="w",
                        text_color="gray"
                    )
                    empty_label.pack(side="top", anchor="w", padx=10, pady=(0, 5))
            
            # Display available items from storage and hands
            all_items = []
            
            # Add storage items (equippable items and weapons)
            for i, item in enumerate(save_data.get("storage", [])):
                if isinstance(item, dict):
                    is_equippable = item.get("equippable", False)
                    is_firearm = item.get("firearm", False)
                    is_melee = item.get("melee", False)
                    if is_equippable or is_firearm or is_melee:
                        all_items.append(("storage", i, item))
            
            # Add hands items (equippable items and weapons)
            for i, item in enumerate(save_data["hands"].get("items", [])):
                if isinstance(item, dict):
                    is_equippable = item.get("equippable", False)
                    is_firearm = item.get("firearm", False)
                    is_melee = item.get("melee", False)
                    if is_equippable or is_firearm or is_melee:
                        all_items.append(("hands", i, item))
            
            for location, idx, item in all_items:
                item_frame = customtkinter.CTkFrame(items_scroll)
                item_frame.pack(fill="x", pady=2, padx=5)
                
                item_name = item.get("name", "Unknown")
                
                # Determine available slots for this item
                if item.get("equippable"):
                    slots = item.get("slot", [])
                    if not isinstance(slots, list):
                        slots = [slots]
                    slots_text = f"Slots: {', '.join(str(s) for s in slots)}"
                elif item.get("firearm") or item.get("melee"):
                    # Weapons can go to holster/sling subslots or waistband (for pistols)
                    if item.get("firearm"):
                        weapon_type = item.get("subtype", "unknown")
                    else:  # melee
                        weapon_type = item.get("type", "unknown")
                    
                    if weapon_type == "pistol":
                        slots_text = "Slots: holster/sling subslots or waistband"
                    else:
                        slots_text = f"Slots: holster/sling subslots (type: {weapon_type})"
                else:
                    slots_text = "Slots: unknown"
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name}\n  {slots_text}",
                    anchor="w",
                    font=customtkinter.CTkFont(size=11)
                )
                item_label.pack(side="left", padx=10, pady=5)
                
                equip_button = self._create_sound_button(
                    item_frame,
                    "Equip",
                    lambda loc=location, i=idx, itm=item: equip_item(loc, i, itm),
                    width=80,
                    height=30
                )
                equip_button.pack(side="right", padx=10, pady=5)
            
            if not all_items:
                empty_label = customtkinter.CTkLabel(items_scroll, text="No equippable items available", text_color="gray")
                empty_label.pack(pady=20)
        
        def equip_item(location, item_idx, item):
            try:
                equipment = save_data.get("equipment", {})
                # Build list of all available target slots/subslots
                choices = []

                def add_choice(label, slot=None, parent_slot=None, subslot=None):
                    choices.append({"label": label, "slot": slot, "parent_slot": parent_slot, "subslot": subslot})

                # Check if this is a weapon (firearm or melee)
                is_weapon = item.get("firearm", False) or item.get("melee", False)

                if is_weapon:
                    weapon_subtype = item.get("subtype", "unknown")
                    weapon_melee_type = item.get("type") if item.get("melee") else None

                    # Waistband for pistols
                    if weapon_subtype == "pistol" and "waistband" in equipment and equipment["waistband"] is None:
                        add_choice("Waistband", slot="waistband")

                    # Holster/sling weapon subslots
                    for parent_slot, equipped_item in equipment.items():
                        if isinstance(equipped_item, dict) and equipped_item.get("holster_sling", False):
                            compatible_types = equipped_item.get("weapon_types", [])
                            if weapon_subtype in compatible_types or weapon_melee_type in compatible_types:
                                for subslot_data in equipped_item.get("subslots", []):
                                    if subslot_data.get("slot") != "weapon_slot" or subslot_data.get("current") is not None:
                                        continue
                                    conflicts = subslot_data.get("conflicts_with", {})
                                    if conflicts:
                                        conflict_type = conflicts.get("type")
                                        conflict_slot = conflicts.get("slot")
                                        if conflict_type == "main" and conflict_slot in equipment and equipment[conflict_slot] is not None:
                                            continue
                                    label = f"{parent_slot.title()} - {subslot_data.get('name', 'Weapon Slot')}"
                                    add_choice(label, parent_slot=parent_slot, subslot=subslot_data)

                    if not choices:
                        if weapon_subtype == "pistol":
                            self._popup_show_info("Error", "No available holster/sling or waistband slot for this pistol.", sound="error")
                        else:
                            self._popup_show_info("Error", f"No available holster/sling slot for this weapon (type: {weapon_subtype or weapon_melee_type}).", sound="error")
                        return

                else:
                    # Regular equippable item logic
                    valid_slots = item.get("slot", [])
                    if not isinstance(valid_slots, list):
                        valid_slots = [valid_slots]

                    # Base equipment slots
                    for slot in valid_slots:
                        if slot in equipment and equipment[slot] is None:
                            add_choice(f"{slot.title()}", slot=slot)

                    # Subslots on equipped items
                    for parent_slot, equipped_item in equipment.items():
                        if isinstance(equipped_item, dict) and "subslots" in equipped_item:
                            for subslot_data in equipped_item["subslots"]:
                                subslot_type = subslot_data.get("slot", "")
                                if subslot_type in valid_slots and subslot_data.get("current") is None:
                                    conflicts = subslot_data.get("conflicts_with", {})
                                    if conflicts:
                                        conflict_type = conflicts.get("type")
                                        conflict_slot = conflicts.get("slot")
                                        if conflict_type == "main" and conflict_slot in equipment and equipment[conflict_slot] is not None:
                                            continue
                                    label = f"{parent_slot.title()} - {subslot_data.get('name', subslot_type)}"
                                    add_choice(label, parent_slot=parent_slot, subslot=subslot_data)

                    if not choices:
                        self._popup_show_info("Error", f"No available slots for this item. Valid slots: {', '.join(valid_slots)}", sound="error")
                        return

                # Helper to finalize equip once a target is chosen
                def apply_choice(choice):
                    if location == "storage":
                        removed_item = save_data["storage"].pop(item_idx)
                    elif location == "hands":
                        removed_item = save_data["hands"]["items"].pop(item_idx)
                        item_weight = removed_item.get("weight", 0) * removed_item.get("quantity", 1)
                        save_data["hands"]["encumbrance"] = max(0, save_data["hands"].get("encumbrance", 0) - item_weight)
                    else:
                        removed_item = item

                    if choice.get("slot"):
                        save_data["equipment"][choice["slot"]] = removed_item
                    elif choice.get("subslot") is not None:
                        choice["subslot"]["current"] = removed_item

                    self._save_file(save_data)
                    refresh_display()
                    self._play_ui_sound("success")

                # If only one option, auto-equip
                if len(choices) == 1:
                    apply_choice(choices[0])
                    return

                # Prompt user to pick a target when multiple choices exist
                popup = customtkinter.CTkToplevel(self.root)
                popup.title("Select Slot")
                popup.geometry("360x200")
                popup.transient(self.root)

                prompt_label = customtkinter.CTkLabel(popup, text="Choose where to equip:", font=customtkinter.CTkFont(size=14, weight="bold"))
                prompt_label.pack(pady=(15, 10))

                choice_labels = [c["label"] for c in choices]
                selection = customtkinter.StringVar(value=choice_labels[0])

                choice_menu = customtkinter.CTkOptionMenu(popup, values=choice_labels, variable=selection)
                choice_menu.pack(pady=10, padx=20, fill="x")

                button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
                button_frame.pack(pady=15)

                def confirm_choice():
                    label = selection.get()
                    chosen = next((c for c in choices if c["label"] == label), None)
                    if chosen:
                        apply_choice(chosen)
                    popup.destroy()

                def cancel_choice():
                    popup.destroy()

                confirm_btn = self._create_sound_button(button_frame, "Equip", confirm_choice, width=120, height=35)
                confirm_btn.pack(side="left", padx=10)

                cancel_btn = self._create_sound_button(button_frame, "Cancel", cancel_choice, width=120, height=35)
                cancel_btn.pack(side="left", padx=10)

                popup.grab_set()
                popup.lift()
                popup.focus()
            except Exception as e:
                logging.error(f"Equip failed: {e}")
                self._popup_show_info("Error", f"Equip failed: {e}", sound="error")
        
        def unequip_item(slot):
            try:
                item = save_data["equipment"][slot]
                if not item:
                    return
                
                # Move to storage
                save_data["storage"].append(item)
                save_data["equipment"][slot] = None

                # Save using _save_file
                self._save_file(save_data)
                
                refresh_display()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Unequip failed: {e}")
                self._popup_show_info("Error", f"Unequip failed: {e}", sound="error")
        
        def unequip_from_subslot(parent_slot, subslot_data):
            try:
                current_item = subslot_data.get("current")
                if not current_item:
                    return
                
                # Move to storage
                save_data["storage"].append(current_item)
                subslot_data["current"] = None

                # Save using _save_file
                self._save_file(save_data)
                
                refresh_display()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Unequip from subslot failed: {e}")
                self._popup_show_info("Error", f"Unequip failed: {e}", sound="error")
        
        def view_container_contents(container_item):
            try:
                self._play_ui_sound("click")
                
                popup = customtkinter.CTkToplevel(self.root)
                popup.title(f"Container: {container_item.get('name', 'Unknown')}")
                popup.geometry("500x600")
                popup.transient(self.root)
                
                main_container = customtkinter.CTkFrame(popup)
                main_container.pack(fill="both", expand=True, padx=20, pady=20)
                
                title = customtkinter.CTkLabel(
                    main_container,
                    text=container_item.get('name', 'Unknown Container'),
                    font=customtkinter.CTkFont(size=18, weight="bold")
                )
                title.pack(pady=(0, 10))
                
                # Capacity info
                total_weight = sum(i.get("weight", 0) * i.get("quantity", 1) for i in container_item.get("items", []))
                capacity = container_item.get("capacity", 0)
                capacity_label = customtkinter.CTkLabel(
                    main_container,
                    text=f"Capacity: {self._format_weight(total_weight)} / {self._format_weight(capacity)}",
                    font=customtkinter.CTkFont(size=14)
                )
                capacity_label.pack(pady=(0, 15))
                
                # Items list
                items_frame = customtkinter.CTkScrollableFrame(main_container, height=400)
                items_frame.pack(fill="both", expand=True, pady=(0, 10))
                
                items = container_item.get("items", [])
                if items:
                    for i, item in enumerate(items):
                        item_frame = customtkinter.CTkFrame(items_frame)
                        item_frame.pack(fill="x", pady=3, padx=5)
                        
                        item_name = item.get("name", "Unknown")
                        quantity = item.get("quantity", 1)
                        weight = item.get("weight", 0)
                        
                        info_text = f"{item_name}"
                        if quantity > 1:
                            info_text += f" (x{quantity})"
                        info_text += f" - {self._format_weight(weight * quantity)}"
                        
                        item_label = customtkinter.CTkLabel(
                            item_frame,
                            text=info_text,
                            anchor="w"
                        )
                        item_label.pack(side="left", padx=10, pady=5, fill="x", expand=True)
                else:
                    empty_label = customtkinter.CTkLabel(
                        items_frame,
                        text="Container is empty",
                        text_color="gray"
                    )
                    empty_label.pack(pady=20)
                
                # Close button
                close_button = self._create_sound_button(
                    main_container,
                    "Close",
                    popup.destroy,
                    width=120,
                    height=35
                )
                close_button.pack(pady=(10, 0))
                
                popup.update_idletasks()
                popup.grab_set()
                popup.lift()
                popup.focus()
            except Exception as e:
                logging.error(f"View container failed: {e}")
                self._popup_show_info("Error", f"Failed to view container: {e}", sound="error")
        
        refresh_display()
        
        # Back button
        back_button = self._create_sound_button(
            main_frame,
            "Back",
            lambda: [self._clear_window(), self._open_inventory_manager_tool()],
            width=200,
            height=40
        )
        back_button.pack(pady=10)
    def _open_combat_mode_tool(self):
        """Open combat mode interface for weapon simulation and combat mechanics."""
        logging.info("Combat Mode opened")
        logging.debug("currentsave=%s debugmode=%s", currentsave, global_variables.get("debugmode", {}).get("value"))
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded. Please load a character first.", sound="error")
            return
        
        try:
            save_path = os.path.join(saves_folder, currentsave)
            if not save_path.endswith('.sldsv'):
                save_path += '.sldsv'
            with open(save_path, 'r') as f:
                save_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load save: {e}")
            self._popup_show_info("Error", f"Failed to load save: {e}", sound="error")
            return
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table file found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Initialize combat state if not present
        if "combat_state" not in save_data:
            save_data["combat_state"] = {
                "current_weapon_index": 0,  # Index into available weapons list
                "barrel_temperatures": {},  # weapon_id: temperature
                "barrel_cleanliness": {},  # weapon_id: cleanliness (0-100)
                "ambient_temperature": 70  # Fahrenheit
            }
        
        combat_state = save_data["combat_state"]
        
        # Get all equipped weapons (from equipment slots and hands)
        equipped_weapons = self._get_equipped_weapons(save_data, table_data)
        
        if not equipped_weapons:
            self._popup_show_info("Error", "No weapons equipped. Please equip a weapon first.", sound="error")
            return
        
        # Validate current weapon index
        if combat_state["current_weapon_index"] >= len(equipped_weapons):
            combat_state["current_weapon_index"] = 0

        # Passive barrel cooldown based on elapsed time since last update
        now_ts = time.time()
        last_ts = combat_state.get("last_temp_update", now_ts)
        elapsed = max(0.0, now_ts - last_ts)
        ambient = combat_state.get("ambient_temperature", 70)
        if elapsed > 0:
            cooldown_rate = 12.0  # degrees F per second toward ambient
            for wpn in equipped_weapons:
                weapon_id = str(wpn["item"].get("id"))
                temp_map = combat_state.setdefault("barrel_temperatures", {})
                current_temp = temp_map.get(weapon_id, ambient)
                # cool toward ambient
                delta = cooldown_rate * elapsed
                if current_temp > ambient:
                    current_temp = max(ambient, current_temp - delta)
                temp_map[weapon_id] = current_temp
        combat_state["last_temp_update"] = now_ts

        logging.info(
            "Combat UI init: %s weapons, current index=%s (%s)",
            len(equipped_weapons),
            combat_state["current_weapon_index"],
            equipped_weapons[combat_state["current_weapon_index"]]["item"].get("name", "Unknown") if equipped_weapons else "n/a"
        )
        
        self._clear_window()
        self._play_ui_sound("whoosh1")
        
        # Main frame
        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="Combat Mode",
            font=customtkinter.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Ambient temperature display
        temp_frame = customtkinter.CTkFrame(main_frame)
        temp_frame.pack(fill="x", pady=(0, 10))
        
        # Convert temperature based on units
        ambient_temp = combat_state['ambient_temperature']
        if appearance_settings["units"] == "metric":
            ambient_temp = round((ambient_temp - 32) * 5/9, 1)
            temp_unit = "°C"
        else:
            temp_unit = "°F"
        
        ambient_label = customtkinter.CTkLabel(
            temp_frame,
            text=f"Ambient Temperature: {ambient_temp}{temp_unit}",
            font=customtkinter.CTkFont(size=14)
        )
        ambient_label.pack(side="left", padx=10, pady=10)
        
        # Weapon switching controls
        weapon_switch_frame = customtkinter.CTkFrame(main_frame)
        weapon_switch_frame.pack(fill="x", pady=(0, 20))
        
        def refresh_weapon_display():
            """Refresh the entire combat display."""
            self._save_combat_state(save_data)
            self._open_combat_mode_tool()
        
        def select_previous():
            logging.debug(
                "Switching weapon: prev from %s/%s",
                combat_state["current_weapon_index"],
                len(equipped_weapons)
            )
            combat_state["current_weapon_index"] = (combat_state["current_weapon_index"] - 1) % len(equipped_weapons)
            refresh_weapon_display()
        
        def select_next():
            logging.debug(
                "Switching weapon: next from %s/%s",
                combat_state["current_weapon_index"],
                len(equipped_weapons)
            )
            combat_state["current_weapon_index"] = (combat_state["current_weapon_index"] + 1) % len(equipped_weapons)
            refresh_weapon_display()
        
        # Bind keyboard shortcut for weapon switching
        def on_left_arrow(event):
            logging.debug("Left arrow pressed - switching weapon")
            select_previous()
        
        def on_right_arrow(event):
            logging.debug("Right arrow pressed - switching weapon")
            select_next()
        
        self.root.bind("<Left>", on_left_arrow)
        self.root.bind("<Right>", on_right_arrow)
        
        self._create_sound_button(
            weapon_switch_frame,
            text="← Previous Weapon",
            command=select_previous,
            width=150,
            height=40
        ).pack(side="left", padx=10, pady=10)
        
        # Weapon indicator
        current_weapon_data = equipped_weapons[combat_state["current_weapon_index"]]
        current_weapon = current_weapon_data["item"]
        current_weapon_state = {"weapon": current_weapon}  # mutable ref for inline updates
        weapon_name_label = customtkinter.CTkLabel(
            weapon_switch_frame,
            text=f"Selected: {current_weapon.get('name', 'Unknown')}",
            font=customtkinter.CTkFont(size=14, weight="bold")
        )
        weapon_name_label.pack(side="left", padx=20, pady=10, expand=True)
        
        self._create_sound_button(
            weapon_switch_frame,
            text="Next Weapon →",
            command=select_next,
            width=150,
            height=40
        ).pack(side="right", padx=10, pady=10)
        
        # Weapon details section
        details_frame = customtkinter.CTkFrame(main_frame)
        details_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        self._display_weapon_details(details_frame, current_weapon, combat_state, save_data, table_data)

        def update_weapon_view():
            """Update labels/details without rebuilding the whole UI."""
            wpn = current_weapon_state["weapon"]
            weapon_name_label.configure(text=f"Selected: {wpn.get('name', 'Unknown')}")
            for child in details_frame.winfo_children():
                child.destroy()
            self._display_weapon_details(details_frame, wpn, combat_state, save_data, table_data)
            self._save_combat_state(save_data)
        
        # Actions section with sliders
        actions_frame = customtkinter.CTkFrame(main_frame)
        actions_frame.pack(fill="x", pady=(0, 20))
        
        # Round count slider (1-10)
        rounds_label_frame = customtkinter.CTkFrame(actions_frame)
        rounds_label_frame.pack(fill="x", padx=10, pady=5)
        
        customtkinter.CTkLabel(
            rounds_label_frame,
            text="Rounds to Fire:",
            font=customtkinter.CTkFont(size=12)
        ).pack(side="left", padx=10)
        
        rounds_var = customtkinter.IntVar(value=3)
        rounds_value_label = customtkinter.CTkLabel(
            rounds_label_frame,
            text="3",
            font=customtkinter.CTkFont(size=12, weight="bold")
        )
        rounds_value_label.pack(side="left", padx=5)
        
        def update_rounds_label(val):
            rounds_value_label.configure(text=str(int(float(val))))
        
        rounds_slider = customtkinter.CTkSlider(
            rounds_label_frame,
            from_=1,
            to=10,
            variable=rounds_var,
            command=update_rounds_label,
            width=200
        )
        rounds_slider.pack(side="left", padx=10, expand=True, fill="x")
        
        # Fire mode selector (only the weapon's supported actions)
        firemode_label_frame = customtkinter.CTkFrame(actions_frame)
        firemode_label_frame.pack(fill="x", padx=10, pady=5)

        customtkinter.CTkLabel(
            firemode_label_frame,
            text="Fire Mode:",
            font=customtkinter.CTkFont(size=12)
        ).pack(side="left", padx=10)

        supported_modes = current_weapon.get("action", ["Semi"])
        if not supported_modes:
            supported_modes = ["Semi"]

        # Persist selected firemode per-weapon
        selected_modes = combat_state.setdefault("selected_firemode", {})
        weapon_id = str(current_weapon.get("id"))
        initial_mode = selected_modes.get(weapon_id, supported_modes[0])
        if initial_mode not in supported_modes:
            initial_mode = supported_modes[0]

        firemode_var = customtkinter.StringVar(value=initial_mode)

        firemode_menu = customtkinter.CTkOptionMenu(
            firemode_label_frame,
            values=supported_modes,
            variable=firemode_var,
            width=160
        )
        firemode_menu.pack(side="left", padx=10)

        def on_firemode_change(choice):
            selected_modes[weapon_id] = choice
        firemode_menu.configure(command=on_firemode_change)
        
        def fire_weapon():
            wpn = current_weapon_state["weapon"]
            rounds_to_fire = rounds_var.get()
            logging.info(
                "Fire button pressed: weapon=%s, rounds=%s, mode=%s",
                wpn.get("name", "Unknown"),
                rounds_to_fire,
                firemode_var.get()
            )
            try:
                result = self._fire_weapon(wpn, combat_state, rounds_to_fire, firemode_var.get())
                logging.info("Fire result: %s", result)
                self._popup_show_info("Fire Result", result)
            except Exception as e:
                logging.exception("Fire action failed: %s", e)
                self._popup_show_info("Fire Error", str(e))
            update_weapon_view()
        
        def reload_weapon():
            wpn = current_weapon_state["weapon"]
            logging.info("Reload requested for %s", wpn.get("name", "Unknown"))
            result = self._reload_weapon(wpn, save_data)
            self._popup_show_info("Reload Result", result)
            update_weapon_view()
        
        def clean_weapon():
            wpn = current_weapon_state["weapon"]
            logging.info("Clean requested for %s", wpn.get("name", "Unknown"))
            result = self._clean_weapon(wpn, combat_state)
            self._popup_show_info("Clean Result", result)
            update_weapon_view()
        
        # Bind spacebar to fire
        def on_spacebar(event):
            logging.debug("Spacebar pressed - firing")
            fire_weapon()
        
        self.root.bind("<space>", on_spacebar)
        
        self._create_sound_button(
            actions_frame,
            text="Fire (Press SPACE)",
            command=fire_weapon,
            width=150,
            height=50,
            font=customtkinter.CTkFont(size=14)
        ).pack(side="left", padx=10, pady=10)
        
        self._create_sound_button(
            actions_frame,
            text="Reload",
            command=reload_weapon,
            width=150,
            height=50,
            font=customtkinter.CTkFont(size=14)
        ).pack(side="left", padx=10, pady=10)
        
        self._create_sound_button(
            actions_frame,
            text="Clean",
            command=clean_weapon,
            width=150,
            height=50,
            font=customtkinter.CTkFont(size=14),
            fg_color="#006400",
            hover_color="#228B22"
        ).pack(side="left", padx=10, pady=10)

        # Attachment management
        def manage_attachments():
            wpn = current_weapon_state["weapon"]
            accessories = wpn.get("accessories", []) or []
            if not accessories:
                self._popup_show_info("Attachments", "This weapon has no attachment slots.")
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Attachments")
            popup.geometry("420x400")
            popup.transient(self.root)

            rows = []
            storage = save_data.get("storage", [])

            def candidates_for_slot(slot_req):
                matches = []
                for itm in list(storage):
                    if itm and itm.get("attachment"):
                        slot_field = itm.get("slot")
                        if slot_field == slot_req or (isinstance(slot_field, list) and slot_req in slot_field):
                            matches.append(itm)
                return matches

            for acc in accessories:
                frame = customtkinter.CTkFrame(popup)
                frame.pack(fill="x", padx=10, pady=6)
                customtkinter.CTkLabel(frame, text=acc.get("name", "Slot"), font=customtkinter.CTkFont(size=12, weight="bold")).pack(anchor="w")
                opts = [(None, "None")]
                for itm in candidates_for_slot(acc.get("slot")):
                    label = itm.get("name", "Attachment")
                    opts.append((itm, label))
                current_choice = customtkinter.StringVar(value="None")
                option = customtkinter.CTkOptionMenu(frame, values=[o[1] for o in opts], variable=current_choice, width=220)
                option.pack(anchor="w", pady=4)
                rows.append((acc, opts, current_choice))

            def apply_changes():
                for acc, opts, var in rows:
                    chosen_label = var.get()
                    chosen_item = None
                    for itm, lbl in opts:
                        if lbl == chosen_label:
                            chosen_item = itm
                            break
                    # Put existing back to storage if being replaced/removed
                    if acc.get("current"):
                        storage.append(acc["current"])
                    if chosen_item is None:
                        acc["current"] = None
                    else:
                        # remove chosen_item from storage by identity
                        if chosen_item in storage:
                            storage.remove(chosen_item)
                        acc["current"] = chosen_item
                popup.destroy()
                update_weapon_view()

            apply_btn = customtkinter.CTkButton(popup, text="Apply", command=apply_changes, width=120)
            apply_btn.pack(pady=10)

        self._create_sound_button(
            actions_frame,
            text="Manage Attachments",
            command=manage_attachments,
            width=170,
            height=50,
            font=customtkinter.CTkFont(size=14)
        ).pack(side="left", padx=10, pady=10)
        
        # Devmode buttons
        if global_variables.get("devmode", {}).get("value", False):
            devmode_frame = customtkinter.CTkFrame(main_frame)
            devmode_frame.pack(fill="x", pady=(0, 20))
            
            customtkinter.CTkLabel(
                devmode_frame,
                text="DevMode:",
                font=customtkinter.CTkFont(size=12)
            ).pack(side="left", padx=10)

            # Build ammo variant choices from table data matching weapon caliber
            def get_variant_choices():
                choices = []
                caliber_list = current_weapon_state["weapon"].get("caliber", []) or []
                cal = caliber_list[0] if caliber_list else None
                ammo_tables = table_data.get("tables", {}).get("ammo", []) if table_data else []
                for ammo in ammo_tables:
                    if ammo.get("caliber") == cal:
                        for var in ammo.get("variants", []) or []:
                            choices.append(var.get("name", "Unknown"))
                return choices or ["Ball"]

            variant_var = customtkinter.StringVar(value=get_variant_choices()[0])
            customtkinter.CTkLabel(
                devmode_frame,
                text="Variant:",
                font=customtkinter.CTkFont(size=12)
            ).pack(side="left", padx=5)
            customtkinter.CTkOptionMenu(
                devmode_frame,
                values=get_variant_choices(),
                variable=variant_var,
                width=120
            ).pack(side="left", padx=5)
            
            def add_ammo():
                try:
                    current_weapon = current_weapon_state["weapon"]
                    mag_type = current_weapon.get("magazinetype", "Unknown")
                    capacity = current_weapon.get("capacity", 30)

                    # Create a fresh loaded mag with dummy rounds tagged to variant
                    dummy_round = f"{current_weapon.get('caliber', ['rnd'])[0]} | {variant_var.get()}"
                    loaded_mag = {
                        "magazinetype": mag_type,
                        "magazinesystem": current_weapon.get("magazinesystem"),
                        "capacity": capacity,
                        "rounds": [dummy_round for _ in range(capacity)]
                    }
                    current_weapon["loaded"] = loaded_mag

                    # Chamber first round
                    if loaded_mag["rounds"]:
                        current_weapon["chambered"] = loaded_mag["rounds"].pop(0)

                    self._popup_show_info("DevMode Ammo", f"Filled mag ({mag_type}) with {capacity} rounds and chambered one")
                    update_weapon_view()
                except Exception as e:
                    self._popup_show_info("DevMode Error", str(e))
            
            def reset_temperature():
                try:
                    current_weapon = current_weapon_state["weapon"]
                    weapon_id = str(current_weapon.get("id"))
                    combat_state["barrel_temperatures"][weapon_id] = combat_state["ambient_temperature"]
                    self._popup_show_info("DevMode Temp", f"Barrel temperature reset to ambient")
                    update_weapon_view()
                except Exception as e:
                    self._popup_show_info("DevMode Error", str(e))
            
            def reset_cleanliness():
                try:
                    current_weapon = current_weapon_state["weapon"]
                    weapon_id = str(current_weapon.get("id"))
                    combat_state["barrel_cleanliness"][weapon_id] = 100
                    self._popup_show_info("DevMode Clean", f"Barrel cleanliness reset to 100%")
                    update_weapon_view()
                except Exception as e:
                    self._popup_show_info("DevMode Error", str(e))
            
            self._create_sound_button(
                devmode_frame,
                text="Fill Magazine",
                command=add_ammo,
                width=120,
                height=40,
                font=customtkinter.CTkFont(size=12),
                fg_color="#8B4513",
                hover_color="#A0522D"
            ).pack(side="left", padx=5, pady=10)
            
            self._create_sound_button(
                devmode_frame,
                text="Reset Temp",
                command=reset_temperature,
                width=120,
                height=40,
                font=customtkinter.CTkFont(size=12),
                fg_color="#8B4513",
                hover_color="#A0522D"
            ).pack(side="left", padx=5, pady=10)
            
            self._create_sound_button(
                devmode_frame,
                text="Reset Clean",
                command=reset_cleanliness,
                width=120,
                height=40,
                font=customtkinter.CTkFont(size=12),
                fg_color="#8B4513",
                hover_color="#A0522D"
            ).pack(side="left", padx=5, pady=10)
        
        # Weapon list section
        list_label = customtkinter.CTkLabel(
            main_frame,
            text="Available Weapons",
            font=customtkinter.CTkFont(size=14, weight="bold")
        )
        list_label.pack(pady=(10, 5))
        
        list_frame = customtkinter.CTkFrame(main_frame)
        list_frame.pack(fill="both", padx=10, pady=(0, 20))
        
        for idx, weapon_data in enumerate(equipped_weapons):
            weapon_item = weapon_data["item"]
            is_selected = (idx == combat_state["current_weapon_index"])
            
            weapon_btn_frame = customtkinter.CTkFrame(
                list_frame,
                fg_color="#2D3B45" if is_selected else "#1F2B35"
            )
            weapon_btn_frame.pack(fill="x", pady=2)
            
            weapon_label = customtkinter.CTkLabel(
                weapon_btn_frame,
                text=f"{weapon_data['display_name']} - {weapon_data['slot']}",
                font=customtkinter.CTkFont(size=12),
                text_color="#00FF00" if is_selected else "#FFFFFF"
            )
            weapon_label.pack(side="left", padx=10, pady=5)
            
            def switch_to(w_idx=idx):
                combat_state["current_weapon_index"] = w_idx
                refresh_weapon_display()
            
            self._create_sound_button(
                weapon_btn_frame,
                text="Select",
                command=switch_to,
                width=100,
                height=30,
                font=customtkinter.CTkFont(size=11)
            ).pack(side="right", padx=10, pady=5)
        
        # Back button
        self._create_sound_button(
            main_frame,
            text="Exit Combat Mode",
            command=lambda: [self._save_combat_state(save_data), self._clear_window(), self._build_main_menu()],
            fg_color="#8B0000",
            hover_color="#A52A2A",
            height=50,
            font=customtkinter.CTkFont(size=14)
        ).pack(pady=10)
        
        # Save combat state
        self._save_combat_state(save_data)
        self._save_combat_state(save_data)
    
    def _get_equipped_weapons(self, save_data, table_data):
        """Get all equipped weapons from equipment slots and hands."""
        weapons = []
        
        # Check all equipment slots for weapons
        for slot_name, item in save_data.get("equipment", {}).items():
            if item and item.get("firearm"):
                weapons.append({
                    "item": item,
                    "slot": slot_name,
                    "display_name": item.get("name", "Unknown Weapon")
                })
            
            # Check subslots (holsters, slings)
            if item and "subslots" in item:
                for subslot in item["subslots"]:
                    if subslot.get("current") and subslot["current"].get("firearm"):
                        weapons.append({
                            "item": subslot["current"],
                            "slot": f"{slot_name} -> {subslot['name']}",
                            "display_name": subslot["current"].get("name", "Unknown Weapon")
                        })
        
        # Check weapons in hands
        if "hands" in save_data and "items" in save_data["hands"]:
            for hand_item in save_data["hands"]["items"]:
                if hand_item and hand_item.get("firearm"):
                    weapons.append({
                        "item": hand_item,
                        "slot": "Hands",
                        "display_name": hand_item.get("name", "Unknown Weapon")
                    })
        
        return weapons
    
    def _display_weapon_details(self, parent, weapon, combat_state, save_data, table_data):
        """Display detailed information about the selected weapon."""
        detail_frame = customtkinter.CTkFrame(parent)
        detail_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Weapon name and basic info
        name_label = customtkinter.CTkLabel(
            detail_frame,
            text=weapon.get("name", "Unknown Weapon"),
            font=customtkinter.CTkFont(size=16, weight="bold")
        )
        name_label.pack(pady=5)
        
        # Weapon stats
        stats_text = f"Platform: {weapon.get('platform', 'Unknown')}\n"
        stats_text += f"Caliber: {', '.join(weapon.get('caliber', ['Unknown']))}\n"
        stats_text += f"Action: {', '.join(weapon.get('action', ['Unknown']))}\n"
        stats_text += f"Cyclic Rate: {weapon.get('cyclic', 0)} RPM\n"
        stats_text += f"Magazine Type: {weapon.get('magazinetype', 'Unknown')}\n"
        
        if weapon.get("magazinesystem"):
            stats_text += f"Magazine System: {weapon.get('magazinesystem')}\n"
        
        if weapon.get("capacity"):
            stats_text += f"Capacity: {weapon.get('capacity')}\n"
        
        customtkinter.CTkLabel(
            detail_frame,
            text=stats_text,
            font=customtkinter.CTkFont(size=12),
            justify="left"
        ).pack(pady=5)
        
        # Barrel temperature
        weapon_id = weapon.get("id")
        temperature = combat_state.get("barrel_temperatures", {}).get(str(weapon_id), combat_state["ambient_temperature"])
        cleanliness = combat_state.get("barrel_cleanliness", {}).get(str(weapon_id), 100)

        # HUD-based detail control
        has_hud = self._check_for_hud(save_data)

        # Convert temperature based on units
        if appearance_settings["units"] == "metric":
            display_temp = round((temperature - 32) * 5/9, 1)
            temp_unit = "°C"
        else:
            display_temp = temperature
            temp_unit = "°F"

        # Steel heat color approximation (°F): blueish 400-500, purple 500-600, brown 600-700, red/orange above
        if temperature >= 1200:
            temp_color = "#FF5E00"  # bright orange
        elif temperature >= 1000:
            temp_color = "#FF3000"  # red-orange
        elif temperature >= 800:
            temp_color = "#CC0000"  # deep red
        elif temperature >= 700:
            temp_color = "#AA2200"  # dark red-brown
        elif temperature >= 600:
            temp_color = "#A65A2E"  # brown/bronze
        elif temperature >= 500:
            temp_color = "#8040A0"  # purple
        elif temperature >= 400:
            temp_color = "#4060C0"  # blue
        elif temperature >= 300:
            temp_color = "#00A0FF"  # light blue/cyan
        elif temperature >= 212:
            temp_color = "#00C878"  # hot but not visible color shift (greenish)
        elif temperature >= 120:
            temp_color = "#00AA00"  # warm green
        else:
            temp_color = "#007700"  # cool green

        if has_hud:
            temp_text = f"Barrel Temperature: {display_temp}{temp_unit}"
        else:
            # Vague temp categories without HUD
            if temperature > 200:
                temp_desc = "Critical hot"
            elif temperature > 150:
                temp_desc = "Very hot"
            elif temperature > 100:
                temp_desc = "Hot"
            elif temperature > 80:
                temp_desc = "Warm"
            else:
                temp_desc = "Cool"
            temp_text = f"Barrel Temperature: {temp_desc}"

        customtkinter.CTkLabel(
            detail_frame,
            text=temp_text,
            font=customtkinter.CTkFont(size=14),
            text_color=temp_color
        ).pack(pady=5)
        
        clean_color = "#00FF00"  # Green
        if cleanliness < 30:
            clean_color = "#FF0000"  # Red
        elif cleanliness < 50:
            clean_color = "#FFA500"  # Orange
        elif cleanliness < 70:
            clean_color = "#FFFF00"  # Yellow
        
        clean_text = f"Cleanliness: {cleanliness:.1f}%" if has_hud else "Cleanliness: Status only"
        customtkinter.CTkLabel(
            detail_frame,
            text=clean_text,
            font=customtkinter.CTkFont(size=14),
            text_color=clean_color
        ).pack(pady=5)
        
        # Ammo count (vague unless HUD equipped)
        has_hud = self._check_for_hud(save_data)
        ammo_text = self._get_ammo_display(weapon, has_hud)
        
        customtkinter.CTkLabel(
            detail_frame,
            text=ammo_text,
            font=customtkinter.CTkFont(size=14)
        ).pack(pady=5)
        
        # Attachments
        if weapon.get("accessories"):
            customtkinter.CTkLabel(
                detail_frame,
                text="Attachments:",
                font=customtkinter.CTkFont(size=14, weight="bold")
            ).pack(pady=(10, 5))
            
            for accessory in weapon["accessories"]:
                if accessory.get("current"):
                    att_text = f"• {accessory['name']}: {accessory['current'].get('name', 'Unknown')}"
                else:
                    att_text = f"• {accessory['name']}: Empty"
                
                customtkinter.CTkLabel(
                    detail_frame,
                    text=att_text,
                    font=customtkinter.CTkFont(size=12)
                ).pack(anchor="w", padx=20)
    
    def _check_for_hud(self, save_data):
        """Check if player has a HUD equipped."""
        for slot_name, item in save_data.get("equipment", {}).items():
            if item and item.get("hud"):
                return True
        return False
    
    def _get_ammo_display(self, weapon, has_hud):
        """Get ammo display text (vague or exact based on HUD)."""
        loaded_mag = weapon.get("loaded")
        chambered = weapon.get("chambered")
        
        if not loaded_mag and not chambered:
            return "Ammo: Empty"
        
        total_rounds = 0
        if chambered:
            total_rounds += 1
        
        if loaded_mag:
            rounds_in_mag = len(loaded_mag.get("rounds", []))
            total_rounds += rounds_in_mag
        
        if has_hud:
            # Exact count with HUD
            chamber_text = " (+1 chambered)" if chambered else ""
            return f"Ammo: {total_rounds} rounds{chamber_text}"
        else:
            # Without HUD, exact count hidden; require mag check
            if not loaded_mag and chambered:
                return "Ammo: Unknown (mag out, round chambered)"
            if not loaded_mag:
                return "Ammo: Mag removed"
            return "Ammo: Unknown (remove mag to check)"
    
    def _save_combat_state(self, save_data):
        """Save combat state to save file."""
        try:
            save_path = os.path.join(saves_folder, currentsave)
            if not save_path.endswith(global_variables.get("save_extension", ".sldsv")):
                save_path += global_variables.get("save_extension", ".sldsv")
            with open(save_path, 'w') as f:
                json.dump(save_data, f, indent=4)
            logging.info("Combat state saved to %s", save_path)
        except Exception as e:
            logging.error(f"Failed to save combat state: {e}")
    
    def _get_firearm_sound_folder(self, weapon):
        """Get the sound folder for a weapon based on its caliber."""
        caliber = weapon.get("caliber", [])[0] if weapon.get("caliber") else None
        
        if not caliber:
            return None
        
        # Map caliber to sound folder names
        caliber_map = {
            "5.56x45mm NATO": "556",
            ".45 ACP": "45acp",
            "9x19mm Parabellum": "9x19",
            "12 Gauge": "12gauge",
            "7.62x51mm NATO": "762_51",
            "7.62x39mm": "762_39",
            "7.62x54mmR": "762_54",
            ".308 Winchester": "308",
            ".223 Remington": "223",
            ".380 ACP": "380acp",
            "5.45x39mm": "545_39",
            "9x18mm Makarov": "9x18",
            ".357 Magnum": "357mag",
            ".44 Magnum": "44mag",
            ".38 Special": "38special",
            ".50 AE": "50ae",
            "20 Gauge": "20gauge",
            ".410 Bore": "410bore",
            ".45-70 Government": "45_70",
            ".30-06 Springfield": "30_06",
            ".30-30 Winchester": "30_30",
            ".277 Wolverine": "277baker",
            ".224 Valkyrie": "224baker",
            ".303 British": "303"
        }
        
        return caliber_map.get(caliber)
    
    def _check_weapon_suppressed(self, weapon):
        """Check if weapon is suppressed (integrally or via attachment)."""
        # Check for integral suppressor
        if weapon.get("suppressed"):
            return True
        
        # Check for suppressor attachment
        if weapon.get("accessories"):
            for accessory in weapon["accessories"]:
                if accessory.get("current") and accessory["current"].get("suppressor"):
                    return True
        
        return False
    
    def _play_firearm_sound(self, weapon, sound_type="fire"):
        """Play firearm sound with proper variants."""
        try:
            sound_folder = self._get_firearm_sound_folder(weapon)
            
            if not sound_folder:
                logging.warning(f"No sound folder found for weapon: {weapon.get('name')}")
                return
            
            # Check for custom equip sound
            if sound_type == "equip" and weapon.get("custom_equip_sound"):
                sound_path = weapon["custom_equip_sound"]
                if os.path.exists(sound_path):
                    self._safe_sound_play("", sound_path)
                    return
            
            # For equip sounds, use placeholder (to be added later)
            if sound_type == "equip":
                logging.info(f"Equip sound placeholder for {weapon.get('name')}")
                return
            
            # Determine if suppressed
            is_suppressed = self._check_weapon_suppressed(weapon)
            
            # Build sound path
            base_path = f"sounds/firearms/{sound_folder}"
            
            # Special handling for SMG sounds in .45 ACP
            subtype = weapon.get("subtype", "")
            if sound_folder == "45acp" and subtype == "smg" and sound_type == "fire":
                suppressed_suffix = "_suppressed" if is_suppressed else ""
                smg_files = glob.glob(f"{base_path}/fire*_smg{suppressed_suffix}.wav")
                if smg_files:
                    sound_file = random.choice(smg_files)
                    self._safe_sound_play("", sound_file)
                    return
            
            # Standard fire sound
            if sound_type == "fire":
                if is_suppressed:
                    fire_files = glob.glob(f"{base_path}/fire*_suppressed.wav")
                else:
                    # Grab all fire*.wav and drop suppressed variants
                    fire_candidates = glob.glob(f"{base_path}/fire*.wav")
                    fire_files = [f for f in fire_candidates if "_suppressed" not in os.path.basename(f)]
                
                # Fallback to universal suppressed sounds if no specific ones
                if is_suppressed and not fire_files:
                    if subtype in ["rifle", "mg"]:
                        fallback_files = glob.glob("sounds/firearms/universal/riflefire_suppressed.wav")
                    elif subtype in ["pistol", "smg"]:
                        fallback_files = glob.glob("sounds/firearms/universal/pistolfire_suppressed.wav")
                    elif subtype == "shotgun":
                        fallback_files = glob.glob("sounds/firearms/universal/shotgunfire.wav")
                    else:
                        fallback_files = []
                    
                    if fallback_files:
                        fire_files = fallback_files
                
                if fire_files:
                    sound_file = random.choice(fire_files)
                    logging.debug("Fire sound selected: %s", sound_file)
                    self._safe_sound_play("", sound_file)
                else:
                    logging.warning(f"No fire sounds found for {sound_folder}")
            
        except Exception as e:
            logging.error(f"Error playing firearm sound: {e}")
    
    def _play_weapon_action_sound(self, weapon, action_type):
        """Play weapon action sounds (reload, bolt, etc)."""
        try:
            platform = weapon.get("platform", "").lower()
            
            # Map platforms to weaponsound folders
            platform_folders = {
                "ar-15": "ar-15",
                "m4": "ar-15",
                "m16": "ar-15",
                "ump": "ump",
                "92fs": "92fs",
                "m9": "92fs",
                "beretta": "92fs",
                "m249": "m249",
                "m203": "m203"
            }
            
            platform_folder = None
            for key, folder in platform_folders.items():
                if key in platform.lower():
                    platform_folder = folder
                    break
            
            # Try platform-specific sound first
            if platform_folder:
                sound_path = f"sounds/firearms/weaponsounds/{platform_folder}/{action_type}.ogg"
                if os.path.exists(sound_path):
                    self._safe_sound_play("", sound_path)
                    return
            
            # Fall back to universal sounds
            universal_sounds = {
                "magin": ["riflemagin", "pistolmagin"],
                "magout": ["riflemagout", "pistolmagout"],
                "boltback": ["rifleboltback", "pistolslideback", "boltactionback"],
                "boltforward": ["rifleboltforward", "pistolslideforward", "boltactionforward"],
                "cleaning": ["cleaning"]
            }
            
            if action_type in universal_sounds:
                for sound_name in universal_sounds[action_type]:
                    sound_path = f"sounds/firearms/universal/{sound_name}.ogg"
                    if os.path.exists(sound_path):
                        self._safe_sound_play("", sound_path)
                        break
            
        except Exception as e:
            logging.error(f"Error playing weapon action sound: {e}")
    
    def _fire_weapon(self, weapon, combat_state, rounds_to_fire=3, fire_mode=None):
        """Fire weapon and handle barrel temperature, jamming, etc."""
        weapon_id = str(weapon.get("id"))
        logging.info(
            "_fire_weapon start: id=%s name=%s rounds=%s mode=%s",
            weapon_id,
            weapon.get("name", "Unknown"),
            rounds_to_fire,
            fire_mode or "unknown"
        )
        
        # Check if weapon has ammo
        chambered = weapon.get("chambered")
        loaded_mag = weapon.get("loaded")
        
        if not chambered and (not loaded_mag or not loaded_mag.get("rounds")):
            logging.info("Weapon empty - dry fire")
            self._safe_sound_play("sounds/firearms/universal", "dryfire.ogg")
            return "Empty! No rounds to fire."
        
        # Get current barrel stats
        temperature = combat_state.get("barrel_temperatures", {}).get(weapon_id, combat_state["ambient_temperature"])
        cleanliness = combat_state.get("barrel_cleanliness", {}).get(weapon_id, 100)
        
        # Calculate jam chance (base + temperature modifier + cleanliness modifier)
        base_jamrate = weapon.get("jamrate", 0.01)
        
        # Temperature increases jam chance
        temp_modifier = 0
        if temperature > 200:
            temp_modifier = 0.10
        elif temperature > 150:
            temp_modifier = 0.05
        elif temperature > 100:
            temp_modifier = 0.02
        
        # Cleanliness decreases jam chance
        clean_modifier = (100 - cleanliness) / 1000  # Up to +10% jam chance at 0 cleanliness
        
        total_jamrate = base_jamrate + temp_modifier + clean_modifier
        logging.debug(
            "Jam calc: base=%s temp_mod=%s clean_mod=%s total=%s temp=%s clean=%s",
            base_jamrate,
            temp_modifier,
            clean_modifier,
            total_jamrate,
            temperature,
            cleanliness
        )
        
        # Timing model
        cyclic = weapon.get("cyclic", 600) or 600
        base_delay = max(0.0, 60.0 / cyclic)
        human_delay = 0.18 if fire_mode in ("Semi", "Burst") else 0.0

        # Fire rounds
        rounds_fired = 0
        jammed = False
        
        for i in range(rounds_to_fire):
            # Check for jam
            if random.random() < total_jamrate:
                jammed = True
                logging.info(f"Weapon jammed after {rounds_fired} rounds!")
                break
            
            # Fire round
            if chambered:
                self._play_firearm_sound(weapon, "fire")
                rounds_fired += 1
                chambered = None
                
                # Try to chamber next round
                if loaded_mag and loaded_mag.get("rounds"):
                    chambered = loaded_mag["rounds"].pop(0)
                
            elif loaded_mag and loaded_mag.get("rounds"):
                chambered = loaded_mag["rounds"].pop(0)
                self._play_firearm_sound(weapon, "fire")
                rounds_fired += 1
            else:
                # Out of ammo mid-burst
                logging.info("Ran out of ammo mid-burst after %s rounds", rounds_fired)
                break
            
            # Increase barrel temperature per shot
            temperature += random.uniform(15, 25)
            
            # Decrease cleanliness per shot
            cleanliness -= random.uniform(0.1, 0.3)
            cleanliness = max(0, cleanliness)

            # Apply timing delay per shot/burst to simulate human reaction on semi/burst
            time.sleep(base_delay + human_delay)
        
        # Update weapon state
        weapon["chambered"] = chambered
        weapon["loaded"] = loaded_mag
        
        # Save barrel stats
        if "barrel_temperatures" not in combat_state:
            combat_state["barrel_temperatures"] = {}
        if "barrel_cleanliness" not in combat_state:
            combat_state["barrel_cleanliness"] = {}
        
        combat_state["barrel_temperatures"][weapon_id] = temperature
        combat_state["barrel_cleanliness"][weapon_id] = cleanliness
        combat_state["last_temp_update"] = time.time()
        
        # Return result message
        if jammed:
            return f"Fired {rounds_fired} rounds - WEAPON JAMMED! Clear jam and try again."
        else:
            return f"Fired {rounds_fired} rounds successfully."
    
    def _reload_weapon(self, weapon, save_data, combat_reload=False):
        """Reload weapon from available magazines."""
        logging.info(
            "_reload_weapon start: name=%s magsystem=%s combat_reload=%s",
            weapon.get("name", "Unknown"),
            weapon.get("magazinesystem"),
            combat_reload
        )
        # TODO: Implement magazine searching and reloading
        # This requires searching storage/equipment for compatible magazines
        
        magazine_system = weapon.get("magazinesystem")
        if not magazine_system:
            return "Weapon doesn't use magazines."
        
        # Search for compatible magazines in storage, hands, and equipment
        compatible_mags = []
        
        # Check storage
        for item in save_data.get("storage", []):
            if item and item.get("magazinesystem") == magazine_system:
                rounds = item.get("rounds", [])
                if rounds and len(rounds) > 0:
                    compatible_mags.append(item)
        
        # Check hands
        for item in save_data.get("hands", {}).get("items", []):
            if item and item.get("magazinesystem") == magazine_system:
                rounds = item.get("rounds", [])
                if rounds and len(rounds) > 0:
                    compatible_mags.append(item)
        
        if not compatible_mags:
            return "No compatible loaded magazines found!"
        
        # Sort by fullness
        compatible_mags.sort(key=lambda m: len(m.get("rounds", [])), reverse=True)
        
        # Take first available mag
        new_mag = compatible_mags[0]
        
        # Handle current magazine
        current_mag = weapon.get("loaded")
        if current_mag and not combat_reload:
            # Put current mag back in storage
            save_data["storage"].append(current_mag)
        
        # Load new magazine and remove from source
        weapon["loaded"] = new_mag
        
        # Remove from storage if found there
        if new_mag in save_data.get("storage", []):
            save_data["storage"].remove(new_mag)
        # Remove from hands if found there
        elif new_mag in save_data.get("hands", {}).get("items", []):
            save_data["hands"]["items"].remove(new_mag)
        
        # Play reload sounds
        self._play_weapon_action_sound(weapon, "magout")
        time.sleep(0.3)
        self._play_weapon_action_sound(weapon, "magin")
        
        return f"Reloaded with magazine ({len(new_mag.get('rounds', []))} rounds)"
    
    def _clean_weapon(self, weapon, combat_state):
        """Clean weapon to restore reliability."""
        weapon_id = str(weapon.get("id"))
        logging.info("_clean_weapon start: id=%s name=%s", weapon_id, weapon.get("name", "Unknown"))
        
        # Play cleaning sound
        self._play_weapon_action_sound(weapon, "cleaning")
        
        # Restore cleanliness
        if "barrel_cleanliness" not in combat_state:
            combat_state["barrel_cleanliness"] = {}
        
        combat_state["barrel_cleanliness"][weapon_id] = 100
        
        return "Weapon cleaned and maintained."
    def _safe_exit(self):
        if currentsave is not None:
            logging.info("Exiting with current save loaded (no auto-save on exit).")
        else:
            logging.info("No current save loaded at exit.")
        logging.info("Program exited safely.")
        self.root.quit()
    def _open_settings(self):
        logging.info("Settings definition called")

        self._clear_window()

        # Track initial state for unsaved changes detection
        appearance_settings_initial = appearance_settings.copy()
        global_variables_initial = {k: v.copy() if isinstance(v, dict) else v for k, v in global_variables.items()}
        settings_modified = [False]  # Use list to allow modification in nested functions

        # Build theme sources (built-in + themes folder)
        builtin_themes = ["dark-blue", "blue", "green"]
        themes_dir = os.path.join(os.getcwd(), "themes")
        custom_theme_files = []
        if os.path.isdir(themes_dir):
            custom_theme_files = [f for f in os.listdir(themes_dir) if f.endswith(".json")]
        theme_sources = {name: name for name in builtin_themes}
        for fname in custom_theme_files:
            name = os.path.splitext(fname)[0]
            theme_sources[name] = os.path.join(themes_dir, fname)
        available_theme_names = list(theme_sources.keys())
        if not available_theme_names:
            available_theme_names = ["dark-blue"]
            theme_sources = {"dark-blue": "dark-blue"}

        # Helpers
        def update_appearance():
            settings_modified[0] = True
            customtkinter.set_appearance_mode(appearance_settings["appearance_mode"])
            theme_key = appearance_settings.get("color_theme", "dark-blue")
            theme_target = theme_sources.get(theme_key, "dark-blue")
            try:
                customtkinter.set_default_color_theme(theme_target)
            except Exception as e:
                logging.warning(f"Failed to load theme '{theme_target}': {e}")
                appearance_settings["color_theme"] = "dark-blue"
                fallback = theme_sources.get("dark-blue", "dark-blue")
                try:
                    customtkinter.set_default_color_theme(fallback)
                except Exception as e2:
                    logging.error(f"Fallback theme load failed: {e2}")
            # Save appearance settings
            try:
                appearance_settings_path = os.path.join(saves_folder, "appearance_settings.sldsv")
                with open(appearance_settings_path, 'w') as f:
                    json.dump(appearance_settings, f, indent=4)
                logging.info(f"Appearance settings saved to {appearance_settings_path}")
            except Exception as e:
                logging.error(f"Failed to save appearance settings: {e}")
            # Rebuild settings UI to immediately reflect the theme change
            self._clear_window()
            self._open_settings()
            try:
                self.root.geometry(appearance_settings["resolution"])
            except Exception as e:
                logging.warning(f"Failed to apply resolution {appearance_settings['resolution']}: {e}")
            self.root.attributes('-fullscreen', appearance_settings.get("fullscreen", False))
            if appearance_settings.get("borderless", False):
                self.root.overrideredirect(True)
            else:
                self.root.overrideredirect(False)

        # Main layout
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure((0, 1), weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        title = customtkinter.CTkLabel(main_frame, text="Settings", font=customtkinter.CTkFont(size=22, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 15))

        content = customtkinter.CTkFrame(main_frame)
        content.grid(row=1, column=0, columnspan=2, sticky="nsew")
        content.grid_columnconfigure((0, 1), weight=1)

        # Appearance settings column
        appearance_frame = customtkinter.CTkFrame(content)
        appearance_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)
        appearance_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(appearance_frame, text="Appearance", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky="w")

        # appearance_mode
        customtkinter.CTkLabel(appearance_frame, text="Mode:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        mode_box = customtkinter.CTkOptionMenu(
            appearance_frame,
            values=["system", "dark", "light"],
            command=lambda v: appearance_settings.__setitem__("appearance_mode", v) or update_appearance()
        )
        mode_box.set(appearance_settings.get("appearance_mode", "system"))
        mode_box.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        # color_theme
        customtkinter.CTkLabel(appearance_frame, text="Color Theme:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        theme_box = customtkinter.CTkOptionMenu(
            appearance_frame,
            values=available_theme_names,
            command=lambda v: appearance_settings.__setitem__("color_theme", v) or update_appearance()
        )
        selected_theme = appearance_settings.get("color_theme", "dark-blue")
        if selected_theme not in available_theme_names:
            selected_theme = "dark-blue"
        theme_box.set(selected_theme)
        theme_box.grid(row=2, column=1, sticky="ew", padx=10, pady=4)

        # resolution (options filtered to the user's max screen size, with multiple aspect ratios)
        customtkinter.CTkLabel(appearance_frame, text="Resolution:").grid(row=3, column=0, sticky="w", padx=10, pady=4)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        common_res = [
            "5120x1440", "3840x2400", "3840x2160", "3840x1080", "2560x1600", "2560x1440", 
            "2560x1080", "1920x1200", "1920x1080", "1680x1050", "1600x1200", "1600x900", 
            "1440x900", "1366x768", "1280x960", "1280x800", "1280x720"
        ]

        def _fits(res_str: str) -> bool:
            try:
                w, h = map(int, res_str.split("x"))
                return w <= screen_w and h <= screen_h
            except Exception:
                return False

        def _aspect_label(res_str: str) -> str:
            try:
                w, h = map(int, res_str.split("x"))
                ratio = w / h if h else 0

                # Snap to common aspect ratios for friendlier labels (e.g., 2560x1080 -> 21:9)
                common_aspects = [
                    (16, 9), (16, 10), (21, 9), (32, 9), (4, 3), (5, 4), (3, 2),
                    (17, 9), (19, 10), (18, 9)
                ]
                closest = min(common_aspects, key=lambda a: abs(ratio - (a[0] / a[1]))) if h else (w, h)
                closest_ratio = closest[0] / closest[1] if closest[1] else ratio

                # If within tolerance, use the snapped ratio; otherwise fall back to reduced fraction
                if h and abs(ratio - closest_ratio) <= 0.05:
                    aspect = f"{closest[0]}:{closest[1]}"
                else:
                    g = math.gcd(w, h)
                    aspect = f"{w//g}:{h//g}" if g else f"{w}:{h}"

                return f"{w}x{h} ({aspect})"
            except Exception:
                return res_str

        filtered_res = []
        seen = set()
        for r in common_res:
            if r not in seen and _fits(r):
                filtered_res.append(r)
                seen.add(r)

        current_res = appearance_settings.get("resolution", "1920x1080")
        if current_res not in filtered_res and _fits(current_res):
            filtered_res.insert(0, current_res)

        if not filtered_res:
            filtered_res = [f"{screen_w}x{screen_h}"]

        labeled_values = [_aspect_label(r) for r in filtered_res]

        current_label = _aspect_label(current_res)
        if current_label not in labeled_values and _fits(current_res):
            labeled_values.insert(0, current_label)

        def _on_resolution_change(label_val: str):
            res_val = label_val.split(" ")[0]
            appearance_settings["resolution"] = res_val
            update_appearance()

        resolution_box = customtkinter.CTkOptionMenu(
            appearance_frame,
            values=labeled_values,
            command=_on_resolution_change
        )
        resolution_box.set(current_label if current_label in labeled_values else labeled_values[0])
        resolution_box.grid(row=3, column=1, sticky="ew", padx=10, pady=4)

        # fullscreen
        fullscreen_switch = customtkinter.CTkCheckBox(
            appearance_frame,
            text="Fullscreen",
            command=lambda: (appearance_settings.__setitem__("fullscreen", bool(fullscreen_switch.get())), update_appearance())
        )
        fullscreen_switch.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        fullscreen_switch.select() if appearance_settings.get("fullscreen", False) else fullscreen_switch.deselect()

        # borderless
        borderless_switch = customtkinter.CTkCheckBox(
            appearance_frame,
            text="Borderless",
            command=lambda: (appearance_settings.__setitem__("borderless", bool(borderless_switch.get())), update_appearance())
        )
        borderless_switch.grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        borderless_switch.select() if appearance_settings.get("borderless", False) else borderless_switch.deselect()

        # units
        customtkinter.CTkLabel(appearance_frame, text="Units:").grid(row=6, column=0, sticky="w", padx=10, pady=4)
        units_box = customtkinter.CTkOptionMenu(
            appearance_frame,
            values=["imperial", "metric"],
            command=lambda v: (appearance_settings.__setitem__("units", v), settings_modified.__setitem__(0, True))
        )
        units_box.set(appearance_settings.get("units", "imperial"))
        units_box.grid(row=6, column=1, sticky="ew", padx=10, pady=4)

        # sound volume
        customtkinter.CTkLabel(appearance_frame, text="Sound Volume:").grid(row=8, column=0, sticky="w", padx=10, pady=(8,4))
        volume_slider = customtkinter.CTkSlider(
            appearance_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            command=lambda v: (appearance_settings.__setitem__("sound_volume", int(v)), settings_modified.__setitem__(0, True))
        )
        volume_slider.grid(row=8, column=1, sticky="ew", padx=10, pady=(8,4))
        volume_slider.set(appearance_settings.get("sound_volume", 100))

        # Tables / global vars column
        right_frame = customtkinter.CTkFrame(content)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=10)
        right_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(right_frame, text="Data", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(10,5), sticky="w")

        # Table selection
        customtkinter.CTkLabel(right_frame, text="Table (.sldtbl):").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        try:
            table_files = [f for f in os.listdir("tables") if f.endswith(global_variables.get("table_extension", ".sldtbl"))]
        except FileNotFoundError:
            table_files = []
        
        # Build table display names from pretty names
        table_display_names = []
        table_name_map = {}  # Map display name to filename
        
        for table_file in table_files:
            try:
                table_path = os.path.join("tables", table_file)
                with open(table_path, 'r') as f:
                    table_data = json.load(f)
                pretty_name = table_data.get("prettyname", table_file)
                table_display_names.append(pretty_name)
                table_name_map[pretty_name] = table_file.replace(".sldtbl", "")
            except Exception as e:
                logging.warning(f"Failed to load table pretty name for {table_file}: {e}")
                table_display_names.append(table_file)
                table_name_map[table_file] = table_file.replace(".sldtbl", "")
        
        if not table_display_names:
            table_display_names = ["<none>"]
            table_name_map["<none>"] = None
        
        table_box = customtkinter.CTkOptionMenu(
            right_frame,
            values=table_display_names,
            state="disabled" if table_display_names == ["<none>"] else "normal",
            command=lambda v: (global_variables.__setitem__("current_table", table_name_map.get(v)), settings_modified.__setitem__(0, True))
        )
        
        # Set current selection based on current_table filename
        current_table_val = global_variables.get("current_table")
        current_display_name = "<none>"
        if current_table_val:
            for display_name, filename in table_name_map.items():
                if filename == current_table_val:
                    current_display_name = display_name
                    break
        
        table_box.set(current_display_name)
        table_box.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        # Dev/global toggles (only if devmode enabled)
        customtkinter.CTkLabel(right_frame, text="Developer Flags", font=customtkinter.CTkFont(size=14, weight="bold")).grid(row=2, column=0, columnspan=2, pady=(12,4), sticky="w")
        dev_enabled = global_variables.get("devmode", {}).get("value", False)

        def make_toggle(row, label, key):
            chk = customtkinter.CTkCheckBox(
                right_frame,
                text=label,
                state="normal" if dev_enabled else "disabled",
                command=lambda k=key, c=lambda: chk.get(): (global_variables[k].__setitem__("value", bool(c())), settings_modified.__setitem__(0, True))
            )
            chk.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=4)
            if global_variables[key].get("value", False):
                chk.select()
            else:
                chk.deselect()
            return chk

        dev_chk = make_toggle(3, "Development Mode", "devmode")
        dm_chk = make_toggle(4, "DM Mode", "dmmode")
        debug_chk = make_toggle(5, "Debug Mode", "debugmode")

        if not dev_enabled:
            info_label = customtkinter.CTkLabel(right_frame, text="Enable devmode to edit these", text_color="gray")
            info_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=(0,8))

        # Button frame for Save and Back buttons
        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10,0))
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        def save_settings():
            try:
                # Save appearance settings
                appearance_settings_path = os.path.join(saves_folder, "appearance_settings.sldsv")
                with open(appearance_settings_path, 'w') as f:
                    json.dump(appearance_settings, f, indent=4)
                logging.info(f"Appearance settings saved to {appearance_settings_path}")
                
                # Save global variables/settings
                settings_path = os.path.join(saves_folder, "settings.sldsv")
                with open(settings_path, 'w') as f:
                    json.dump(global_variables, f, indent=4)
                logging.info(f"Global settings saved to {settings_path}")
                
                settings_modified[0] = False
                self._popup_show_info("Success", "Settings saved successfully!", sound="success")
            except Exception as e:
                logging.error(f"Failed to save settings: {e}")
                self._popup_show_info("Error", f"Failed to save settings: {e}", sound="error")
        
        def go_back():
            if settings_modified[0]:
                def confirm_leave():
                    self._clear_window()
                    self._build_main_menu()
                    confirm_window.destroy()
                
                def cancel_leave():
                    confirm_window.destroy()
                
                confirm_window = customtkinter.CTkToplevel(self.root)
                confirm_window.title("Unsaved Changes")
                confirm_window.geometry("400x150")
                confirm_window.transient(self.root)
                
                msg_label = customtkinter.CTkLabel(
                    confirm_window,
                    text="You have unsaved changes.\nDo you want to leave without saving?",
                    font=customtkinter.CTkFont(size=12)
                )
                msg_label.pack(pady=20)
                
                button_frame_confirm = customtkinter.CTkFrame(confirm_window, fg_color="transparent")
                button_frame_confirm.pack(pady=10)
                button_frame_confirm.grid_columnconfigure((0, 1), weight=1)
                
                leave_btn = self._create_sound_button(
                    button_frame_confirm,
                    "Leave",
                    confirm_leave,
                    width=150,
                    height=35
                )
                leave_btn.grid(row=0, column=0, padx=(0, 10))
                
                cancel_btn = self._create_sound_button(
                    button_frame_confirm,
                    "Cancel",
                    cancel_leave,
                    width=150,
                    height=35
                )
                cancel_btn.grid(row=0, column=1, padx=(10, 0))
                
                confirm_window.grab_set()
            else:
                self._clear_window()
                self._build_main_menu()
        
        save_button = self._create_sound_button(
            button_frame,
            "Save Settings",
            save_settings,
            width=200,
            height=40
        )
        save_button.grid(row=0, column=0, padx=(0, 10))
        
        back_button = self._create_sound_button(
            button_frame,
            "Back",
            go_back,
            width=200,
            height=40
        )
        back_button.grid(row=0, column=1, padx=(10, 0))
    def _open_add_item_by_id_tool(self):
        logging.info("Add Item By ID definition called")
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table files found.", sound="error")
                return
            
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
            
            # Collect all items from all tables
            all_items = []
            for table_name, items in table_data.get("tables", {}).items():
                for item in items:
                    item_copy = item.copy()
                    item_copy["table_category"] = table_name
                    all_items.append(item_copy)
            
            if not all_items:
                self._popup_show_info("Error", "No items found in table.", sound="error")
                return
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Build UI
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        title = customtkinter.CTkLabel(main_frame, text="Add Item to Inventory By ID", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, pady=(0, 10))
        
        # Search frame
        search_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=10)
        search_frame.grid_columnconfigure(1, weight=1)
        
        search_label = customtkinter.CTkLabel(search_frame, text="Search (ID or Name):", font=customtkinter.CTkFont(size=13))
        search_label.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        search_entry = customtkinter.CTkEntry(search_frame, placeholder_text="Enter item ID or name...")
        search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        # Scrollable item list
        scroll_frame = customtkinter.CTkScrollableFrame(main_frame, width=900, height=500)
        scroll_frame.grid(row=2, column=0, sticky="nsew", pady=10)
        scroll_frame.grid_columnconfigure(0, weight=1)
        
        def filter_and_display_items(search_term=""):
            # Clear existing items
            for widget in scroll_frame.winfo_children():
                widget.destroy()
            
            # Filter items
            search_lower = search_term.lower().strip()
            filtered_items = []
            
            if search_lower:
                for item in all_items:
                    item_id = str(item.get("id", ""))
                    item_name = item.get("name", "").lower()
                    if search_lower in item_id or search_lower in item_name:
                        filtered_items.append(item)
            else:
                filtered_items = all_items
            
            # Sort by ID
            filtered_items.sort(key=lambda x: x.get("id", 999999))
            
            if not filtered_items:
                no_results = customtkinter.CTkLabel(scroll_frame, text="No items found.", font=customtkinter.CTkFont(size=14), text_color="gray")
                no_results.pack(pady=20)
                return
            
            def add_item_to_inventory(item):
                try:
                    save_path = os.path.join(saves_folder, currentsave + ".sldsv")
                    with open(save_path, 'r') as f:
                        save_data = json.load(f)
                    
                    # Create a clean copy of the item (remove table_category)
                    item_to_add = {k: v for k, v in item.items() if k != "table_category"}
                    
                    # Add subslots if applicable
                    item_to_add = add_subslots_to_item(item_to_add)
                    
                    # Add to storage
                    save_data["storage"].append(item_to_add)
                    
                    # Save
                    with open(save_path, 'w') as f:
                        json.dump(save_data, f, indent=4)
                    
                    logging.info(f"Added item ID {item.get('id')} ({item.get('name')}) to storage")
                    self._popup_show_info("Success", f"Added '{item.get('name')}' to storage!", sound="success")
                except Exception as e:
                    logging.error(f"Failed to add item: {e}")
                    self._popup_show_info("Error", f"Failed to add item: {e}", sound="error")
            
            # Display filtered items
            for i, item in enumerate(filtered_items):
                item_frame = customtkinter.CTkFrame(scroll_frame)
                item_frame.pack(fill="x", pady=5, padx=10)
                item_frame.grid_columnconfigure(1, weight=1)
                
                # ID badge
                id_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"ID: {item.get('id', 'N/A')}",
                    font=customtkinter.CTkFont(size=12, weight="bold"),
                    width=80,
                    fg_color=("gray75", "gray25"),
                    corner_radius=6
                )
                id_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
                
                # Item details
                details_frame = customtkinter.CTkFrame(item_frame, fg_color="transparent")
                details_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
                
                name_label = customtkinter.CTkLabel(
                    details_frame,
                    text=item.get("name", "Unknown"),
                    font=customtkinter.CTkFont(size=14, weight="bold"),
                    anchor="w"
                )
                name_label.pack(anchor="w")
                
                category_label = customtkinter.CTkLabel(
                    details_frame,
                    text=f"Category: {item.get('table_category', 'N/A')} | Rarity: {item.get('rarity', 'N/A')} | Value: ${item.get('value', 0)}",
                    font=customtkinter.CTkFont(size=11),
                    text_color="gray",
                    anchor="w"
                )
                category_label.pack(anchor="w", pady=(2, 0))
                
                if "description" in item and item["description"]:
                    desc_label = customtkinter.CTkLabel(
                        details_frame,
                        text=item["description"][:100] + ("..." if len(item["description"]) > 100 else ""),
                        font=customtkinter.CTkFont(size=10),
                        text_color="gray",
                        anchor="w",
                        wraplength=500
                    )
                    desc_label.pack(anchor="w", pady=(2, 0))
                
                # Add button
                add_button = self._create_sound_button(
                    item_frame,
                    "Add to Storage",
                    lambda it=item: add_item_to_inventory(it),
                    width=150,
                    height=35,
                    font=customtkinter.CTkFont(size=12)
                )
                add_button.grid(row=0, column=2, padx=10, pady=10)
        
        # Search callback
        def on_search_change(*args):
            filter_and_display_items(search_entry.get())
        
        search_entry.bind("<KeyRelease>", on_search_change)
        
        # Initial display
        filter_and_display_items()
        
        # Button frame
        button_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, pady=10)
        
        back_button = self._create_sound_button(
            button_frame,
            "Back",
            lambda: [self._clear_window(), self._open_modify_save_data_tool()],
            width=200,
            height=40,
            font=customtkinter.CTkFont(size=14)
        )
        back_button.pack()
    def _open_modify_save_data_tool(self):
        logging.info("Modify Save Data definition called")
        self._clear_window()
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        add_item_button = self._create_sound_button(main_frame, "Add Item to Inventory By ID", self._open_add_item_by_id_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        add_item_button.pack(pady=10)
        back_button = self._create_sound_button(
            main_frame,
            "Back",
            lambda: [self._clear_window(), self._open_dev_tools()],
            width=200,
            height=40
        )
        back_button.pack(pady=10)
    def _open_dev_tools(self):
        logging.info("Developer Tools definition called")
        self._clear_window()
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        title_label = customtkinter.CTkLabel(main_frame, text="Developer Tools", font=customtkinter.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=20)
        modify_data = self._create_sound_button(main_frame, "Modify Data", self._open_modify_save_data_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        modify_data.pack(pady=10)
        back_button = self._create_sound_button(
            main_frame,
            "Back",
            lambda: [self._clear_window(), self._build_main_menu()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=10)
    def _open_dm_tools(self):
        logging.info("DM Tools definition called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="DM Tools", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        # Create scrollable frame for buttons
        scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        encounter_roll_button = self._create_sound_button(scroll_frame, "Encounter Roll", self._open_encounter_roll_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        encounter_roll_button.pack(pady=10)
        
        enemy_loot_button = self._create_sound_button(scroll_frame, "Individual Enemy Loot", self._open_enemy_loot_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        enemy_loot_button.pack(pady=10)
        
        create_lootcrate_button = self._create_sound_button(scroll_frame, "Create Loot Crate", self._open_create_lootcrate_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        create_lootcrate_button.pack(pady=10)
        
        create_item_transfer_button = self._create_sound_button(scroll_frame, "Create Item Transfer", self._open_create_item_transfer_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        create_item_transfer_button.pack(pady=10)
        
        create_magazine_transfer_button = self._create_sound_button(scroll_frame, "Create Loaded Magazine Transfer", self._open_create_magazine_transfer_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        create_magazine_transfer_button.pack(pady=10)
        
        create_belt_transfer_button = self._create_sound_button(scroll_frame, "Create Belt Transfer", self._open_create_belt_transfer_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        create_belt_transfer_button.pack(pady=10)
        
        modify_settings_button = self._create_sound_button(scroll_frame, "Modify Settings", self._open_modify_settings_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        modify_settings_button.pack(pady=10)
        
        back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda: [self._clear_window(), self._build_main_menu()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        back_button.pack(pady=20)
    
    def _open_encounter_roll_tool(self):
        """Roll for random encounter and generate enemy loot."""
        logging.info("Encounter Roll tool called")
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table file found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Load DM settings for enabled enemies
        dm_settings_path = os.path.join(saves_folder, "dm_settings.sldsv")
        enabled_enemies = {}
        
        if os.path.exists(dm_settings_path):
            try:
                with open(dm_settings_path, 'r') as f:
                    dm_settings = json.load(f)
                    enabled_enemies = dm_settings.get("enabled_enemies", {})
            except Exception as e:
                logging.warning(f"Failed to load DM settings: {e}")
        
        # Get enemy list
        enemy_list = table_data.get("tables", {}).get("enemy_drops", [])
        
        # Filter by enabled status (default to enabled if not specified)
        available_enemies = [
            enemy for enemy in enemy_list
            if enabled_enemies.get(enemy.get("name"), True)
        ]
        
        if not available_enemies:
            self._popup_show_info("Error", "No enabled enemies in table.", sound="error")
            return
        
        self._clear_window()
        self._play_ui_sound("whoosh1")
        
        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="Encounter Roll",
            font=customtkinter.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)
        
        # Difficulty explanation
        info_frame = customtkinter.CTkFrame(main_frame)
        info_frame.pack(fill="x", pady=10)
        
        info_text = """Encounter Difficulty Ranges:
        1 = Miniboss
        2-5 = Hard
        6-10 = Medium
        11-14 = Easy
        15-20 = None/Friendly (50/50)"""
        
        customtkinter.CTkLabel(
            info_frame,
            text=info_text,
            font=customtkinter.CTkFont(size=12),
            justify="left"
        ).pack(padx=20, pady=10)
        
        # Roll button
        result_label = customtkinter.CTkLabel(
            main_frame,
            text="",
            font=customtkinter.CTkFont(size=14),
            wraplength=600
        )
        result_label.pack(pady=20)
        
        def perform_roll():
            roll = random.randint(1, 20)
            
            # Determine difficulty
            if roll == 1:
                difficulty = "Miniboss"
            elif 2 <= roll <= 5:
                difficulty = "Hard"
            elif 6 <= roll <= 10:
                difficulty = "Medium"
            elif 11 <= roll <= 14:
                difficulty = "Easy"
            else:  # 15-20
                # 50/50 None or Friendly
                is_friendly = random.choice([True, False])
                difficulty = "Friendly" if is_friendly else "None"
            
            result_text = f"Roll: {roll}\nDifficulty: {difficulty}\n\n"
            
            if difficulty in ["None", "Friendly"]:
                result_text += "No hostile encounter!" if difficulty == "None" else "Friendly encounter!"
                result_label.configure(text=result_text)
                return
            
            # Find enemies matching difficulty
            matching_enemies = [e for e in available_enemies if e.get("difficulty", "").lower() == difficulty.lower()]
            
            if not matching_enemies:
                result_text += f"No enemies found for difficulty: {difficulty}"
                result_label.configure(text=result_text)
                return
            
            # Select random enemy
            selected_enemy = random.choice(matching_enemies)
            result_text += f"Enemy: {selected_enemy.get('name', 'Unknown')}\n\n"
            
            # Generate loot
            loot = self._generate_enemy_loot(selected_enemy, table_data)
            
            result_text += "Generated Loot:\n"
            for item in loot:
                result_text += f"- {item.get('name', 'Unknown Item')}"
                if item.get("quantity", 1) > 1:
                    result_text += f" x{item['quantity']}"
                result_text += "\n"
            
            result_label.configure(text=result_text)
            
            # Offer to save as enemy loot transfer
            def save_loot():
                self._save_enemy_loot_transfer(selected_enemy.get("name"), loot)
            
            save_button = self._create_sound_button(
                main_frame,
                text="Save as Enemy Loot Transfer",
                command=save_loot,
                width=300
            )
            save_button.pack(pady=10)
        
        self._create_sound_button(
            main_frame,
            text="Roll for Encounter",
            command=perform_roll,
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=16)
        ).pack(pady=10)
        
        back_button = self._create_sound_button(
            main_frame,
            text="Back to DM Tools",
            command=lambda: [self._clear_window(), self._open_dm_tools()],
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=20)
    
    def _open_enemy_loot_tool(self):
        """Generate loot for a specific enemy type."""
        logging.info("Individual Enemy Loot tool called")
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table file found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Load DM settings for enabled enemies
        dm_settings_path = os.path.join(saves_folder, "dm_settings.sldsv")
        enabled_enemies = {}
        
        if os.path.exists(dm_settings_path):
            try:
                with open(dm_settings_path, 'r') as f:
                    dm_settings = json.load(f)
                    enabled_enemies = dm_settings.get("enabled_enemies", {})
            except Exception as e:
                logging.warning(f"Failed to load DM settings: {e}")
        
        # Get enemy list
        enemy_list = table_data.get("tables", {}).get("enemy_drops", [])
        
        # Filter by enabled status
        available_enemies = [
            enemy for enemy in enemy_list
            if enabled_enemies.get(enemy.get("name"), True)
        ]
        
        if not available_enemies:
            self._popup_show_info("Error", "No enabled enemies in table.", sound="error")
            return
        
        self._clear_window()
        self._play_ui_sound("whoosh1")
        
        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="Individual Enemy Loot",
            font=customtkinter.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)
        
        customtkinter.CTkLabel(
            main_frame,
            text="Select an enemy to generate loot:",
            font=customtkinter.CTkFont(size=14)
        ).pack(pady=10)
        
        # List available enemies
        for enemy in available_enemies:
            enemy_frame = customtkinter.CTkFrame(main_frame)
            enemy_frame.pack(fill="x", pady=5, padx=20)
            
            enemy_info = f"{enemy.get('name', 'Unknown')} - {enemy.get('difficulty', 'Unknown')} Difficulty"
            
            customtkinter.CTkLabel(
                enemy_frame,
                text=enemy_info,
                font=customtkinter.CTkFont(size=12)
            ).pack(side="left", padx=10, pady=10)
            
            def generate_loot(e=enemy):
                self._show_enemy_loot_result(e, table_data)
            
            self._create_sound_button(
                enemy_frame,
                text="Generate Loot",
                command=generate_loot,
                width=150
            ).pack(side="right", padx=10, pady=5)
        
        back_button = self._create_sound_button(
            main_frame,
            text="Back to DM Tools",
            command=lambda: [self._clear_window(), self._open_dm_tools()],
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=20)
    
    def _show_enemy_loot_result(self, enemy, table_data):
        """Show generated loot for an enemy."""
        loot = self._generate_enemy_loot(enemy, table_data)
        
        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title(f"Loot: {enemy.get('name', 'Unknown')}")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        customtkinter.CTkLabel(
            dialog,
            text=f"Generated Loot for {enemy.get('name', 'Unknown')}",
            font=customtkinter.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        scroll_frame = customtkinter.CTkScrollableFrame(dialog)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        if not loot:
            customtkinter.CTkLabel(
                scroll_frame,
                text="No loot generated",
                font=customtkinter.CTkFont(size=12)
            ).pack(pady=20)
        else:
            for item in loot:
                item_text = item.get('name', 'Unknown Item')
                if item.get("quantity", 1) > 1:
                    item_text += f" x{item['quantity']}"
                
                customtkinter.CTkLabel(
                    scroll_frame,
                    text=f"• {item_text}",
                    font=customtkinter.CTkFont(size=12)
                ).pack(anchor="w", padx=10, pady=2)
        
        # Save button
        def save_loot():
            self._save_enemy_loot_transfer(enemy.get("name"), loot)
            dialog.destroy()
        
        self._create_sound_button(
            dialog,
            text="Save as Enemy Loot Transfer",
            command=save_loot,
            width=250
        ).pack(pady=10)
        
        self._create_sound_button(
            dialog,
            text="Close",
            command=dialog.destroy,
            fg_color="#8B0000",
            width=250
        ).pack(pady=10)
    
    def _generate_enemy_loot(self, enemy, table_data):
        """Generate loot items for an enemy."""
        loot = []
        
        for loot_entry in enemy.get("items", []):
            # Check if guaranteed or roll for rarity
            if loot_entry.get("guaranteed"):
                should_drop = True
            else:
                # Use rarity system to determine if item drops
                rarity = loot_entry.get("rarity", "Common")
                rarity_weights = table_data.get("rarity_weights", {})
                drop_chance = rarity_weights.get(rarity, 50) / 100.0
                should_drop = random.random() < drop_chance
            
            if should_drop:
                item = self._resolve_loot_entry(loot_entry, table_data)
                if item:
                    loot.append(item)
        
        return loot
    
    def _save_enemy_loot_transfer(self, enemy_name, loot_items):
        """Save enemy loot as a transfer file."""
        try:
            # Create transfer data
            transfer_data = {
                "type": "enemyloot",
                "enemy_name": enemy_name,
                "items": loot_items,
                "timestamp": datetime.now().isoformat()
            }
            
            # Generate filename
            safe_name = enemy_name.replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"enemyloot_{safe_name}_{timestamp}.sldenlt"
            filepath = os.path.join("enemyloot", filename)
            
            # Ensure directory exists
            os.makedirs("enemyloot", exist_ok=True)
            
            # Save as base85 encoded pickle
            with open(filepath, 'wb') as f:
                pickled = pickle.dumps(transfer_data)
                encoded = base64.b85encode(pickled)
                f.write(encoded)
            
            logging.info(f"Saved enemy loot transfer: {filepath}")
            self._popup_show_info("Success", f"Enemy loot saved as:\n{filename}", sound="success")
            
        except Exception as e:
            logging.error(f"Failed to save enemy loot transfer: {e}")
            self._popup_show_info("Error", f"Failed to save: {e}", sound="error")
    
    def _open_create_lootcrate_tool(self):
        logging.info("Create Loot Crate tool called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="Create Lootcrate", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        # Two main buttons
        create_scratch_btn = self._create_sound_button(main_frame, "Create from Scratch", self._open_create_lootcrate_from_scratch, width=800, height=60, font=customtkinter.CTkFont(size=16))
        create_scratch_btn.pack(pady=10, padx=20)
        
        create_preset_btn = self._create_sound_button(main_frame, "Create from Preset", self._open_create_lootcrate_from_preset, width=800, height=60, font=customtkinter.CTkFont(size=16))
        create_preset_btn.pack(pady=10, padx=20)
        
        back_button = self._create_sound_button(main_frame, "Back to DM Tools", lambda: [self._clear_window(), self._open_dm_tools()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        back_button.pack(pady=20)
    
    def _open_create_lootcrate_from_preset(self):
        logging.info("Create Loot Crate from Preset called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkScrollableFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="Create Lootcrate from Preset", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table files found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load tables for loot crate creator: {e}")
            self._popup_show_info("Error", f"Failed to load tables: {e}", sound="error")
            return
        
        def generate_crate_from_preset(crate):
            """Generate a single-use .sldlct from preset"""
            try:
                crate_copy = json.loads(json.dumps(crate))
                crate_copy.pop("_source_file", None)
                crate_copy.pop("_file_path", None)
                crate_copy["generated_at"] = datetime.now().isoformat()
                os.makedirs("lootcrates", exist_ok=True)
                filename = os.path.join(
                    "lootcrates",
                    f"lootcrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['lootcrate_extension']}"
                )
                pickled_data = pickle.dumps(crate_copy)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                with open(filename, 'w') as f:
                    f.write(encoded_data)
                self._popup_show_info("Success", f"Generated loot crate '{crate.get('name', 'Loot Crate')}'.", sound="success")
                logging.info(f"Generated loot crate file: {filename}")
            except Exception as e:
                logging.error(f"Failed to generate loot crate: {e}")
                self._popup_show_info("Error", f"Failed to generate loot crate: {e}", sound="error")
        
        def render_preset(crate, parent_frame):
            """Render a single preset crate with create button"""
            row = customtkinter.CTkFrame(parent_frame)
            row.pack(fill="x", padx=5, pady=4)
            row.grid_columnconfigure(0, weight=1)
            
            name = crate.get("name", "Loot Crate")
            desc = crate.get("description", "")
            
            title = customtkinter.CTkLabel(row, text=name, font=customtkinter.CTkFont(size=14, weight="bold"), anchor="w")
            title.grid(row=0, column=0, sticky="w", padx=4, pady=(2, 0))
            
            if desc:
                desc_label = customtkinter.CTkLabel(row, text=desc, font=customtkinter.CTkFont(size=11), text_color="gray", justify="left", anchor="w", wraplength=600)
                desc_label.grid(row=1, column=0, sticky="w", padx=4, pady=(0, 2))
            
            preview = self._get_loot_crate_contents_preview(crate, table_data)
            if preview:
                preview_label = customtkinter.CTkLabel(row, text=preview, font=customtkinter.CTkFont(size=10), text_color="orange", justify="left", anchor="w", wraplength=600)
                preview_label.grid(row=2, column=0, sticky="w", padx=4, pady=(0, 4))
            
            create_btn = self._create_sound_button(row, "Create", lambda c=crate: generate_crate_from_preset(c), width=130, height=35, font=customtkinter.CTkFont(size=12))
            create_btn.grid(row=0, column=1, rowspan=3, sticky="e", padx=10, pady=6)
        
        # Load presets from table's lootcrates table
        presets_from_table = table_data.get("tables", {}).get("lootcrates", [])
        
        # Load presets from folder
        os.makedirs(os.path.join("lootcrates", "presets"), exist_ok=True)
        preset_files = glob.glob(os.path.join("lootcrates", "presets", f"*{global_variables['lootcrate_extension']}"))
        presets_from_folder = []
        for pf in preset_files:
            try:
                with open(pf, 'r') as f:
                    encoded_data = f.read()
                pickled_data = base64.b85decode(encoded_data.encode('utf-8'))
                pdata = pickle.loads(pickled_data)
                pdata["_source_file"] = pf
                presets_from_folder.append(pdata)
            except Exception as e:
                logging.warning(f"Failed to load preset file {pf}: {e}")
        
        # Display all presets
        all_presets = presets_from_table + presets_from_folder
        if all_presets:
            for crate in all_presets:
                render_preset(crate, main_frame)
        else:
            no_presets_label = customtkinter.CTkLabel(main_frame, text="No presets available.", font=customtkinter.CTkFont(size=14), text_color="gray")
            no_presets_label.pack(pady=20)
        
        # Back button
        back_button = self._create_sound_button(main_frame, "Back", self._open_create_lootcrate_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        back_button.pack(pady=20)
    
    def _open_create_lootcrate_from_scratch(self):
        logging.info("Create Loot Crate from Scratch called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkScrollableFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="Create Lootcrate from Scratch", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table files found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load tables for loot crate creator: {e}")
            self._popup_show_info("Error", f"Failed to load tables: {e}", sound="error")
            return
        
        def save_preset_to_folder(crate):
            """Save preset to lootcrates/presets/ for reuse"""
            try:
                crate_copy = json.loads(json.dumps(crate))
                crate_copy.pop("_source_file", None)
                crate_copy.pop("_file_path", None)
                crate_copy["created_at"] = datetime.now().isoformat()
                os.makedirs(os.path.join("lootcrates", "presets"), exist_ok=True)
                filename = os.path.join(
                    "lootcrates", "presets",
                    f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['lootcrate_extension']}"
                )
                pickled_data = pickle.dumps(crate_copy)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                with open(filename, 'w') as f:
                    f.write(encoded_data)
                self._popup_show_info("Success", f"Saved preset '{crate.get('name', 'Loot Crate')}' to presets folder.", sound="success")
                logging.info(f"Saved preset loot crate to {filename}")
            except Exception as e:
                logging.error(f"Failed to save preset loot crate: {e}")
                self._popup_show_info("Error", f"Failed to save preset loot crate: {e}", sound="error")
        
        # Metadata inputs
        meta_frame = customtkinter.CTkFrame(main_frame)
        meta_frame.pack(fill="x", padx=20, pady=10)
        meta_frame.grid_columnconfigure(1, weight=1)
        
        name_label = customtkinter.CTkLabel(meta_frame, text="Lootcrate Name:")
        name_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        name_entry = customtkinter.CTkEntry(meta_frame, placeholder_text="")
        name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        desc_label = customtkinter.CTkLabel(meta_frame, text="Description:")
        desc_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
        desc_text = customtkinter.CTkEntry(meta_frame, placeholder_text="")
        desc_text.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        locked_var = customtkinter.BooleanVar(value=False)
        locked_check = customtkinter.CTkCheckBox(meta_frame, text="This lootcrate requires lockpicking", variable=locked_var)
        locked_check.grid(row=2, column=0, columnspan=2, padx=5, pady=10, sticky="w")
        
        # Number of pulls section
        pulls_frame = customtkinter.CTkFrame(meta_frame)
        pulls_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        
        pulls_label = customtkinter.CTkLabel(pulls_frame, text="Number of Pulls:")
        pulls_label.pack(side="left", padx=5)
        
        pulls_type_var = customtkinter.StringVar(value="Fixed")
        fixed_radio = customtkinter.CTkRadioButton(pulls_frame, text="Fixed", variable=pulls_type_var, value="Fixed")
        fixed_radio.pack(side="left", padx=10)
        range_radio = customtkinter.CTkRadioButton(pulls_frame, text="Range", variable=pulls_type_var, value="Range")
        range_radio.pack(side="left", padx=10)
        
        pulls_entry_label = customtkinter.CTkLabel(pulls_frame, text="Pulls:")
        pulls_entry_label.pack(side="left", padx=5)
        pulls_entry = customtkinter.CTkEntry(pulls_frame, placeholder_text="3", width=60)
        pulls_entry.pack(side="left", padx=5)
        
        # Guaranteed items section
        guaranteed_label = customtkinter.CTkLabel(meta_frame, text="Guaranteed Items (IDs):")
        guaranteed_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        guaranteed_entry = customtkinter.CTkEntry(meta_frame, placeholder_text="e.g., 1,2,3")
        guaranteed_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        
        # ID Pool section
        id_pool_label = customtkinter.CTkLabel(meta_frame, text="ID Pool (Random Items):")
        id_pool_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
        id_pool_entry = customtkinter.CTkEntry(meta_frame, placeholder_text="e.g., 10,11,12")
        id_pool_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        
        # Table Pool section
        table_pool_label = customtkinter.CTkLabel(meta_frame, text="Table Pool:")
        table_pool_label.grid(row=6, column=0, padx=5, pady=5, sticky="nw")
        
        table_pool_frame = customtkinter.CTkScrollableFrame(meta_frame, height=150)
        table_pool_frame.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        
        table_selections = {}
        for table_name in table_data.get("tables", {}).keys():
            if table_name != "lootcrates":
                row_frame = customtkinter.CTkFrame(table_pool_frame)
                row_frame.pack(fill="x", padx=5, pady=2)
                
                var = customtkinter.BooleanVar(value=False)
                check = customtkinter.CTkCheckBox(row_frame, text=table_name, variable=var)
                check.pack(side="left", padx=5)
                
                chance_label = customtkinter.CTkLabel(row_frame, text="Chance %:")
                chance_label.pack(side="left", padx=5)
                chance_entry = customtkinter.CTkEntry(row_frame, placeholder_text="50", width=60)
                chance_entry.pack(side="left", padx=5)
                
                table_selections[table_name] = {"var": var, "chance": chance_entry}
        
        def save_custom_crate():
            """Generate single-use crate from custom builder"""
            try:
                crate_name = name_entry.get().strip()
                if not crate_name:
                    self._popup_show_info("Error", "Please enter a crate name.", sound="error")
                    return
                
                crate_desc = desc_text.get().strip()
                locked = locked_var.get()
                pulls_type = pulls_type_var.get()
                pulls_value = pulls_entry.get().strip()
                
                # Parse pulls
                pulls = None
                if pulls_type == "Fixed":
                    try:
                        pulls = int(pulls_value) if pulls_value else 3
                    except ValueError:
                        self._popup_show_info("Error", "Pulls must be a number.", sound="error")
                        return
                else:  # Range
                    if "-" in pulls_value or "," in pulls_value:
                        parts = pulls_value.replace("-", ",").split(",")
                        try:
                            pulls = {"min": int(parts[0]), "max": int(parts[1])}
                        except (ValueError, IndexError):
                            self._popup_show_info("Error", "Range must be in format: min,max or min-max", sound="error")
                            return
                    else:
                        self._popup_show_info("Error", "Range must be in format: min,max or min-max", sound="error")
                        return
                
                # Parse guaranteed items
                guaranteed_items = []
                guaranteed_text = guaranteed_entry.get().strip()
                if guaranteed_text:
                    try:
                        guaranteed_items = [int(x.strip()) for x in guaranteed_text.split(",") if x.strip()]
                    except ValueError:
                        self._popup_show_info("Error", "Guaranteed items must be comma-separated IDs.", sound="error")
                        return
                
                # Parse ID pool
                id_pool = []
                id_pool_text = id_pool_entry.get().strip()
                if id_pool_text:
                    try:
                        id_pool = [int(x.strip()) for x in id_pool_text.split(",") if x.strip()]
                    except ValueError:
                        self._popup_show_info("Error", "ID pool must be comma-separated IDs.", sound="error")
                        return
                
                # Parse table pool
                table_pool = []
                for table_name, selection in table_selections.items():
                    if selection["var"].get():
                        chance_text = selection["chance"].get().strip()
                        try:
                            chance = int(chance_text) if chance_text else 50
                            table_pool.append({"table": table_name, "chance": chance})
                        except ValueError:
                            self._popup_show_info("Error", f"Chance for {table_name} must be a number.", sound="error")
                            return
                
                # Build loot_table entries
                loot_entries = []
                for item_id in guaranteed_items:
                    loot_entries.append({"type": "item", "id": item_id})
                
                crate_data = {
                    "name": crate_name,
                    "description": crate_desc,
                    "locked": locked,
                    "pulls": pulls,
                    "loot_table": loot_entries,
                    "id_pool": id_pool if id_pool else None,
                    "table_pool": table_pool if table_pool else None,
                    "created_at": datetime.now().isoformat(),
                    "dm_created": True
                }
                
                os.makedirs("lootcrates", exist_ok=True)
                filename = os.path.join("lootcrates", f"lootcrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['lootcrate_extension']}")
                pickled_data = pickle.dumps(crate_data)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                with open(filename, 'w') as f:
                    f.write(encoded_data)
                self._popup_show_info("Success", f"Generated loot crate '{crate_name}'.", sound="success")
                logging.info(f"Generated loot crate file: {filename}")
            except Exception as e:
                logging.error(f"Failed to generate crate: {e}")
                self._popup_show_info("Error", f"Failed to generate crate: {e}", sound="error")
        
        # Action buttons
        action_frame = customtkinter.CTkFrame(main_frame)
        action_frame.pack(fill="x", padx=20, pady=20)
        
        save_btn = self._create_sound_button(action_frame, "Save Lootcrate", save_custom_crate, width=200, height=50, font=customtkinter.CTkFont(size=14))
        save_btn.pack(side="left", padx=5)
        
        cancel_btn = self._create_sound_button(action_frame, "Cancel", self._open_create_lootcrate_tool, width=200, height=50, font=customtkinter.CTkFont(size=14))
        cancel_btn.pack(side="left", padx=5)
    
    def _open_create_item_transfer_tool(self):
        logging.info("Create Item Transfer tool called")
        self._clear_window()
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        title_label = customtkinter.CTkLabel(main_frame, text="Create Item Transfer", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        
        # Money input
        money_frame = customtkinter.CTkFrame(main_frame)
        money_frame.pack(fill="x", padx=20, pady=10)
        money_label = customtkinter.CTkLabel(money_frame, text="Money Amount:")
        money_label.pack(side="left", padx=5, pady=5)
        money_entry = customtkinter.CTkEntry(money_frame, placeholder_text="0", width=160)
        money_entry.pack(side="left", padx=5, pady=5)
        
        # Load table items
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table files found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load tables for item transfer: {e}")
            self._popup_show_info("Error", f"Failed to load tables: {e}", sound="error")
            return
        
        all_items = []
        for table_name, items in table_data.get("tables", {}).items():
            for item in items:
                item_copy = item.copy()
                item_copy["table_category"] = table_name
                all_items.append(item_copy)
        
        items_frame = customtkinter.CTkFrame(main_frame)
        items_frame.pack(fill="both", expand=True, padx=20, pady=10)
        items_label = customtkinter.CTkLabel(items_frame, text="Select items to include in the transfer:", font=customtkinter.CTkFont(size=14, weight="bold"))
        items_label.pack(pady=5)
        items_scroll = customtkinter.CTkScrollableFrame(items_frame, width=700, height=300)
        items_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        selected_indices = []
        for idx, item in enumerate(all_items):
            row = customtkinter.CTkFrame(items_scroll)
            row.pack(fill="x", padx=5, pady=2)
            var = customtkinter.BooleanVar(value=False)
            def on_toggle(i=idx, v=var):
                if v.get():
                    if i not in selected_indices:
                        selected_indices.append(i)
                else:
                    if i in selected_indices:
                        selected_indices.remove(i)
            checkbox = customtkinter.CTkCheckBox(
                row,
                text=f"ID {item.get('id', '?')}: {item.get('name', 'Unknown')} (Table: {item.get('table_category', 'N/A')}, Rarity: {item.get('rarity', 'N/A')})",
                variable=var,
                command=on_toggle
            )
            checkbox.pack(side="left", padx=5, pady=4)
        
        def save_transfer():
            try:
                transfer_money = int(money_entry.get() or 0)
            except ValueError:
                self._popup_show_info("Error", "Money amount must be a number.", sound="error")
                return
            try:
                if not selected_indices and transfer_money == 0:
                    self._popup_show_info("Error", "Add money or select at least one item.", sound="error")
                    return
                items_to_send = []
                for idx in selected_indices:
                    if 0 <= idx < len(all_items):
                        itm = {k: v for k, v in all_items[idx].items() if k != "table_category"}
                        itm = add_subslots_to_item(itm)
                        items_to_send.append(itm)
                transfer_data = {
                    "money": transfer_money,
                    "items": items_to_send,
                    "timestamp": datetime.now().isoformat(),
                    "from_character": "DM"
                }
                pickled_data = pickle.dumps(transfer_data)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                os.makedirs("transfers", exist_ok=True)
                filename = os.path.join("transfers", f"transfer_dm_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['transfer_extension']}")
                with open(filename, 'w') as f:
                    f.write(encoded_data)
                self._popup_show_info("Success", f"Saved transfer with ${transfer_money} and {len(items_to_send)} items.", sound="success")
                logging.info(f"Saved DM transfer to {filename}")
                self._open_dm_tools()
            except Exception as e:
                logging.error(f"Failed to save item transfer: {e}")
                self._popup_show_info("Error", f"Failed to save item transfer: {e}", sound="error")
        
        save_button = self._create_sound_button(main_frame, "Save Transfer", save_transfer, width=500, height=50, font=customtkinter.CTkFont(size=16))
        save_button.pack(pady=10)
        
        back_button = self._create_sound_button(main_frame, "Back to DM Tools", lambda: [self._clear_window(), self._open_dm_tools()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        back_button.pack(pady=10)
    
    def _open_create_magazine_transfer_tool(self):
        """Create loaded magazine transfers for players."""
        logging.info("Create Loaded Magazine Transfer tool called")
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table file found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Get all magazines from table
        magazines = table_data.get("tables", {}).get("magazines", [])
        
        if not magazines:
            self._popup_show_info("Error", "No magazines found in table.", sound="error")
            return
        
        self._clear_window()
        self._play_ui_sound("whoosh1")
        
        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="Create Loaded Magazine Transfer",
            font=customtkinter.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)
        
        customtkinter.CTkLabel(
            main_frame,
            text="Select a magazine type to create:",
            font=customtkinter.CTkFont(size=14)
        ).pack(pady=10)
        
        # List magazines
        for mag in magazines:
            mag_frame = customtkinter.CTkFrame(main_frame)
            mag_frame.pack(fill="x", pady=5, padx=20)
            
            mag_info = f"{mag.get('name', 'Unknown')}\n"
            mag_info += f"Caliber: {', '.join(mag.get('caliber', ['Unknown']))}\n"
            mag_info += f"Capacity: {mag.get('capacity', 0)}"
            
            if mag.get("magazinesystem"):
                mag_info += f" | System: {mag.get('magazinesystem')}"
            
            customtkinter.CTkLabel(
                mag_frame,
                text=mag_info,
                font=customtkinter.CTkFont(size=12),
                justify="left"
            ).pack(side="left", padx=10, pady=10)
            
            def create_mag_transfer(m=mag):
                self._create_loaded_magazine_dialog(m, table_data)
            
            self._create_sound_button(
                mag_frame,
                text="Create Transfer",
                command=create_mag_transfer,
                width=150
            ).pack(side="right", padx=10, pady=5)
        
        back_button = self._create_sound_button(
            main_frame,
            text="Back to DM Tools",
            command=lambda: [self._clear_window(), self._open_dm_tools()],
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=20)
    
    def _create_loaded_magazine_dialog(self, magazine, table_data):
        """Dialog to configure and create loaded magazine transfer."""
        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title(f"Create: {magazine.get('name', 'Magazine')}")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        try:
            dialog.wait_visibility()
            dialog.grab_set()
        except Exception as e:
            logging.warning("Dialog grab_set failed: %s", e)
        
        customtkinter.CTkLabel(
            dialog,
            text=f"Configure {magazine.get('name', 'Magazine')}",
            font=customtkinter.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Quantity
        quantity_frame = customtkinter.CTkFrame(dialog)
        quantity_frame.pack(fill="x", padx=20, pady=10)
        
        customtkinter.CTkLabel(
            quantity_frame,
            text="Number of magazines:",
            font=customtkinter.CTkFont(size=12)
        ).pack(side="left", padx=10)
        
        quantity_var = customtkinter.StringVar(value="1")
        quantity_entry = customtkinter.CTkEntry(quantity_frame, textvariable=quantity_var, width=100)
        quantity_entry.pack(side="right", padx=10)
        
        # Ammo selection
        customtkinter.CTkLabel(
            dialog,
            text="Select ammunition type:",
            font=customtkinter.CTkFont(size=14, weight="bold")
        ).pack(pady=10)
        
        # Get compatible ammunition
        mag_calibers = magazine.get("caliber", [])
        ammunition_table = table_data.get("tables", {}).get("ammunition", [])
        
        compatible_ammo = [
            ammo for ammo in ammunition_table
            if ammo.get("caliber") in mag_calibers
        ]
        
        if not compatible_ammo:
            customtkinter.CTkLabel(
                dialog,
                text="No compatible ammunition found!",
                font=customtkinter.CTkFont(size=12),
                text_color="red"
            ).pack(pady=20)
            
            self._create_sound_button(
                dialog,
                text="Close",
                command=dialog.destroy,
                fg_color="#8B0000"
            ).pack(pady=10)
            return
        
        selected_ammo = customtkinter.StringVar(value=compatible_ammo[0].get("name", ""))
        selected_variant = customtkinter.StringVar(value="")
        
        ammo_scroll = customtkinter.CTkScrollableFrame(dialog, height=200)
        ammo_scroll.pack(fill="x", padx=20, pady=10)
        
        for ammo in compatible_ammo:
            ammo_frame = customtkinter.CTkFrame(ammo_scroll)
            ammo_frame.pack(fill="x", pady=2)
            
            radio = customtkinter.CTkRadioButton(
                ammo_frame,
                text=ammo.get("name", "Unknown"),
                variable=selected_ammo,
                value=ammo.get("name", ""),
                font=customtkinter.CTkFont(size=12)
            )
            radio.pack(anchor="w", padx=10, pady=5)
            
            # Show variants if available
            if ammo.get("variants"):
                variant_frame = customtkinter.CTkFrame(ammo_frame)
                variant_frame.pack(fill="x", padx=30)
                
                for variant in ammo["variants"]:
                    var_radio = customtkinter.CTkRadioButton(
                        variant_frame,
                        text=variant.get("name", "Unknown Variant"),
                        variable=selected_variant,
                        value=f"{ammo.get('name')}|{variant.get('name')}",
                        font=customtkinter.CTkFont(size=11)
                    )
                    var_radio.pack(anchor="w", padx=10, pady=2)
        
        # Fill level
        fill_frame = customtkinter.CTkFrame(dialog)
        fill_frame.pack(fill="x", padx=20, pady=10)
        
        customtkinter.CTkLabel(
            fill_frame,
            text="Fill level (% of capacity):",
            font=customtkinter.CTkFont(size=12)
        ).pack(side="left", padx=10)
        
        fill_var = customtkinter.StringVar(value="100")
        fill_entry = customtkinter.CTkEntry(fill_frame, textvariable=fill_var, width=100)
        fill_entry.pack(side="right", padx=10)
        
        # Create button
        def create_transfer():
            try:
                qty = int(quantity_var.get())
                fill_percent = int(fill_var.get())
                
                if qty <= 0 or fill_percent < 0 or fill_percent > 100:
                    raise ValueError("Invalid quantity or fill percentage")
                
                # Find selected ammo
                ammo_obj = None
                for ammo in compatible_ammo:
                    if ammo.get("name") == selected_ammo.get():
                        ammo_obj = ammo
                        break
                
                if not ammo_obj:
                    raise ValueError("No ammunition selected")
                
                # Create loaded magazines
                magazines = []
                capacity = magazine.get("capacity", 30)
                rounds_to_load = int(capacity * (fill_percent / 100.0))
                
                for i in range(qty):
                    mag_copy = json.loads(json.dumps(magazine))
                    mag_copy["rounds"] = []
                    
                    # Ensure magazinesystem is preserved
                    if not mag_copy.get("magazinesystem"):
                        mag_copy["magazinesystem"] = magazine.get("magazinesystem", "Unknown")
                    
                    # Load rounds - use simple string format: "caliber | variant"
                    for j in range(rounds_to_load):
                        round_str = ammo_obj.get("caliber", "Unknown")
                        
                        # Add variant if selected
                        if selected_variant.get():
                            variant_parts = selected_variant.get().split("|")
                            if len(variant_parts) == 2:
                                round_str = f"{round_str} | {variant_parts[1]}"
                        
                        mag_copy["rounds"].append(round_str)
                    
                    magazines.append(mag_copy)
                
                # Save as transfer
                self._save_magazine_transfer(magazines)
                dialog.destroy()
                
            except ValueError as e:
                self._popup_show_info("Error", f"Invalid input: {e}", sound="error")
        
        self._create_sound_button(
            dialog,
            text="Create Transfer",
            command=create_transfer,
            width=200
        ).pack(pady=10)
        
        self._create_sound_button(
            dialog,
            text="Cancel",
            command=dialog.destroy,
            fg_color="#8B0000",
            width=200
        ).pack(pady=5)
    
    def _save_magazine_transfer(self, magazines):
        """Save loaded magazines as transfer file."""
        try:
            transfer_data = {
                "type": "magazines",
                "items": magazines,
                "timestamp": datetime.now().isoformat()
            }
            
            # Generate filename
            mag_name = magazines[0].get("name", "magazine").replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mag_{mag_name}_{len(magazines)}x_{timestamp}.sldtrf"
            filepath = os.path.join("transfers", filename)
            
            # Ensure directory exists
            os.makedirs("transfers", exist_ok=True)
            
            # Save as base85 encoded pickle
            with open(filepath, 'wb') as f:
                pickled = pickle.dumps(transfer_data)
                encoded = base64.b85encode(pickled)
                f.write(encoded)
            
            logging.info(f"Saved magazine transfer: {filepath}")
            self._popup_show_info("Success", f"Magazine transfer saved as:\n{filename}", sound="success")
            
        except Exception as e:
            logging.error(f"Failed to save magazine transfer: {e}")
            self._popup_show_info("Error", f"Failed to save: {e}", sound="error")
    
    def _open_create_belt_transfer_tool(self):
        """Create loaded belt transfers for machine guns."""
        logging.info("Create Belt Transfer tool called")
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table file found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Get all belt links from magazines table
        magazines = table_data.get("tables", {}).get("magazines", [])
        belt_links = [mag for mag in magazines if mag.get("beltlink")]
        
        if not belt_links:
            self._popup_show_info("Error", "No belt links found in table.", sound="error")
            return
        
        self._clear_window()
        self._play_ui_sound("whoosh1")
        
        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="Create Loaded Belt Transfer",
            font=customtkinter.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)
        
        customtkinter.CTkLabel(
            main_frame,
            text="Select a belt link type to create:",
            font=customtkinter.CTkFont(size=14)
        ).pack(pady=10)
        
        # List belt links
        for belt in belt_links:
            belt_frame = customtkinter.CTkFrame(main_frame)
            belt_frame.pack(fill="x", pady=5, padx=20)
            
            belt_info = f"{belt.get('name', 'Unknown')}\n"
            belt_info += f"Caliber: {', '.join(belt.get('caliber', ['Unknown']))}\n"
            belt_info += f"Belt Link: {belt.get('beltlink')}"
            
            customtkinter.CTkLabel(
                belt_frame,
                text=belt_info,
                font=customtkinter.CTkFont(size=12),
                justify="left"
            ).pack(side="left", padx=10, pady=10)
            
            def create_belt_transfer(b=belt):
                self._create_loaded_belt_dialog(b, table_data)
            
            self._create_sound_button(
                belt_frame,
                text="Create Transfer",
                command=create_belt_transfer,
                width=150
            ).pack(side="right", padx=10, pady=5)
        
        back_button = self._create_sound_button(
            main_frame,
            text="Back to DM Tools",
            command=lambda: [self._clear_window(), self._open_dm_tools()],
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=20)
    
    def _create_loaded_belt_dialog(self, belt_link, table_data):
        """Dialog to configure and create loaded belt transfer."""
        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title(f"Create: {belt_link.get('name', 'Belt')}")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        customtkinter.CTkLabel(
            dialog,
            text=f"Configure {belt_link.get('name', 'Belt')}",
            font=customtkinter.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Round count
        count_frame = customtkinter.CTkFrame(dialog)
        count_frame.pack(fill="x", padx=20, pady=10)
        
        customtkinter.CTkLabel(
            count_frame,
            text="Number of rounds in belt:",
            font=customtkinter.CTkFont(size=12)
        ).pack(side="left", padx=10)
        
        count_var = customtkinter.StringVar(value="100")
        count_entry = customtkinter.CTkEntry(count_frame, textvariable=count_var, width=100)
        count_entry.pack(side="right", padx=10)
        
        # Ammo selection
        customtkinter.CTkLabel(
            dialog,
            text="Select ammunition type:",
            font=customtkinter.CTkFont(size=14, weight="bold")
        ).pack(pady=10)
        
        # Get compatible ammunition
        belt_calibers = belt_link.get("caliber", [])
        ammunition_table = table_data.get("tables", {}).get("ammunition", [])
        
        compatible_ammo = [
            ammo for ammo in ammunition_table
            if ammo.get("caliber") in belt_calibers
        ]
        
        if not compatible_ammo:
            customtkinter.CTkLabel(
                dialog,
                text="No compatible ammunition found!",
                font=customtkinter.CTkFont(size=12),
                text_color="red"
            ).pack(pady=20)
            
            self._create_sound_button(
                dialog,
                text="Close",
                command=dialog.destroy,
                fg_color="#8B0000"
            ).pack(pady=10)
            return
        
        selected_ammo = customtkinter.StringVar(value=compatible_ammo[0].get("name", ""))
        selected_variant = customtkinter.StringVar(value="")
        
        ammo_scroll = customtkinter.CTkScrollableFrame(dialog, height=250)
        ammo_scroll.pack(fill="x", padx=20, pady=10)
        
        for ammo in compatible_ammo:
            ammo_frame = customtkinter.CTkFrame(ammo_scroll)
            ammo_frame.pack(fill="x", pady=2)
            
            radio = customtkinter.CTkRadioButton(
                ammo_frame,
                text=ammo.get("name", "Unknown"),
                variable=selected_ammo,
                value=ammo.get("name", ""),
                font=customtkinter.CTkFont(size=12)
            )
            radio.pack(anchor="w", padx=10, pady=5)
            
            # Show variants if available
            if ammo.get("variants"):
                variant_frame = customtkinter.CTkFrame(ammo_frame)
                variant_frame.pack(fill="x", padx=30)
                
                for variant in ammo["variants"]:
                    var_radio = customtkinter.CTkRadioButton(
                        variant_frame,
                        text=variant.get("name", "Unknown Variant"),
                        variable=selected_variant,
                        value=f"{ammo.get('name')}|{variant.get('name')}",
                        font=customtkinter.CTkFont(size=11)
                    )
                    var_radio.pack(anchor="w", padx=10, pady=2)
        
        # Create button
        def create_transfer():
            try:
                round_count = int(count_var.get())
                
                if round_count <= 0:
                    raise ValueError("Invalid round count")
                
                # Find selected ammo
                ammo_obj = None
                for ammo in compatible_ammo:
                    if ammo.get("name") == selected_ammo.get():
                        ammo_obj = ammo
                        break
                
                if not ammo_obj:
                    raise ValueError("No ammunition selected")
                
                # Create loaded belt
                belt_copy = json.loads(json.dumps(belt_link))
                belt_copy["rounds"] = []
                
                # Load rounds
                for i in range(round_count):
                    round_data = {
                        "caliber": ammo_obj.get("caliber"),
                        "name": ammo_obj.get("name")
                    }
                    
                    # Add variant data if selected
                    if selected_variant.get():
                        variant_parts = selected_variant.get().split("|")
                        if len(variant_parts) == 2:
                            # Find variant details
                            for var in ammo_obj.get("variants", []):
                                if var.get("name") == variant_parts[1]:
                                    round_data["variant"] = var.get("name")
                                    round_data["variant_data"] = var
                                    break
                    
                    belt_copy["rounds"].append(round_data)
                
                # Save as transfer
                self._save_belt_transfer(belt_copy, round_count)
                dialog.destroy()
                
            except ValueError as e:
                self._popup_show_info("Error", f"Invalid input: {e}", sound="error")
        
        self._create_sound_button(
            dialog,
            text="Create Transfer",
            command=create_transfer,
            width=200
        ).pack(pady=10)
        
        self._create_sound_button(
            dialog,
            text="Cancel",
            command=dialog.destroy,
            fg_color="#8B0000",
            width=200
        ).pack(pady=5)
    
    def _save_belt_transfer(self, belt, round_count):
        """Save loaded belt as transfer file."""
        try:
            transfer_data = {
                "type": "belt",
                "items": [belt],
                "timestamp": datetime.now().isoformat()
            }
            
            # Generate filename
            belt_name = belt.get("beltlink", "belt").replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"belt_{belt_name}_{round_count}rds_{timestamp}.sldtrf"
            filepath = os.path.join("transfers", filename)
            
            # Ensure directory exists
            os.makedirs("transfers", exist_ok=True)
            
            # Save as base85 encoded pickle
            with open(filepath, 'wb') as f:
                pickled = pickle.dumps(transfer_data)
                encoded = base64.b85encode(pickled)
                f.write(encoded)
            
            logging.info(f"Saved belt transfer: {filepath}")
            self._popup_show_info("Success", f"Belt transfer saved as:\n{filename}", sound="success")
            
        except Exception as e:
            logging.error(f"Failed to save belt transfer: {e}")
            self._popup_show_info("Error", f"Failed to save: {e}", sound="error")
    
    def _open_modify_settings_tool(self):
        """Modify DM settings including enemy spawn toggles."""
        logging.info("Modify Settings tool called")
        
        # Load table data
        try:
            table_files = glob.glob(os.path.join("tables", "*.sldtbl"))
            if not table_files:
                self._popup_show_info("Error", "No table file found.", sound="error")
                return
            with open(table_files[0], 'r') as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound="error")
            return
        
        # Load DM settings
        dm_settings_path = os.path.join(saves_folder, "dm_settings.sldsv")
        dm_settings = {"enabled_enemies": {}}
        
        if os.path.exists(dm_settings_path):
            try:
                with open(dm_settings_path, 'r') as f:
                    dm_settings = json.load(f)
                    if "enabled_enemies" not in dm_settings:
                        dm_settings["enabled_enemies"] = {}
            except Exception as e:
                logging.warning(f"Failed to load DM settings: {e}")
        
        # Get enemy list
        enemy_list = table_data.get("tables", {}).get("enemy_drops", [])
        
        # Initialize enabled status for all enemies (default True)
        for enemy in enemy_list:
            enemy_name = enemy.get("name")
            if enemy_name and enemy_name not in dm_settings["enabled_enemies"]:
                dm_settings["enabled_enemies"][enemy_name] = True
        
        self._clear_window()
        self._play_ui_sound("whoosh1")
        
        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_label = customtkinter.CTkLabel(
            main_frame,
            text="DM Settings - Enemy Spawn Control",
            font=customtkinter.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)
        
        customtkinter.CTkLabel(
            main_frame,
            text="Toggle enemies on/off for encounter rolls and loot generation:",
            font=customtkinter.CTkFont(size=14)
        ).pack(pady=10)
        
        # Enemy toggles
        enemy_vars = {}
        
        for enemy in enemy_list:
            enemy_name = enemy.get("name", "Unknown")
            enemy_frame = customtkinter.CTkFrame(main_frame)
            enemy_frame.pack(fill="x", pady=5, padx=20)
            
            enemy_info = f"{enemy_name} - {enemy.get('difficulty', 'Unknown')} Difficulty"
            
            customtkinter.CTkLabel(
                enemy_frame,
                text=enemy_info,
                font=customtkinter.CTkFont(size=12)
            ).pack(side="left", padx=10, pady=10)
            
            # Toggle switch
            var = customtkinter.BooleanVar(value=dm_settings["enabled_enemies"].get(enemy_name, True))
            enemy_vars[enemy_name] = var
            
            toggle = customtkinter.CTkSwitch(
                enemy_frame,
                text="Enabled",
                variable=var,
                font=customtkinter.CTkFont(size=12)
            )
            toggle.pack(side="right", padx=10, pady=10)
        
        # Buttons frame
        buttons_frame = customtkinter.CTkFrame(main_frame)
        buttons_frame.pack(fill="x", pady=20, padx=20)
        
        def save_settings():
            """Save DM settings to file."""
            try:
                # Update settings with toggle values
                for enemy_name, var in enemy_vars.items():
                    dm_settings["enabled_enemies"][enemy_name] = var.get()
                
                # Save to file
                with open(dm_settings_path, 'w') as f:
                    json.dump(dm_settings, f, indent=4)
                
                logging.info(f"DM settings saved to {dm_settings_path}")
                self._popup_show_info("Success", "DM settings saved successfully!", sound="success")
                
            except Exception as e:
                logging.error(f"Failed to save DM settings: {e}")
                self._popup_show_info("Error", f"Failed to save settings: {e}", sound="error")
        
        def enable_all():
            """Enable all enemies."""
            for var in enemy_vars.values():
                var.set(True)
        
        def disable_all():
            """Disable all enemies."""
            for var in enemy_vars.values():
                var.set(False)
        
        # Save button
        self._create_sound_button(
            buttons_frame,
            text="Save Settings",
            command=save_settings,
            width=200
        ).pack(side="left", padx=10)
        
        # Enable all button
        self._create_sound_button(
            buttons_frame,
            text="Enable All",
            command=enable_all,
            width=150,
            fg_color="#006400"
        ).pack(side="left", padx=10)
        
        # Disable all button
        self._create_sound_button(
            buttons_frame,
            text="Disable All",
            command=disable_all,
            width=150,
            fg_color="#8B0000"
        ).pack(side="left", padx=10)
        
        # Back button
        back_button = self._create_sound_button(
            main_frame,
            text="Back to DM Tools",
            command=lambda: [self._clear_window(), self._open_dm_tools()],
            width=300,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        back_button.pack(pady=20)
if __name__ == "__main__":
    app = App()