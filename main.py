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

pygame.init()

pygame.mixer.init(channels=4096)

version = "0.0.0"

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
    "borderless": False
}

folders = [
    "logs",
    "sounds",
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
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info(f"Created missing folder: {folder}")
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
    if os.name == 'nt':  # Windows
        saves_folder = os.path.join(os.getenv('LOCALAPPDATA'), 'DOOM Tools', 'saves')
    else:  # Unix-based systems
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
        ""
    }
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
    def __init__(self):
        self.root = customtkinter.CTk()
        self.root.title("DOOM Tools")
        self.root.minsize(1280, 720)
        self._build_main_menu()
        self.root.mainloop()
        customtkinter.set_appearance_mode(appearance_settings["appearance_mode"])
        customtkinter.set_default_color_theme(appearance_settings["color_theme"])
        self.root.attributes('-fullscreen', appearance_settings["fullscreen"])
        if appearance_settings["borderless"]:
            self.root.overrideredirect(True)
        self.root.geometry(appearance_settings["resolution"])
    def _popup_show_info(self, title, message):
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("400x200")
        label = customtkinter.CTkLabel(popup, text=message, wraplength=380)
        label.pack(pady=20, padx=20)
        ok_button = customtkinter.CTkButton(popup, text="OK", command=popup.destroy)
        ok_button.pack(pady=10)
    def _build_main_menu(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        title_label = customtkinter.CTkLabel(main_frame, text="DOOM Tools", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        version_label = customtkinter.CTkLabel(main_frame, text=f"Version: {version}", font=customtkinter.CTkFont(size=16))
        version_label.pack()
        loot_button = customtkinter.CTkButton(main_frame, text="Looting", command=self._open_loot_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        loot_button.pack(pady=10)
        business_button = customtkinter.CTkButton(main_frame, text="Businesses", command=self._open_business_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        business_button.pack(pady=10)
        inventoryman_button = customtkinter.CTkButton(main_frame, text="Inventory Manager", command=self._open_inventory_manager_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        inventoryman_button.pack(pady=10)
        combatmode_button = customtkinter.CTkButton(main_frame, text="Combat Mode", command=self._open_combat_mode_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        combatmode_button.pack(pady=10)
        exitb_button = customtkinter.CTkButton(main_frame, text="Exit", command=self._safe_exit, width=500, height=50, font=customtkinter.CTkFont(size=16))
        exitb_button.pack(pady=10)
        settings_button = customtkinter.CTkButton(main_frame, text="Settings", command=self._open_settings, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        settings_button.pack(pady=10)
        if global_variables["devmode"]["value"]:
            devtools_button = customtkinter.CTkButton(main_frame, text="Developer Tools", command=self._open_dev_tools, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
            devtools_button.pack(pady=10)
        else:
            devtools_button = customtkinter.CTkButton(main_frame, text="Developer Tools", width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled")
            devtools_button.pack(pady=10)
        if global_variables["dmmode"]["value"]:
            dmmode_button = customtkinter.CTkButton(main_frame, text="DM Tools", command=self._open_dm_tools, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
            dmmode_button.pack(pady=10)
        else:
            dmmode_button = customtkinter.CTkButton(main_frame, text="DM Tools", width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled")
            dmmode_button.pack(pady=10)
        if currentsave is None:
            currentsave_label = customtkinter.CTkLabel(main_frame, text="No save loaded. Please load a save to enable tools.", font=customtkinter.CTkFont(size=14), text_color="red")
            currentsave_label.pack(pady=20)
    def _open_loot_tool(self):
        self._popup_show_info("Looting", "Looting is under development.")
    def _open_business_tool(self):
        self._popup_show_info("Businesses", "Businesses are under development.")
    def _open_inventory_manager_tool(self):
        self._popup_show_info("Inventory Manager", "Inventory Manager is under development.")
    def _open_combat_mode_tool(self):
        self._popup_show_info("Combat Mode", "Combat Mode is under development.")
    def _safe_exit(self):
        # once save functionality is added, implement save on exit
        logging.info("Program exited safely.")
        self.root.quit()
    def _open_settings(self):
        pass
    def _open_dev_tools(self):
        pass
    def _open_dm_tools(self):
        pass
if __name__ == "__main__":
    app = App()