# projectAlgo

<img src="assets/logo.png" alt="Project Logo" width="200" title="projectAlgo Logo">

an algorithmic trading suite in python by storyofthewolf

feels the vibes!

## Table of Contents

- [About The Project](#about-the-project)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)

---

## About The Project


This project provides a python framework for collecting, managing, and visualizing historical financial data, serving as the foundation for algorithmic trading strategy development and backtesting to come later.  While other resources exist, I find that one cannot really learn something unless you do it yourself.  So here we go.*

### Key Features:
- 1: collecting market data from yahoo finance.
- 2: make static plots of market data with technical indicators using mplfinance

---

## Getting Started

This section will guide users (and yourself) on how to set up and run your project locally.

### Prerequisites

List any software, libraries, or accounts that need to be installed or set up before running the project.

* Python 3.x
* Anaconda/Miniconda (recommended for environment management)
* Required Python libraries (listed in `requirements.txt` - we'll get to this later)
* An active internet connection for data downloads.

### Installation

Step-by-step instructions on how to get a development environment running.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/storyofthewolf/projectAlgo.git](https://github.com/storyofthewolf/projectAlgo.git)
    cd your-repo-name # or whatever your local folder is called (e.g., projectAalgo)
    ```
2.  **Create and activate a Conda environment:**
    ```bash
    conda create -n algo_env python=3.9 # Use your preferred Python version
    conda activate algo_env
    ```
3.  **Install required Python packages:**
    ```bash
    pip install pandas yfinance mplfinance argparse # And any others you add later
    ```

### Usage

How to use your scripts. Provide clear examples.

#### 1. Data Collection (`get_data.py`)

Download historical stock data:

```bash
# Navigate to the project root (e.g., /Users/wolfe/Desktop/myprojects/algo)
python -m data_manager.get_data --tickers AAPL MSFT --interval 1d --start 2023-01-01 --end 2024-12-31 --output_dir data/historical_data
```


#### 2. Plotting (`visualize.py`)

Produce simple visualizations using mplfinance

```bash
python -m visualization.visualize -t ISRG -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20,50, 100;rsi:14,28"
```

## Development Issues
1. Downloading data for short timeframes and intervals does not source correctly.  
