# Publishing the Magazine Accounts site on Render (with PostgreSQL)

The same program now runs in two ways:
* **Office PC (as now):** no `DATABASE_URL` set -> uses the file `subscribers.db`.
* **Online (Render):** `DATABASE_URL` is set -> uses PostgreSQL. Nothing else in the program changes.

Cost (Render price list, Oct 2026): web service Starter about **$7/month** + PostgreSQL 256 MB about **$6/month**; the Hobby workspace is $0.
A free web service exists but it goes to sleep when nobody uses it (first page takes ~1 minute to wake up).

## Step 1 - Prepare the project on your PC
1. Copy the files of this update into `F:\Magazine_app` (replace `app.py`, `db.py`, `import_access.py`, `requirements.txt`; add `render.yaml`, `.gitignore`, `requirements-access.txt`; replace the `templates` folder). Keep `subscribers.db` and `.venv`.
2. In the VS Code terminal:  `pip install -r requirements.txt`   (adds the PostgreSQL driver)
3. Start `python app.py` and check the site still works as before.

## Step 2 - Put the code on GitHub (private repository)
Same as your inventory app:
```
cd F:\Magazine_app
git init
git add .
git commit -m "Magazine accounts"
git branch -M main
git remote add origin https://github.com/<your-name>/magazine-accounts.git
git push -u origin main
```
(Create the empty **private** repository on github.com first. `.gitignore` keeps your database and the .mdb file OUT of GitHub - subscriber data must never go to GitHub.)

## Step 3 - Create the site on Render
1. render.com -> **New +** -> **Blueprint** -> connect the GitHub repository.
2. Render reads `render.yaml` and shows a database `magazine-db` and a web service `magazine-accounts`.
3. It asks for two values: **ADMIN_USERNAME** and **ADMIN_PASSWORD** (the first administrator login). Type them, press **Apply**.
4. Wait for the first deploy (about 3-5 minutes) until it says **Live**. Your address is like `https://magazine-accounts.onrender.com`.

## Step 4 - Copy your existing data to the online database
1. Render dashboard -> `magazine-db` -> **Connections** -> copy the **External Database URL**.
2. In the VS Code terminal (PowerShell) on your PC:
```
$env:DATABASE_URL="PASTE-THE-EXTERNAL-URL-HERE"
python -m flask --app app init-db
python -m flask --app app migrate-sqlite subscribers.db --force
```
It prints how many jamaats, users, subscribers and payments were copied (compare with your local site).
`--force` replaces the temporary admin by your real users (same usernames and passwords as on the office PC).
3. Close that PowerShell window (so `DATABASE_URL` is forgotten) and open your Render address. Log in.

## Step 5 - From now on
* **Enter data in ONE place only.** After you go online, use the Render site; do not keep adding data to the office `subscribers.db`.
* Updates: change the code, `git add .`, `git commit -m "..."`, `git push` -> Render redeploys automatically.
* **Backups:** every month download the Excel reports (Jama'at-wise list -> Download Excel) and keep them. Also check the backup options of your Render database plan in the Render dashboard.
* Share the address with Jama'at users; create their logins on the site (Admin -> Users). The site uses https automatically.

## If something goes wrong
* Render dashboard -> `magazine-accounts` -> **Logs** shows the error.
* "relation does not exist" -> run `python -m flask --app app init-db` with the External Database URL as in Step 4.
* Login not working after migrating -> the usernames/passwords are the ones from the office database.
