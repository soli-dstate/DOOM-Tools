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
    {"name": "enemyloot", "ignore_gitignore": False}
]

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
            save_path = os.path.join(saves_folder, currentsave)
            try:
                pickled_data = pickle.dumps(data)
                encoded_data = base64.b85encode(pickled_data).decode('utf-8')
                save_file_path = save_path + ".sldsv"
                with open(save_file_path, 'w') as f:
                    f.write(encoded_data)
                logging.info(f"Data saved to {save_file_path}")
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
        try:
            persistent_path = os.path.join(saves_folder, "persistent_data.sldsv")
            if os.path.exists(persistent_path):
                with open(persistent_path, 'r') as f:
                    encoded_persistent = f.read()
                pickled_persistent = base64.b85decode(encoded_persistent.encode('utf-8'))
                loaded_persistent = pickle.loads(pickled_persistent)
                persistentdata.update(loaded_persistent)
                logging.info(f"Persistent data loaded from {persistent_path}")
            else:
                logging.info("No persistent data file found, using defaults")
        except Exception as e:
            logging.warning(f"Failed to load persistent data: {e}")
        if save_filename is None:
            return None
        save_path = os.path.join(saves_folder, save_filename)
        if not os.path.exists(save_path):
            logging.error(f"Save file '{save_filename}' does not exist.")
            return None
        try:
            with open(save_path, 'r') as f:
                encoded_data = f.read()
            pickled_data = base64.b85decode(encoded_data.encode('utf-8'))
            data = pickle.loads(pickled_data)
            logging.info(f"Data loaded from {save_filename}")
            if save_filename.endswith('.sldsv'):
                parts = save_filename.rsplit('_', 1)
                if len(parts) == 2:
                    uuid_part = parts[1].replace('.sldsv', '')
                    persistentdata["last_loaded_save"] = uuid_part
                    logging.info(f"Updated last_loaded_save to UUID: {uuid_part}")
            return data
        except Exception as e:
            logging.error(f"Failed to load data from '{save_filename}': {e}")
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
        character_management_button = self._create_sound_button(self.root, "Character Management", lambda: [self._clear_window(), self._open_character_management()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        character_management_button.pack(pady=20)
        inventory_management_button = self._create_sound_button(self.root, "Inventory Management", lambda: [self._clear_window(), self._open_inventory_management()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        inventory_management_button.pack(pady=20)
        item_equip_button = self._create_sound_button(self.root, "Item Equipping", lambda: [self._clear_window(), self._open_item_equipping()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        item_equip_button.pack(pady=20)
        back_button = self._create_sound_button(self.root, "Back to Main Menu", lambda: [self._clear_window(), self._build_main_menu()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        back_button.pack(pady=20)
    def _open_character_management(self):
        logging.info("Character Management definition called")
        create_new_character_button = self._create_sound_button(self.root, "Create New Character", lambda: [self._clear_window(), self._create_new_character()], width=500, height=50, font=customtkinter.CTkFont(size=16))
        create_new_character_button.pack(pady=20)
        load_existing_character_button = self._create_sound_button(self.root, "Load Existing Character", lambda: [self._clear_window(), self._load_existing_character()], width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if not os.listdir(saves_folder) or all(f in ["persistent_data.sldsv", "settings.sldsv"] for f in os.listdir(saves_folder)) else "normal")
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
        
        # Storage/Hands Transfer button
        storage_transfer_button = self._create_sound_button(
            main_frame,
            "Transfer Items (Storage ↔ Hands)",
            lambda: [self._clear_window(), self._transfer_storage_hands()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        storage_transfer_button.pack(pady=10)
        
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
        
        # Container Management button
        container_management_button = self._create_sound_button(
            main_frame,
            "Manage Containers",
            lambda: [self._clear_window(), self._manage_containers()],
            width=500,
            height=50,
            font=customtkinter.CTkFont(size=16)
        )
        container_management_button.pack(pady=10)
        
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
    
    def _transfer_storage_hands(self):
        import json
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        # Load current save data
        save_path = os.path.join(saves_folder, currentsave + ".sldsv")
        try:
            with open(save_path, 'r') as f:
                save_data = json.load(f)
        except Exception as e:
            self._popup_show_info("Error", f"Failed to load character data: {e}", sound="error")
            return
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_container = customtkinter.CTkFrame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_container.grid_rowconfigure(1, weight=1)
        main_container.grid_columnconfigure((0, 1), weight=1)
        
        title = customtkinter.CTkLabel(main_container, text="Transfer Items: Storage ↔ Hands", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Storage column
        storage_frame = customtkinter.CTkFrame(main_container)
        storage_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        storage_frame.grid_rowconfigure(1, weight=1)
        storage_frame.grid_columnconfigure(0, weight=1)
        
        storage_label = customtkinter.CTkLabel(storage_frame, text="Storage", font=customtkinter.CTkFont(size=16, weight="bold"))
        storage_label.grid(row=0, column=0, pady=(10, 5))
        
        storage_scroll = customtkinter.CTkScrollableFrame(storage_frame, width=400, height=400)
        storage_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        storage_scroll.grid_columnconfigure(0, weight=1)
        
        # Hands column
        hands_frame = customtkinter.CTkFrame(main_container)
        hands_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        hands_frame.grid_rowconfigure(1, weight=1)
        hands_frame.grid_columnconfigure(0, weight=1)
        
        hands_label = customtkinter.CTkLabel(hands_frame, text=f"Hands ({self._format_weight(save_data['hands'].get('encumbrance', 0))}/{self._format_weight(save_data['hands'].get('capacity', 50))})", font=customtkinter.CTkFont(size=16, weight="bold"))
        hands_label.grid(row=0, column=0, pady=(10, 5))
        
        hands_scroll = customtkinter.CTkScrollableFrame(hands_frame, width=400, height=400)
        hands_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        hands_scroll.grid_columnconfigure(0, weight=1)
        
        def refresh_display():
            # Clear existing items
            for widget in storage_scroll.winfo_children():
                widget.destroy()
            for widget in hands_scroll.winfo_children():
                widget.destroy()
            
            # Update hands label
            hands_label.configure(text=f"Hands ({self._format_weight(save_data['hands'].get('encumbrance', 0))}/{self._format_weight(save_data['hands'].get('capacity', 50))})")
            
            # Display storage items
            for i, item in enumerate(save_data.get("storage", [])):
                item_frame = customtkinter.CTkFrame(storage_scroll)
                item_frame.grid(row=i, column=0, sticky="ew", pady=2)
                item_frame.grid_columnconfigure(0, weight=1)
                
                item_name = item.get("name", "Unknown Item")
                item_weight = item.get("weight", 0)
                quantity = item.get("quantity", 1)
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name} x{quantity} ({self._format_weight(item_weight * quantity)})",
                    anchor="w"
                )
                item_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
                
                transfer_button = self._create_sound_button(
                    item_frame,
                    "→ Hands",
                    lambda idx=i: transfer_to_hands(idx),
                    width=100,
                    height=30
                )
                transfer_button.grid(row=0, column=1, padx=10, pady=5)
            
            if not save_data.get("storage", []):
                empty_label = customtkinter.CTkLabel(storage_scroll, text="Storage is empty", text_color="gray")
                empty_label.grid(row=0, column=0, pady=20)
            
            # Display hands items
            for i, item in enumerate(save_data["hands"].get("items", [])):
                item_frame = customtkinter.CTkFrame(hands_scroll)
                item_frame.grid(row=i, column=0, sticky="ew", pady=2)
                item_frame.grid_columnconfigure(0, weight=1)
                
                item_name = item.get("name", "Unknown Item")
                item_weight = item.get("weight", 0)
                quantity = item.get("quantity", 1)
                
                item_label = customtkinter.CTkLabel(
                    item_frame,
                    text=f"{item_name} x{quantity} ({self._format_weight(item_weight * quantity)})",
                    anchor="w"
                )
                item_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
                
                transfer_button = self._create_sound_button(
                    item_frame,
                    "← Storage",
                    lambda idx=i: transfer_to_storage(idx),
                    width=100,
                    height=30
                )
                transfer_button.grid(row=0, column=1, padx=10, pady=5)
            
            if not save_data["hands"].get("items", []):
                empty_label = customtkinter.CTkLabel(hands_scroll, text="Hands are empty", text_color="gray")
                empty_label.grid(row=0, column=0, pady=20)
        
        def transfer_to_hands(storage_idx):
            try:
                item = save_data["storage"][storage_idx]
                item_weight = item.get("weight", 0) * item.get("quantity", 1)
                
                current_encumbrance = save_data["hands"].get("encumbrance", 0)
                capacity = save_data["hands"].get("capacity", 50)
                
                if current_encumbrance + item_weight > capacity:
                    self._popup_show_info("Error", "Not enough capacity in hands!", sound="error")
                    return
                
                # Transfer item
                save_data["hands"]["items"].append(item)
                save_data["hands"]["encumbrance"] = current_encumbrance + item_weight
                save_data["storage"].pop(storage_idx)
                
                # Save changes
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
                refresh_display()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Transfer failed: {e}")
                self._popup_show_info("Error", f"Transfer failed: {e}", sound="error")
        
        def transfer_to_storage(hands_idx):
            try:
                item = save_data["hands"]["items"][hands_idx]
                item_weight = item.get("weight", 0) * item.get("quantity", 1)
                
                # Transfer item
                save_data["storage"].append(item)
                save_data["hands"]["items"].pop(hands_idx)
                save_data["hands"]["encumbrance"] = max(0, save_data["hands"].get("encumbrance", 0) - item_weight)
                
                # Save changes
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
                refresh_display()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Transfer failed: {e}")
                self._popup_show_info("Error", f"Transfer failed: {e}", sound="error")
        
        refresh_display()
        
        # Back button
        back_button = self._create_sound_button(
            main_container,
            "Back",
            lambda: [self._clear_window(), self._open_inventory_management()],
            width=200,
            height=40,
            font=customtkinter.CTkFont(size=14)
        )
        back_button.grid(row=2, column=0, columnspan=2, pady=(10, 0))
    
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
        import json
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        # Load current save data
        save_path = os.path.join(saves_folder, currentsave + ".sldsv")
        try:
            with open(save_path, 'r') as f:
                save_data = json.load(f)
        except Exception as e:
            self._popup_show_info("Error", f"Failed to load character data: {e}", sound="error")
            return
        
        self._clear_window()
        
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title = customtkinter.CTkLabel(main_frame, text="Container Management", font=customtkinter.CTkFont(size=20, weight="bold"))
        title.pack(pady=(0, 20))
        
        # Find all equipped containers
        containers = []
        equipment = save_data.get("equipment", {})
        
        # Check storage as a container
        containers.append({
            "name": "Storage",
            "location": "storage",
            "capacity": float('inf'),
            "items": save_data.get("storage", []),
            "encumbrance": sum(item.get("weight", 0) * item.get("quantity", 1) for item in save_data.get("storage", []))
        })
        
        # Check hands as a container
        containers.append({
            "name": "Hands",
            "location": "hands",
            "capacity": save_data["hands"].get("capacity", 50),
            "items": save_data["hands"].get("items", []),
            "encumbrance": save_data["hands"].get("encumbrance", 0)
        })
        
        # Check equipped items for containers
        for slot, item in equipment.items():
            if item and isinstance(item, dict):
                if "capacity" in item and "items" in item:
                    item_encumbrance = sum(i.get("weight", 0) * i.get("quantity", 1) for i in item.get("items", []))
                    containers.append({
                        "name": f"{item.get('name', 'Container')} ({slot})",
                        "location": f"equipment.{slot}",
                        "capacity": item.get("capacity", 0),
                        "items": item.get("items", []),
                        "encumbrance": item_encumbrance
                    })
        
        if len(containers) <= 2:  # Only storage and hands
            self._popup_show_info("Info", "No equipped containers found. Equip backpacks, pouches, or other containers first.", sound="popup")
            self._clear_window()
            self._open_inventory_management()
            return
        
        # Container selection
        info_label = customtkinter.CTkLabel(main_frame, text="Select source and destination containers to move items:", font=customtkinter.CTkFont(size=13))
        info_label.pack(pady=10)
        
        container_frame = customtkinter.CTkFrame(main_frame)
        container_frame.pack(fill="both", expand=True, pady=10)
        container_frame.grid_rowconfigure(0, weight=1)
        container_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Source container
        source_frame = customtkinter.CTkFrame(container_frame)
        source_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        source_frame.grid_rowconfigure(2, weight=1)
        
        source_label = customtkinter.CTkLabel(source_frame, text="Source Container", font=customtkinter.CTkFont(size=16, weight="bold"))
        source_label.grid(row=0, column=0, pady=10)
        
        source_selector = customtkinter.CTkComboBox(source_frame, values=[c["name"] for c in containers], width=300)
        source_selector.grid(row=1, column=0, pady=5)
        source_selector.set(containers[0]["name"])
        
        source_scroll = customtkinter.CTkScrollableFrame(source_frame, width=350, height=400)
        source_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        # Destination container
        dest_frame = customtkinter.CTkFrame(container_frame)
        dest_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        dest_frame.grid_rowconfigure(2, weight=1)
        
        dest_label = customtkinter.CTkLabel(dest_frame, text="Destination Container", font=customtkinter.CTkFont(size=16, weight="bold"))
        dest_label.grid(row=0, column=0, pady=10)
        
        dest_selector = customtkinter.CTkComboBox(dest_frame, values=[c["name"] for c in containers], width=300)
        dest_selector.grid(row=1, column=0, pady=5)
        dest_selector.set(containers[1]["name"] if len(containers) > 1 else containers[0]["name"])
        
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
            
            source_container = next((c for c in containers if c["name"] == source_name), None)
            dest_container = next((c for c in containers if c["name"] == dest_name), None)
            
            if not source_container or not dest_container:
                return
            
            # Display source items
            for i, item in enumerate(source_container["items"]):
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
                    lambda idx=i, src=source_container, dst=dest_container: move_item(idx, src, dst),
                    width=80,
                    height=30
                )
                move_button.pack(side="right", padx=10, pady=5)
            
            if not source_container["items"]:
                empty_label = customtkinter.CTkLabel(source_scroll, text="Container is empty", text_color="gray")
                empty_label.pack(pady=20)
            
            # Display destination items
            for item in dest_container["items"]:
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
            
            if not dest_container["items"]:
                empty_label = customtkinter.CTkLabel(dest_scroll, text="Container is empty", text_color="gray")
                empty_label.pack(pady=20)
        
        def move_item(item_idx, source_container, dest_container):
            try:
                item = source_container["items"][item_idx]
                item_weight = item.get("weight", 0) * item.get("quantity", 1)
                
                # Check capacity
                if dest_container["capacity"] != float('inf'):
                    if dest_container["encumbrance"] + item_weight > dest_container["capacity"]:
                        self._popup_show_info("Error", "Not enough capacity in destination container!", sound="error")
                        return
                
                # Move item
                source_container["items"].pop(item_idx)
                source_container["encumbrance"] -= item_weight
                dest_container["items"].append(item)
                dest_container["encumbrance"] += item_weight
                
                # Update save data
                if source_container["location"] == "storage":
                    save_data["storage"] = source_container["items"]
                elif source_container["location"] == "hands":
                    save_data["hands"]["items"] = source_container["items"]
                    save_data["hands"]["encumbrance"] = source_container["encumbrance"]
                elif source_container["location"].startswith("equipment."):
                    slot = source_container["location"].split(".")[1]
                    save_data["equipment"][slot]["items"] = source_container["items"]
                
                if dest_container["location"] == "storage":
                    save_data["storage"] = dest_container["items"]
                elif dest_container["location"] == "hands":
                    save_data["hands"]["items"] = dest_container["items"]
                    save_data["hands"]["encumbrance"] = dest_container["encumbrance"]
                elif dest_container["location"].startswith("equipment."):
                    slot = dest_container["location"].split(".")[1]
                    save_data["equipment"][slot]["items"] = dest_container["items"]
                
                # Save to file
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
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
        back_button.pack(pady=10)
    
    def _open_item_equipping(self):
        import json
        
        logging.info("Item Equipping definition called")
        
        if currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound="error")
            return
        
        # Load current save data
        save_path = os.path.join(saves_folder, currentsave + ".sldsv")
        try:
            with open(save_path, 'r') as f:
                save_data = json.load(f)
        except Exception as e:
            self._popup_show_info("Error", f"Failed to load character data: {e}", sound="error")
            return
        
        self._clear_window()
        
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
                
                # Save
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
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
                
                # Save
                with open(save_path, 'w') as f:
                    json.dump(save_data, f, indent=4)
                
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
            self._save_file(currentsave)
            logging.info("Data saved before exit.")
        else:
            logging.info("No current save to save before exit.")
        logging.info("Program exited safely.")
        self.root.quit()
    def _open_settings(self):
        logging.info("Settings definition called")
        self._popup_show_info("Settings", "Settings are under development.")
    def _open_dev_tools(self):
        logging.info("Developer Tools definition called")
        self._popup_show_info("Developer Tools", "Developer Tools are under development.")
    def _open_dm_tools(self):
        logging.info("DM Tools definition called")
        self._popup_show_info("DM Tools", "DM Tools are under development.")
if __name__ == "__main__":
    app = App()