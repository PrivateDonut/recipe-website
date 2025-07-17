# Recipe Website

A full-featured web application for managing, viewing, and importing recipes. Built with Flask, SQLAlchemy, and Selenium, it supports recipe import from URLs using AI-powered ingredient parsing.

---

## Features

- **Add, Edit, and View Recipes**: Store recipes with ingredients, instructions, and images.
- **Import Recipes from URL**: Scrape recipe sites and use OpenAI to parse ingredients.
- **Random Recipe**: Get a random recipe suggestion.
- **Recipe Cart**: Add recipes to a cart for meal planning or shopping.
- **Image Uploads**: Attach images to your recipes.
- **Modern UI**: Responsive, dark-themed interface using Bootstrap 5.

---

## Installation & Setup

### 1. System Requirements
- Python 3.7+
- Ubuntu (or any Linux with Python and Chrome)

### 2. Install System Dependencies
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv chromium-browser chromium-chromedriver unzip -y
```

### 3. Clone the Repository
```bash
git clone <your-repo-url> recipe-website
cd recipe-website
```

### 4. Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Set Environment Variables
Create a `.env` file in the project root:
```
OPENAI_API_KEY=sk-...
```
Or export it in your shell:
```bash
export OPENAI_API_KEY=sk-...
```

### 6. Initialize the Database
```bash
python3 app.py
# This will create the database and tables. Press Ctrl+C after it starts if you want to run it as a service.
```

### 7. Run the App (Development)
```bash
python3 app.py
# Visit http://localhost:5000
```

---

## Running 24/7 (Production)

### Using Gunicorn + systemd

1. **Install Gunicorn:**
   ```bash
   pip install gunicorn
   ```
2. **Create a systemd Service File:**
   Example: `/etc/systemd/system/recipe-website.service`
   ```ini
   [Unit]
   Description=Recipe Website Flask App
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/recipe-website
   Environment="PATH=/home/ubuntu/recipe-website/venv/bin"
   EnvironmentFile=/home/ubuntu/recipe-website/.env
   ExecStart=/home/ubuntu/recipe-website/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app

   [Install]
   WantedBy=multi-user.target
   ```
   Adjust paths and user as needed.
3. **Enable and Start the Service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable recipe-website
   sudo systemctl start recipe-website
   sudo systemctl status recipe-website
   ```

### (Optional) Nginx Reverse Proxy
For production, use Nginx to proxy requests to Gunicorn.

---

## Usage
- Access the site at `http://localhost:5000` (or your server's IP/domain).
- Use the navigation bar to add, view, or import recipes.
- Import recipes from supported URLs using the "Import" button.
- Add recipes to your cart for planning.

---

## Notes
- **OpenAI API Key**: Required for ingredient parsing when importing recipes from URLs.
- **Chrome/Chromium**: Selenium uses headless Chrome for scraping. Ensure `chromium-browser` and `chromium-chromedriver` are installed.
- **Database**: Uses SQLite by default (`instance/recipes.db`).

---

## License
MIT License