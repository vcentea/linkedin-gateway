# Remote Chrome on Hetzner — Simple Step-by-Step

> Goal: spin up a tiny cloud computer that opens Chrome (with your extension) in your local browser via a secure tunnel.

---

## What you need

* A **Hetzner Cloud** account (console.hetzner.cloud).
* The **cloud-init** file you already have (you’ll paste its contents).
* A computer:

  * **Windows 10/11** (built-in OpenSSH is fine), or
  * **macOS / Linux** (Terminal app).

---

## 1) Create the server on Hetzner

1. Log in to **Hetzner Cloud Console**.
2. Create (or pick) a **Project**.
3. Click **Add Server**.
4. Choose:

   * **Location:** any (closest to you is faster).
   * **Image:** **Ubuntu 24.04 LTS** (recommended) or 22.04.
   * **Type:** e.g. **CX22** (2 vCPU / 4 GB RAM). Smaller works, but this feels smooth.
5. **User data (cloud-init):**

   * Expand **User data** → change selector to **cloud-config**.
   * Open your saved cloud-init file, copy everything, **paste** it into the box.
6. **SSH key or password:**

   * If you already have an SSH key in Hetzner, select it.
   * If not, choose **Password**; Hetzner will set a **root** password and show it after creation.
7. Click **Create & Buy Now**. Wait ~1–2 minutes.

> Keep the server’s **public IP** handy (shown in the server list/details).

---

## 2) Connect the secure tunnel (from your computer)

You’ll open a small “pipe” from your laptop to the server, then load the remote Chrome in your normal browser.

### Windows 10/11

1. Open **PowerShell**.
2. Run (replace `SERVER_IP`):

   ```powershell
   ssh -N -T -L 6901:127.0.0.1:6901 chrome@SERVER_IP
   ```

   * When asked for a password, type: **ChromeUser#2025**
   * Keep this window **open** (it’s the tunnel).

> If the above user doesn’t exist (only on very old setups), use `root@SERVER_IP` and the **root password** shown in Hetzner; the rest is identical.

### macOS / Linux

1. Open **Terminal**.
2. Run:

   ```bash
   ssh -N -T -L 6901:127.0.0.1:6901 chrome@SERVER_IP
   ```

   * Password: **ChromeUser#2025**
   * Keep Terminal **open**.

---

## 3) Open the remote Chrome

1. In your local browser, go to **[https://localhost:6901](https://localhost:6901)**

   * It’s **HTTPS** with a **self-signed** certificate → your browser will warn you. Click **Advanced** → **Proceed**.
2. Login:

   * **Username:** `kasm_user`
   * **Password:** `Rc2025!!`
3. You’ll land in the Chrome session. It opens **LinkedIn** by default, and the **LinkedIn Gateway** extension is already installed and pinned.

> Leave the PowerShell/Terminal window running while you use Chrome. Closing it closes the tunnel.

---

## 4) Everyday use (quick recap)

* Start tunnel:

  * Windows: open PowerShell → `ssh -N -T -L 6901:127.0.0.1:6901 chrome@SERVER_IP`
  * macOS/Linux: open Terminal → same command
* Open **[https://localhost:6901](https://localhost:6901)**
* Login: `kasm_user` / `Rc2025!!`
* Do your thing. Close the SSH window when done.

---

## 5) (Optional) One-click launcher for Windows

Create a file named `RemoteChrome.bat` on your desktop (right-click → New → Text Document → rename to `.bat`), put this inside (edit the IP):

```bat
@echo off
set SERVER_IP=YOUR.SERVER.IP.HERE
start "" powershell -NoExit -Command "ssh -N -T -L 6901:127.0.0.1:6901 chrome@%SERVER_IP%"
timeout /t 2 >nul
start "" https://localhost:6901
```

Double-click it any time to connect and open.

---

## 6) Troubleshooting (fast)

* **Browser says “didn’t send any data”**

  * Make sure you used **[https://localhost:6901](https://localhost:6901)** (not `http`).
  * Check the tunnel window is still **open** (no errors).

* **Login box appears but password fails**

  * Use **kasm_user** (or **kasm-user** if the first doesn’t work) and password **Rc2025!!**.

* **Blank page or can’t connect**

  1. On the server (Hetzner console → “Open SSH on server” button, or your own SSH):

     ```bash
     systemctl status kasm-chrome --no-pager
     docker ps
     ss -ltnp | grep 6901
     ```

     You should see:

     * `kasm-chrome.service` **active (running)**
     * a `kasmweb/chrome` container **Up**
     * a listener on **127.0.0.1:6901**
  2. If needed, restart:

     ```bash
     sudo systemctl restart kasm-chrome
     ```

* **Reset the Chrome profile (start fresh)**

  ```bash
  sudo systemctl stop kasm-chrome
  sudo rm -rf /opt/kasm/data
  sudo install -d -o 1000 -g 1000 -m 0775 /opt/kasm/data
  sudo systemctl start kasm-chrome
  ```

---

## 7) Cost & housekeeping

* You pay while the server exists. When you don’t need it:

  * **Shut down** to stop compute charges (disks still billed), or
  * **Delete the server** to stop all charges.
* Data you create in Chrome is stored under `/opt/kasm/data` on the server. Deleting the server deletes that data too.

---

## 8) Security notes (plain English)

* The Chrome UI is **not public**; it only listens on the server’s **loopback** (127.0.0.1). You can reach it **only** through your SSH tunnel.
* The login uses a random self-signed cert; your browser warns you because it’s not from a public CA. That’s expected here.
* If you prefer key-based SSH later (no passwords), we can add your public key and disable password logins.
