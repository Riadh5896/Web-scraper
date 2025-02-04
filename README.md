# Web-scraper
A multi-threaded web scraping tool with a user-friendly Tkinter GUI. This project allows users to scrape web pages (support for JS-dependent pages), extract structured data, and export results in CSV and JSON formats.


# Web Scraper with Tkinter GUI

## Overview
This project is a **web scraper with a graphical user interface (GUI)** built using **Tkinter**. It allows users to scrape webpages from a **sitemap or a single URL**, extract content (headings, paragraphs, images, and metadata), and save the results as **CSV or JSON** files.

The scraper supports:
- **Parallel scraping** with multithreading
- **JavaScript rendering** using Playwright (optional)
- **Filtering URLs** based on disallowed patterns
- **Pausing and resuming** the scraping process
- **Progress tracking** and estimated completion time

---
## Features
### ✅ Sitemap-Based Scraping
- Fetches URLs from **XML sitemaps** recursively.
- Allows filtering **disallowed URLs**.

### ✅ Content Extraction
- Extracts **headings (h1-h6)**, **paragraphs**, **images**, and **metadata**.
- Saves data in **CSV or JSON format**.

### ✅ JavaScript Support (Optional)
- Uses **Playwright** to render JavaScript-heavy pages.
- Can be toggled **on/off** in the GUI.

### ✅ Multithreading for Faster Scraping
- Uses **ThreadPoolExecutor** to scrape multiple URLs in parallel.
- Adjustable **thread count** for performance tuning.

### ✅ GUI with Tkinter
- Start, pause, resume, and stop scraping.
- **Browse & select output files** (CSV & JSON).
- **Live status updates & progress tracking.**
- Estimated **completion time** displayed dynamically.

---
## Installation
### 1️⃣ Clone the Repository
```sh
git clone https://github.com/your-username/Web-Scraper.git
cd Web-Scraper
```

### 2️⃣ Install Dependencies
This project requires Python 3. Install the dependencies:
```sh
pip install -r requirements.txt
```

If using **JavaScript rendering**, install Playwright:
```sh
pip install playwright
playwright install
```

### 3️⃣ Run the Scraper
Run the Tkinter GUI:
```sh
python scraper.py
```

---
## Usage
### **1️⃣ Start Scraping**
1. **Enter a sitemap URL** or a **single URL**.
2. (Optional) Enter **disallowed patterns** (comma-separated).
3. Choose an **output file (CSV/JSON)**.
4. Adjust **delay, thread count, and URL limit**.
5. Click **"Start"** to begin scraping.

### **2️⃣ Pause, Resume, or Stop**
- Click **"Pause"** to temporarily halt the process.
- Click **"Resume"** to continue.
- Click **"Stop"** to cancel the scraping.

### **3️⃣ Save and Export**
- Click **"Save"** to export results to CSV.
- Click **"Export JSON"** to save as a JSON file.

---
## File Structure
```
📂 Web-Scraper
│── scraper.py               # Main script with Tkinter GUI
│── requirements.txt         # Required dependencies
│── scraper.log              # Log file for debugging
│── output.csv (example)     # Example scraped data
│── output.json (example)    # Example JSON output
```

---
## Dependencies
- **Tkinter** → GUI for user interactions
- **Requests** → Fetches webpage content
- **BeautifulSoup** → Parses HTML content
- **Threading** → Multithreaded execution
- **Concurrent Futures** → Parallel scraping
- **Logging** → Saves error messages & logs
- **CSV & JSON** → Data export formats
- **Playwright (optional)** → Renders JavaScript pages

---
## Example Output
### **CSV Output**
| URL | Headings | Paragraphs | Images | Meta Description |
|------|----------|------------|--------|-----------------|
| example.com | ["Title"] | ["Paragraph 1"] | [{"src": "image.jpg", "alt": "desc"}] | "Meta data here" |

### **JSON Output**
```json
[
  {
    "url": "https://example.com",
    "headings": ["Title"],
    "paragraphs": ["Paragraph 1"],
    "images": [{"src": "image.jpg", "alt": "desc"}],
    "meta_description": "Meta data here"
  }
]
```

---
## Contributing
1. **Fork** the repository.
2. **Create** a new branch (`feature-xyz`).
3. **Commit** your changes.
4. **Push** and create a **pull request**.

---
## License
This project is **open-source** and available under the **MIT License**.

---
## Contact
For any questions or issues, reach out via GitHub **Issues** or **Pull Requests**.

🚀 Happy Scraping! 🚀

