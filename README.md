# Smart Canteen Ordering System

A final-year BCA project prototype:

**QR scan → menu → cart → demo payment → order code → preparation → ready → collection**

## Features

- Student login
- Digital menu
- Cart and quantity management
- Demo payment confirmation
- Automatic order/parcel code
- Student order history
- Admin login
- Add menu items
- Enable/disable menu items
- View incoming orders
- Update Pending / Preparing / Ready / Collected
- Verify order code during collection
- SQLite database

## Run on Windows

1. Install Python 3.11+.
2. Open this project folder in VS Code.
3. Create a virtual environment:

   `python -m venv venv`

4. Activate it:

   `venv\Scripts\activate`

5. Install dependencies:

   `pip install -r requirements.txt`

6. Start the application:

   `python app.py`

7. Open:

   `http://127.0.0.1:5000`

## Demo accounts

Admin:
- Email: admin@canteen.local
- Password: admin123

Student:
- Email: student@canteen.local
- Password: student123

## Deploy to Render

This project is configured for a Python web service.

### If your GitHub repository contains:

`Smart-Canteen/app.py`

then in Render set:

- **Root Directory:** `Smart-Canteen`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`

If `app.py` is directly in the GitHub repository root, leave **Root Directory** empty and use the same Build and Start Commands.

The HTML files must remain inside:

`templates/`

especially:

`templates/index.html`

The static files must remain inside:

`static/`

### Important

Do not set the Root Directory to `templates`.

Do not use `python app.py` as the production Start Command when deploying through Gunicorn.

The included `Procfile` also contains:

`web: gunicorn app:app`

## Demo payment

The payment flow is a DEMO payment. It does not charge real money.

For production, passwords should be hashed and a real payment provider should be integrated through its official SDK/API.

## Database note

This prototype uses SQLite. On many cloud platforms, local SQLite storage is not persistent across all redeploy/restart scenarios. For a production canteen system, move the database to a managed PostgreSQL/MySQL database.
