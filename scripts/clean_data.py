# projectAlgo/scripts/clean_data.py

import os
import shutil
import argparse

def delete_all_data(data_dir: str):
    """
    Deletes the 'historical_data' and 'backtest_results' directories
    within the specified data directory.
    """
    dirs_to_delete = [
        os.path.join(data_dir, 'historical_data'),
        os.path.join(data_dir, 'backtest_results')
    ]

    print(f"--- Attempting to delete all data within: {data_dir} ---")

    for dir_path in dirs_to_delete:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"Successfully deleted: {dir_path}")
            except OSError as e:
                print(f"Error deleting {dir_path}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while deleting {dir_path}: {e}")
        else:
            print(f"Directory not found, skipping: {dir_path}")

    print("--- All data deletion process complete ---")


def delete_ticker_data(data_dir: str, tickers: list[str]):
    """
    Deletes historical data and backtest results files specifically for the given tickers.
    """
    if not tickers:
        print("No tickers provided for specific deletion. Nothing to do.")
        return

    print(f"--- Deleting data for tickers: {', '.join(tickers)} ---")

    # Normalize tickers to lowercase for case-insensitive matching
    lower_case_tickers = [t.lower() for t in tickers]

    # Directories to scan for ticker-specific files
    scan_dirs = [
        os.path.join(data_dir, 'historical_data'),
        os.path.join(data_dir, 'backtest_results')
    ]

    files_deleted_count = 0

    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            print(f"Skipping scan of '{scan_dir}': Directory does not exist.")
            continue

        print(f"Scanning '{scan_dir}' for ticker-specific files...")
        for filename in os.listdir(scan_dir):
            file_path = os.path.join(scan_dir, filename)
            
            # Check if it's a file and not a directory (e.g., in case of nested structures)
            if os.path.isfile(file_path):
                # Check if any of the provided tickers are in the filename (case-insensitive)
                if any(ticker in filename.lower() for ticker in lower_case_tickers):
                    try:
                        os.remove(file_path)
                        print(f"  Deleted: {filename}")
                        files_deleted_count += 1
                    except OSError as e:
                        print(f"  Error deleting {filename}: {e}")
                    except Exception as e:
                        print(f"  An unexpected error occurred while deleting {filename}: {e}")
            else:
                # If there are subdirectories (e.g., for specific backtest runs),
                # you might want to extend this to recursively delete them if their name
                # or their content implies a ticker. For now, it only deletes files.
                pass 
    
    if files_deleted_count == 0:
        print(f"No files found for tickers: {', '.join(tickers)}.")
    else:
        print(f"--- Deleted {files_deleted_count} files for specified tickers ---")


if __name__ == "__main__":
    # Determine the project root directory relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    data_base_dir = os.path.join(project_root, 'data')

    parser = argparse.ArgumentParser(
        description="Delete historical data and backtest results from the projectAlgo/data directory."
    )

    # Create a mutually exclusive group for --all and --tickers
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--all',
        action='store_true',
        help="Delete all historical_data and backtest_results directories."
    )
    group.add_argument(
        '--tickers',
        nargs='+', # Accepts one or more ticker symbols
        help="Delete data (CSV/PKL files) for specific ticker symbols (e.g., AAPL MSFT)."
    )

    args = parser.parse_args()

    if args.all:
        delete_all_data(data_base_dir)
    elif args.tickers:
        delete_ticker_data(data_base_dir, args.tickers)
