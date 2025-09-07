# ===========================================
# file: README.md
# ===========================================
# GalaDex Arbitrage Bot

Welcome to the GalaDex Arbitrage Bot! This is a simple but powerful tool designed to automatically find and execute arbitrage trading opportunities on the GalaSwap DEX.

**This bot is intended for educational purposes. Automated trading is risky and can result in the loss of funds. Use this software at your own risk.**

---

## What is Arbitrage Trading?

Arbitrage is a trading strategy that takes advantage of small price differences for the same asset across different markets. In our case, the "markets" are different trading pools on the GalaSwap DEX.

This bot looks for "triangular arbitrage" opportunities. For example, it might find a path like this:

1.  Trade **GUSDC** for **GALA**.
2.  Trade that **GALA** for **GWETH**.
3.  Trade that **GWETH** back to **GUSDC**.

If, at the end of this cycle, you end up with more GUSDC than you started with, you've made a profit! This bot is designed to find and execute these cycles automatically.

---

## Getting Started

Follow these steps to get the bot up and running on your local machine.

### 1. Prerequisites

*   You need to have **Python** installed on your computer. You can download it from [python.org](https://www.python.org/downloads/).

### 2. Download the Code

*   You can download the code as a ZIP file from the GitHub page.
*   Alternatively, if you have Git installed, you can clone the repository with this command:
    ```bash
    git clone <repository-url>
    ```

### 3. Set Up a Virtual Environment

A virtual environment is a private sandbox for your project's dependencies. It's a best practice to always use one.

*   Open a terminal or command prompt in the project's main folder (`GalaDex/`).
*   Run the following command to create a virtual environment named `.venv`:
    ```bash
    python -m venv .venv
    ```
*   Activate the environment:
    *   **On Windows:**
        ```powershell
        .\.venv\Scripts\Activate.ps1
        ```
    *   **On macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```
    You'll know it's active when you see `(.venv)` at the beginning of your terminal prompt.

### 4. Install Dependencies

*   With your virtual environment still active, run this command to install all the necessary libraries:
    ```bash
    pip install -r requirements.txt
    ```

---

## Configuration

All the bot's settings are located in the `gala/config.py` file. This is the most important file for you to edit. Open it in a text editor to get started.

### **VERY IMPORTANT: Wallet Security**

To trade, the bot needs your wallet address and your private key.

*   `USER_ADDRESS`: Your public GalaChain address (e.g., `eth|0x...`). This is like your bank account number.
*   `PRIVATE_KEY_HEX`: Your wallet's private key. This is like the password to your bank account.

**NEVER, EVER SHARE YOUR PRIVATE KEY OR COMMIT IT TO A PUBLIC GITHUB REPOSITORY.**

The safest way to provide your private key is by using **environment variables**. This avoids saving it directly in the code.

*   **How to set environment variables (example):**
    *   **On Windows (in PowerShell):**
        ```powershell
        $env:GALA_PRIVATE_KEY="0xyourprivatekey..."
        $env:GALA_USER_ADDR="eth|0xyouraddress..."
        ```
    *   **On macOS/Linux:**
        ```bash
        export GALA_PRIVATE_KEY="0xyourprivatekey..."
        export GALA_USER_ADDR="eth|0xyouraddress..."
        ```

### Key Settings in `config.py`

*   `DRY_RUN`: **This is your most important safety switch.** By default, it is `true`. When `DRY_RUN` is `true`, the bot will only *simulate* trades and print what it *would* do. It will never spend your funds. **Only set this to `false` when you are ready to live trade.**
*   `START_TOKEN`: The token the bot will use to start its trades (e.g., "GUSDC").
*   `START_AMOUNT`: The amount of `START_TOKEN` to use in each trade.
*   `POOLS`: The list of trading pairs you want the bot to consider.
*   `SCAN_INTERVAL_SECONDS`: How many seconds to wait between each scan for opportunities.

---

## How to Run the Bot

1.  Make sure your virtual environment is **active**.
2.  Make sure you have set your `GALA_PRIVATE_KEY` and `GALA_USER_ADDR` as environment variables (or entered them in `config.py`, which is less secure).
3.  Run the bot from the main project folder using this command:
    ```bash
    python main.py
    ```

The bot will start scanning. By default, it's in **Dry Run** mode, so you can watch its output safely.

When you are ready to perform live trades, stop the bot (`Ctrl+C`), open `gala/config.py`, change `DRY_RUN` to `false`, and run it again. **Do this with extreme caution.**

---

## How It Works (A Quick Overview)

1.  **Discover Pools:** The bot first checks which of the pools you listed in the config have enough money ("liquidity") to be worth trading in. To save on API requests, this list is cached and only refreshed periodically.
2.  **Find Triangles:** Using the list of active pools, it finds all possible three-step triangular paths (e.g., A -> B -> C -> A).
3.  **Simulate Trades:** It simulates a trade through the most promising paths to calculate the potential profit.
4.  **Check Profitability:** It compares the potential profit against your `MIN_PROFIT_BPS` and `PROFIT_BUFFER_BPS` settings.
5.  **Execute:** If `DRY_RUN` is `false` and a profitable opportunity is found, the bot will execute the series of trades.
6.  **Repeat:** The bot waits for the configured interval and starts a new scan.
