# algo/data_manager/__init__.py

# Re-export functions from data_manager_functions.py
from .data_manager_functions import get_historical_data, save_data_to_csv, load_data_from_csv

# Optionally, you can also define __all__ if you want to control what
# gets imported with 'from data_manager import *'.
# __all__ = [
#     "get_historical_data",
#     "save_data_to_csv",
#     "load_data_from_csv",
# ]