import os
import logging
from datetime import datetime
import zipfile
import glob
import requests
import platform
import pygame
import customtkinter

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
    "devmode": False,
}

folders = [
    "logs",
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

if any(indicator in os.environ for indicator in ide_indicators):
    if not global_variables["devmode"]:
        global_variables["devmode"] = True
        logging.info("Development mode activated due to IDE environment detection.")
    else:
        logging.info("IDE environment detected, but development mode is already True.")
    logging.info(f"Trigger: {[key for key in os.environ if key in ide_indicators]}")
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info(f"Created missing folder: {folder}")
        with open('.gitignore', 'a') as gitignore:
            gitignore.write(f'/{folder}/\n')

currentsave = None

class App:
    def __init__(self):
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("dark-blue")
        self.root = customtkinter.CTk()
        self.root.title("DOOM Tools")
        self.root.geometry("1280x720")
        self.root.minsize(960, 600)
        self._build_main_menu()
        self.root.mainloop()
    def _build_main_menu(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        title_label = customtkinter.CTkLabel(main_frame, text="DOOM Tools", font=customtkinter.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)
        version_label = customtkinter.CTkLabel(main_frame, text=f"Version: {version}", font=customtkinter.CTkFont(size=16))
        version_label.pack()
        loot_button = customtkinter.CTkButton(main_frame, text="Loot", command=self._open_loot_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        loot_button.pack(pady=10)
        business_button = customtkinter.CTkButton(main_frame, text="Businesses", command=self._open_business_tool, width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        business_button.pack(pady=10)
        inventoryman_button = customtkinter.CTkButton(main_frame, text="Inventory Manager", command=self._open_inventory_manager_tool, width=500, height=50, font=customtkinter.CTkFont(size=16))
        inventoryman_button.pack(pady=10)
        combatmode_button = customtkinter.CTkButton(main_frame, text="Combat Mode", width=500, height=50, font=customtkinter.CTkFont(size=16), state="disabled" if currentsave is None else "normal")
        combatmode_button.pack(pady=10)
    def _open_loot_tool(self):
        pass
    def _open_business_tool(self):
        pass
    def _open_inventory_manager_tool(self):
        pass
if __name__ == "__main__":
    app = App()