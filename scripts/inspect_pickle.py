# projectAlgo/scripts/inspect_pickle.py

import pickle
import sys
import os
import pandas as pd # Needed to format DataFrame/Series nicely
from pprint import pprint # For pretty printing dictionaries

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_pickle.py <path_to_pickle_file>")
        sys.exit(1)

    filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"Error: File not found at '{filepath}'")
        sys.exit(1)

    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        print(f"\n--- Contents of '{filepath}' ---")
        if isinstance(data, dict):
            # Print main keys and types
            print("\nKeys and Data Types:")
            for key, value in data.items():
                print(f"  - '{key}': Type: {type(value).__name__}", end="")
                if isinstance(value, (pd.DataFrame, pd.Series)):
                    print(f", Shape: {value.shape}, Index Type: {type(value.index).__name__}")
                    if isinstance(value, pd.DataFrame):
                        print(f"    Columns: {list(value.columns)}")
                else:
                    print(f", Value: {str(value)[:100]}...") # Print first 100 chars for non-pandas types

            # Print first few rows of DataFrames/Series for quick inspection
            print("\n--- First 5 rows of DataFrame/Series data: ---")
            for key, value in data.items():
                if isinstance(value, pd.DataFrame):
                    print(f"\n--- {key} (DataFrame) ---")
                    print(value.head().to_markdown(index=True)) # Use to_markdown for readable format
                elif isinstance(value, pd.Series):
                    print(f"\n--- {key} (Series) ---")
                    print(value.head().to_markdown(index=True))
            
            # Print performance metrics
            if 'performance_metrics' in data and isinstance(data['performance_metrics'], dict):
                print("\n--- Performance Metrics ---")
                pprint(data['performance_metrics'])

        else:
            print("\n--- Raw Content (not a dictionary) ---")
            pprint(data) # Just try to print whatever it is

        print("\n--- End of Inspection ---")

    except Exception as e:
        print(f"Error loading or inspecting pickle file: {e}")
        sys.exit(1)