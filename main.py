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
    logging.info(f"Random fact: {fact}")
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
logging.info(f"RAM: {round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024. ** 2), 2)} MB")
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

possible_flags = ["--dev", "--dm", "--debug", "--force"]

for flag in possible_flags:
    if flag in os.sys.argv:
        if flag == "--dev":
            global_variables["devmode"]["value"] = True
            logging.info("Development mode activated via command-line flag.")
        elif flag == "--dm":
            global_variables["dmmode"]["value"] = True
            logging.info("DM mode activated via command-line flag.")
        elif flag == "--debug":
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
        try:
            persistent_path = os.path.join(saves_folder, "persistent_data.sldsv")
            pickled_persistent = pickle.dumps(persistentdata)
            encoded_persistent = base64.b85encode(pickled_persistent).decode('utf-8')
            with open(persistent_path, 'w') as f:
                f.write(encoded_persistent)
            logging.info(f"Persistent data saved to {persistent_path}")
        except Exception as e:
            logging.error(f"Failed to save persistent data: {e}")
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
            return data
        except Exception as e:
            logging.error(f"Failed to load data from '{save_path}': {e}")
            return None
    def __init__(self):
        customtkinter.set_appearance_mode(appearance_settings["appearance_mode"])
        customtkinter.set_default_color_theme(appearance_settings["color_theme"])
        self.root = customtkinter.CTk()
        self.root.title("DOOM Tools")
        self.root.geometry(appearance_settings["resolution"])
        self.root.minsize(1280, 720)
        if appearance_settings["borderless"]:
            self.root.overrideredirect(True)
        self.root.attributes('-fullscreen', appearance_settings["fullscreen"])
        self._load_file(None)
        if persistentdata.get("last_loaded_save"):
            last_save_uuid = persistentdata["last_loaded_save"]
            last_save_name = persistentdata.get("save_uuids", {}).get(last_save_uuid)
            if last_save_name:
                # Normalize name to avoid double extensions
                if last_save_name.endswith(".sldsv"):
                    last_save_name = last_save_name.replace(".sldsv", "")
                save_filename = f"{last_save_name}_{last_save_uuid}.sldsv"
                loaded_data = self._load_file(save_filename)
                if loaded_data:
                    global currentsave
                    currentsave = save_filename
                    logging.info(f"Automatically loaded last save: {save_filename}")
                else:
                    logging.warning(f"Failed to load last save: {save_filename}")
            else:
                logging.warning(f"Last save UUID {last_save_uuid} not found in save_uuids") 
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
        button = customtkinter.CTkButton(
            parent, text=text, command=lambda: [self._play_ui_sound("click"), command()], **kwargs
        )
        def on_hover(e):
            if button.cget("state") != "disabled":
                self._play_ui_sound("hover")
        button.bind("<Enter>", on_hover)
        return button
    def _safe_sound_play(self, directory, sound_filename):
        sound_path = os.path.join("sounds", directory, sound_filename + ".ogg")
        if os.path.exists(sound_path):
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                logging.debug(f"Played sound: {sound_filename} from {directory}")
            except Exception as e:
                logging.warning(f"Failed to play sound '{sound_filename}' from {directory}: {e}")
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
        self._popup_show_info("Looting", "Looting is under development.")
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
        return_button = self._create_sound_button(self.root, "Return to Inventory Manager", lambda: [self._clear_window(), self._open_inventory_manager_tool()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        return_button.pack(pady=20)
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
                persistentdata["last_loaded_save"] = save_info["uuid"]
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
        
        def create_export():
            try:
                save_path = os.path.join(saves_folder, currentsave + ".sldsv")
                with open(save_path, 'r') as f:
                    save_data = json.load(f)
                
                money_amount = int(money_entry.get() or 0)
                
                if money_amount > save_data.get("money", 0):
                    self._popup_show_info("Error", "Not enough money!", sound="error")
                    return
                
                # Create transfer package
                transfer_data = {
                    "money": money_amount,
                    "items": [],
                    "timestamp": datetime.now().isoformat(),
                    "from_character": save_data.get("charactername", "Unknown")
                }
                
                # Deduct money
                save_data["money"] = save_data.get("money", 0) - money_amount
                
                # Save character
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
                # Create transfer file
                pickled_data = pickle.dumps(transfer_data)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                
                transfer_filename = f"transfers/transfer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sldtrf"
                with open(transfer_filename, 'w') as f:
                    f.write(encoded_data)
                
                self._popup_show_info("Success", f"Transfer file created: {transfer_filename}", sound="success")
                logging.info(f"Created transfer file: {transfer_filename}")
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
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure((0, 1), weight=1)
        
        title = customtkinter.CTkLabel(main_frame, text="Manage Containers & Transfer Items", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
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
            
            return containers
        
        containers = get_containers()
        
        # Info label
        info_label = customtkinter.CTkLabel(main_frame, text="Select source and destination containers to move items:", font=customtkinter.CTkFont(size=13))
        info_label.grid(row=1, column=0, columnspan=2, pady=10)
        
        container_frame = customtkinter.CTkFrame(main_frame)
        container_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=10)
        container_frame.grid_rowconfigure(0, weight=1)
        container_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Source container
        source_frame = customtkinter.CTkFrame(container_frame)
        source_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        source_frame.grid_rowconfigure(2, weight=1)
        source_frame.grid_columnconfigure(0, weight=1)
        
        source_label = customtkinter.CTkLabel(source_frame, text="Source Container", font=customtkinter.CTkFont(size=16, weight="bold"))
        source_label.grid(row=0, column=0, pady=10)
        
        source_selector = customtkinter.CTkComboBox(source_frame, values=[c["name"] for c in containers], width=300)
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
        
        dest_selector = customtkinter.CTkComboBox(dest_frame, values=[c["name"] for c in containers], width=300)
        dest_selector.grid(row=1, column=0, pady=5)
        dest_selector.set(containers[0]["name"])  # Default to Storage
        
        dest_scroll = customtkinter.CTkScrollableFrame(dest_frame, width=350, height=400)
        dest_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        def get_container_items(location):
            """Get items from a container location"""
            if location == "storage":
                return save_data.get("storage", [])
            elif location == "hands":
                return save_data["hands"].get("items", [])
            elif location.startswith("equipment."):
                slot = location.split(".")[1]
                item = save_data["equipment"].get(slot)
                if item and isinstance(item, dict):
                    return item.get("items", [])
            return []
        
        def set_container_items(location, items):
            """Set items for a container location"""
            if location == "storage":
                save_data["storage"] = items
            elif location == "hands":
                save_data["hands"]["items"] = items
            elif location.startswith("equipment."):
                slot = location.split(".")[1]
                if slot in save_data["equipment"] and save_data["equipment"][slot]:
                    save_data["equipment"][slot]["items"] = items
        
        def refresh_containers():
            # Clear displays
            for widget in source_scroll.winfo_children():
                widget.destroy()
            for widget in dest_scroll.winfo_children():
                widget.destroy()
            
            # Get selected containers
            source_name = source_selector.get()
            dest_name = dest_selector.get()
            
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
                
                # Check capacity of destination
                if dest_location == "hands":
                    current_encumbrance = save_data["hands"].get("encumbrance", 0)
                    capacity = save_data["hands"].get("capacity", 50)
                    if current_encumbrance + item_weight > capacity:
                        self._popup_show_info("Error", "Not enough capacity in destination!", sound="error")
                        return
                    save_data["hands"]["encumbrance"] = current_encumbrance + item_weight
                elif dest_location.startswith("equipment."):
                    slot = dest_location.split(".")[1]
                    if slot in save_data["equipment"] and save_data["equipment"][slot]:
                        dest_capacity = save_data["equipment"][slot].get("capacity", 0)
                        dest_encumbrance = sum(i.get("weight", 0) * i.get("quantity", 1) for i in dest_items)
                        if dest_encumbrance + item_weight > dest_capacity:
                            self._popup_show_info("Error", "Not enough capacity in destination!", sound="error")
                            return
                
                # Move item
                source_items.pop(item_idx)
                dest_items.append(item)
                
                set_container_items(source_location, source_items)
                set_container_items(dest_location, dest_items)
                
                # If moving from hands, update encumbrance
                if source_location == "hands":
                    save_data["hands"]["encumbrance"] = max(0, save_data["hands"].get("encumbrance", 0) - item_weight)
                
                # Save to file using _save_file
                self._save_file(save_data)
                
                refresh_containers()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Move failed: {e}")
                self._popup_show_info("Error", f"Move failed: {e}", sound="error")
        
        source_selector.configure(command=lambda _: refresh_containers())
        dest_selector.configure(command=lambda _: refresh_containers())
        
        refresh_containers()
        
        # Back button
        back_button = self._create_sound_button(
            main_frame,
            "Back",
            lambda: [self._clear_window(), self._open_inventory_management()],
            width=200,
            height=40
        )
        back_button.grid(row=3, column=0, columnspan=2, pady=10)
    
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
            
            # Add storage items
            for i, item in enumerate(save_data.get("storage", [])):
                if isinstance(item, dict) and item.get("equippable"):
                    all_items.append(("storage", i, item))
            
            # Add hands items
            for i, item in enumerate(save_data["hands"].get("items", [])):
                if isinstance(item, dict) and item.get("equippable"):
                    all_items.append(("hands", i, item))
            
            for location, idx, item in all_items:
                item_frame = customtkinter.CTkFrame(items_scroll)
                item_frame.pack(fill="x", pady=2, padx=5)
                
                item_name = item.get("name", "Unknown")
                slots = item.get("slot", [])
                if not isinstance(slots, list):
                    slots = [slots]
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name}\n  Slots: {', '.join(str(s) for s in slots)}",
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
                # Get valid slots for this item
                valid_slots = item.get("slot", [])
                if not isinstance(valid_slots, list):
                    valid_slots = [valid_slots]
                
                # Find first available slot
                equipment = save_data.get("equipment", {})
                target_slot = None
                for slot in valid_slots:
                    if slot in equipment and equipment[slot] is None:
                        target_slot = slot
                        break
                
                if target_slot is None:
                    self._popup_show_info("Error", f"No available slots for this item. Valid slots: {', '.join(valid_slots)}", sound="error")
                    return
                
                # Remove from source
                if location == "storage":
                    removed_item = save_data["storage"].pop(item_idx)
                elif location == "hands":
                    removed_item = save_data["hands"]["items"].pop(item_idx)
                    item_weight = removed_item.get("weight", 0) * removed_item.get("quantity", 1)
                    save_data["hands"]["encumbrance"] = max(0, save_data["hands"].get("encumbrance", 0) - item_weight)
                
                # Equip to slot
                save_data["equipment"][target_slot] = removed_item

                # Save using _save_file
                self._save_file(save_data)
                
                refresh_display()
                self._play_ui_sound("success")
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
        logging.info("Combat Mode definition called")
        self._popup_show_info("Combat Mode", "Combat Mode is under development.")
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

        # resolution
        customtkinter.CTkLabel(appearance_frame, text="Resolution:").grid(row=3, column=0, sticky="w", padx=10, pady=4)
        resolution_box = customtkinter.CTkOptionMenu(
            appearance_frame,
            values=["1920x1080", "1600x900", "1366x768", "1280x720"],
            command=lambda v: appearance_settings.__setitem__("resolution", v) or update_appearance()
        )
        resolution_box.set(appearance_settings.get("resolution", "1920x1080"))
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
            command=lambda v: appearance_settings.__setitem__("units", v)
        )
        units_box.set(appearance_settings.get("units", "imperial"))
        units_box.grid(row=6, column=1, sticky="ew", padx=10, pady=4)

        # auto set units
        auto_units_switch = customtkinter.CTkCheckBox(
            appearance_frame,
            text="Auto set units",
            command=lambda: appearance_settings.__setitem__("auto_set_units", bool(auto_units_switch.get()))
        )
        auto_units_switch.grid(row=7, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        auto_units_switch.select() if appearance_settings.get("auto_set_units", False) else auto_units_switch.deselect()

        # sound volume
        customtkinter.CTkLabel(appearance_frame, text="Sound Volume:").grid(row=8, column=0, sticky="w", padx=10, pady=(8,4))
        volume_slider = customtkinter.CTkSlider(
            appearance_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            command=lambda v: appearance_settings.__setitem__("sound_volume", int(v))
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
        if not table_files:
            table_files = ["<none>"]
        table_box = customtkinter.CTkOptionMenu(
            right_frame,
            values=table_files,
            state="disabled" if table_files == ["<none>"] else "normal",
            command=lambda v: global_variables.__setitem__("current_table", None if v == "<none>" else v)
        )
        current_table_val = global_variables.get("current_table") or "<none>"
        if current_table_val not in table_files:
            current_table_val = "<none>"
        table_box.set(current_table_val)
        table_box.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        # Dev/global toggles (only if devmode enabled)
        customtkinter.CTkLabel(right_frame, text="Developer Flags", font=customtkinter.CTkFont(size=14, weight="bold")).grid(row=2, column=0, columnspan=2, pady=(12,4), sticky="w")
        dev_enabled = global_variables.get("devmode", {}).get("value", False)

        def make_toggle(row, label, key):
            chk = customtkinter.CTkCheckBox(
                right_frame,
                text=label,
                state="normal" if dev_enabled else "disabled",
                command=lambda k=key, c=lambda: chk.get(): global_variables[k].__setitem__("value", bool(c()))
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

        # Back button
        back_button = self._create_sound_button(
            main_frame,
            "Back",
            lambda: [self._clear_window(), self._build_main_menu()],
            width=200,
            height=40
        )
        back_button.grid(row=2, column=0, columnspan=2, pady=(10,0))
    def _open_dev_tools(self):
        logging.info("Developer Tools definition called")
        self._popup_show_info("Developer Tools", "Developer Tools are under development.")
    def _open_dm_tools(self):
        logging.info("DM Tools definition called")
        self._popup_show_info("DM Tools", "DM Tools are under development.")
if __name__ == "__main__":
    app = App()