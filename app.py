from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, redirect, session, send_file
from flask_socketio import SocketIO, emit
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15
from Crypto.PublicKey import RSA
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
import sqlite3
import os
import shutil

app = Flask(__name__)
app.secret_key = "super-secure-secret-key-123"
socketio = SocketIO(app, async_mode="gevent")

# =========================
# MASTER ENCRYPTION KEY
# =========================
FERNET_KEY_FILE = "server_secret.key"
if not os.path.exists(FERNET_KEY_FILE):
    with open(FERNET_KEY_FILE, "wb") as f:
        f.write(Fernet.generate_key())

with open(FERNET_KEY_FILE, "rb") as f:
    SERVER_SECRET_KEY = f.read()

cipher_suite = Fernet(SERVER_SECRET_KEY)

# =========================
# DATABASE SETUP
# =========================
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS requests(sender TEXT, receiver TEXT, status TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS friends(user1 TEXT, user2 TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS messages(sender TEXT, receiver TEXT, message TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS shared_files(sender TEXT, receiver TEXT, filename TEXT)")

cursor.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT NOT NULL, admin TEXT NOT NULL)")
cursor.execute("CREATE TABLE IF NOT EXISTS group_members (group_id INTEGER, username TEXT, FOREIGN KEY(group_id) REFERENCES groups(id))")
cursor.execute("CREATE TABLE IF NOT EXISTS group_files (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, sender TEXT, filename TEXT, allowed_users TEXT)")
# TABLE FOR GROUP INVITATIONS
cursor.execute("CREATE TABLE IF NOT EXISTS group_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, sender TEXT, receiver TEXT, status TEXT)")
# Per-user group chat clear: stores the highest message rowid the user had cleared up to
cursor.execute("""CREATE TABLE IF NOT EXISTS group_chat_clears
    (group_id INTEGER, username TEXT, cleared_before_rowid INTEGER,
     PRIMARY KEY (group_id, username))""")
# Member-suggested invites awaiting admin approval
cursor.execute("""CREATE TABLE IF NOT EXISTS group_invite_suggestions
    (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER,
     suggested_by TEXT, suggested_user TEXT, status TEXT DEFAULT 'pending_admin')""")

conn.commit()
conn.close()

# =========================
# AUTHENTICATION
# =========================
@app.route("/")
def home():
    return redirect("/login")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = generate_password_hash(password)
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users(username, password) VALUES(?, ?)", (username, hashed_pw))
            conn.commit()
            user_folder = f"keys/{username}/default_key"
            os.makedirs(user_folder, exist_ok=True)
            key = RSA.generate(2048)
            with open(f"{user_folder}/private.pem", "wb") as f:
                f.write(key.export_key())
            with open(f"{user_folder}/public.pem", "wb") as f:
                f.write(key.publickey().export_key())
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists"
        conn.close()
        return redirect("/login")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            session["username"] = username
            return redirect("/dashboard")
        else:
            return "Invalid Username or Password"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

# =========================
# DASHBOARD & SEARCH
# =========================
@app.route("/dashboard")
def dashboard():
    if "username" not in session: return redirect("/login")
    return render_template("dashboard.html", username=session["username"])

@app.route("/search_page")
def search_page():
    if "username" not in session: return redirect("/login")
    return render_template("search_users.html")

@app.route("/search_users", methods=["POST"])
def search_users():
    if "username" not in session: return redirect("/login")
    search = request.form["search"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username=?", (search,))
    user = cursor.fetchone()
    conn.close()
    if user: return render_template("search_users.html", found_user=search)
    return render_template("search_users.html", message="User not found")

# =========================
# FRIEND REQUESTS & PAGE
# =========================
@app.route("/send_request/<receiver>")
def send_request(receiver):
    # BUG FIX 1: Added session guard
    if "username" not in session: return redirect("/login")
    sender = session["username"]

    # BUG FIX 2: Prevent self-requests and duplicate requests
    if sender == receiver:
        return redirect("/friends_page")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Check for existing pending request or existing friendship
    cursor.execute(
        "SELECT 1 FROM requests WHERE sender=? AND receiver=? AND status='pending'",
        (sender, receiver)
    )
    if cursor.fetchone():
        conn.close()
        return redirect("/friends_page")

    cursor.execute(
        "SELECT 1 FROM friends WHERE (user1=? AND user2=?) OR (user1=? AND user2=?)",
        (sender, receiver, receiver, sender)
    )
    if cursor.fetchone():
        conn.close()
        return redirect("/friends_page")

    conn.execute(
        "INSERT INTO requests(sender, receiver, status) VALUES(?, ?, ?)",
        (sender, receiver, "pending")
    )
    conn.commit()
    conn.close()
    return redirect("/friends_page")

@app.route("/accept/<sender>")
def accept(sender):
    # BUG FIX 3: Added session guard
    if "username" not in session: return redirect("/login")
    receiver = session["username"]
    conn = sqlite3.connect("users.db")
    conn.execute("INSERT INTO friends(user1, user2) VALUES(?, ?)", (sender, receiver))
    conn.execute("UPDATE requests SET status='accepted' WHERE sender=? AND receiver=?", (sender, receiver))
    conn.commit()
    conn.close()
    def auto_exchange_keys(u1, u2):
        src = f"keys/{u1}/default_key/public.pem"
        dst_dir = f"public_keys/{u2}/{u1}"
        if os.path.exists(src):
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copyfile(src, f"{dst_dir}/default_key.pem")
    auto_exchange_keys(sender, receiver)
    auto_exchange_keys(receiver, sender)
    return redirect("/friends_page")

@app.route("/reject/<sender>")
def reject(sender):
    # BUG FIX 4: Added session guard
    if "username" not in session: return redirect("/login")
    receiver = session["username"]
    conn = sqlite3.connect("users.db")
    conn.execute("DELETE FROM requests WHERE sender=? AND receiver=?", (sender, receiver))
    conn.commit()
    conn.close()
    return redirect("/friends_page")

@app.route("/friends_page")
def friends_page():
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # 1. Friend Requests
    cursor.execute("SELECT sender FROM requests WHERE receiver=? AND status='pending'", (username,))
    friend_requests = cursor.fetchall()

    # 2. Friends List
    cursor.execute("SELECT user1, user2 FROM friends WHERE user1=? OR user2=?", (username, username))
    friends_raw = cursor.fetchall()
    friends = [f[1] if f[0] == username else f[0] for f in friends_raw]

    # 3. Group Invitations
    cursor.execute("""
        SELECT gr.id, g.group_name, gr.sender 
        FROM group_requests gr 
        JOIN groups g ON gr.group_id = g.id 
        WHERE gr.receiver=? AND gr.status='pending'
    """, (username,))
    group_requests = cursor.fetchall()

    conn.close()
    return render_template("friends.html", requests=friend_requests, friends=friends, group_requests=group_requests)

# =========================
# CHAT SYSTEM (1-on-1)
# =========================
@app.route("/chat/<friend>")
def chat(friend):
    # BUG FIX 5: Added missing session guard
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, receiver, message FROM messages WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)",
        (username, friend, friend, username)
    )
    raw_messages = cursor.fetchall()
    messages = []
    for msg in raw_messages:
        try:
            messages.append((msg[0], msg[1], cipher_suite.decrypt(msg[2].encode()).decode()))
        except:
            messages.append((msg[0], msg[1], "[Encrypted/Corrupted Message]"))
    cursor.execute(
        "SELECT sender, filename FROM shared_files WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)",
        (username, friend, friend, username)
    )
    shared_files = cursor.fetchall()
    conn.close()
    return render_template("chat.html", username=username, friend=friend, messages=messages, shared_files=shared_files)

@app.route("/clear_chat/<friend>", methods=["POST"])
def clear_chat(friend):
    # BUG FIX 6: Added missing session guard
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    conn.execute(
        "DELETE FROM messages WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)",
        (username, friend, friend, username)
    )
    conn.execute(
        "DELETE FROM shared_files WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)",
        (username, friend, friend, username)
    )
    conn.commit()
    conn.close()
    return redirect(f"/chat/{friend}")

@app.route("/upload_chat_file/<friend>", methods=["POST"])
def upload_chat_file(friend):
    # BUG FIX 7: Added missing session guard
    if "username" not in session: return redirect("/login")
    username = session["username"]
    file = request.files["file"]
    if not file or file.filename == "": return redirect(f"/chat/{friend}")
    file_data = file.read()
    filename = secure_filename(file.filename)
    aes_key = get_random_bytes(16)
    cipher_aes = AES.new(aes_key, AES.MODE_EAX)
    ciphertext, tag = cipher_aes.encrypt_and_digest(file_data)
    with open(f"public_keys/{username}/{friend}/default_key.pem", "rb") as f:
        pub_key = RSA.import_key(f.read())
    encrypted_key = PKCS1_OAEP.new(pub_key).encrypt(aes_key)
    with open(f"keys/{username}/default_key/private.pem", "rb") as f:
        priv_key = RSA.import_key(f.read())
    signature = pkcs1_15.new(priv_key).sign(SHA256.new(file_data))
    # File is saved in the RECEIVER's folder so they can download it
    save_folder = f"shared_encrypted_files/{friend}"
    os.makedirs(save_folder, exist_ok=True)
    secure_filename_out = f"{filename}.secure"
    with open(f"{save_folder}/{secure_filename_out}", "wb") as f:
        f.write(len(filename.encode()).to_bytes(4, 'big'))
        f.write(filename.encode())
        f.write(len(encrypted_key).to_bytes(4, 'big'))
        f.write(encrypted_key)
        f.write(len(signature).to_bytes(4, 'big'))
        f.write(signature)
        f.write(cipher_aes.nonce)
        f.write(tag)
        f.write(ciphertext)
    conn = sqlite3.connect("users.db")
    conn.execute(
        "INSERT INTO shared_files(sender, receiver, filename) VALUES(?, ?, ?)",
        (username, friend, secure_filename_out)
    )
    conn.commit()
    conn.close()
    return redirect(f"/chat/{friend}")

@app.route("/download_chat_file/<filename>")
def download_chat_file(filename):
    # BUG FIX 8: Added missing session guard
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender FROM shared_files WHERE (receiver=? AND filename=?) OR (sender=? AND filename=?)",
        (username, filename, username, filename)
    )
    row = cursor.fetchone()
    conn.close()
    if not row: return "Access Denied", 403

    sender = row[0]

    # BUG FIX 9: Corrected folder_owner logic.
    # Files are always saved under the RECEIVER's folder in upload_chat_file.
    # - If the current user is the receiver, the file is in their own folder.
    # - If the current user is the sender re-downloading, the file is in the other user's folder.
    if sender == username:
        # Current user is the sender; file lives in the receiver's folder.
        # We need to find who the receiver is.
        conn2 = sqlite3.connect("users.db")
        cur2 = conn2.cursor()
        cur2.execute(
            "SELECT receiver FROM shared_files WHERE sender=? AND filename=?",
            (username, filename)
        )
        recv_row = cur2.fetchone()
        conn2.close()
        folder_owner = recv_row[0] if recv_row else username
    else:
        # Current user is the receiver; file lives in their folder.
        folder_owner = username

    file_path = f"shared_encrypted_files/{folder_owner}/{filename}"

    if not os.path.exists(file_path):
        return "File not found on server.", 404

    # BUG FIX 10: Corrected binary read order.
    # Original code called f.read(int.from_bytes(f.read(4), 'big')) which reads
    # the content BEFORE reading the 4-byte length prefix — completely wrong order.
    # Correct order: read length first, then read that many bytes.
    with open(file_path, "rb") as f:
        name_len = int.from_bytes(f.read(4), 'big')
        orig_name = f.read(name_len).decode()
        key_len = int.from_bytes(f.read(4), 'big')
        enc_key = f.read(key_len)
        sig_len = int.from_bytes(f.read(4), 'big')
        signature = f.read(sig_len)
        nonce = f.read(16)
        tag = f.read(16)
        ciphertext = f.read()

    with open(f"keys/{username}/default_key/private.pem", "rb") as f:
        aes_key = PKCS1_OAEP.new(RSA.import_key(f.read())).decrypt(enc_key)

    data = AES.new(aes_key, AES.MODE_EAX, nonce=nonce).decrypt_and_verify(ciphertext, tag)

    with open(f"public_keys/{username}/{sender}/default_key.pem", "rb") as f:
        pkcs1_15.new(RSA.import_key(f.read())).verify(SHA256.new(data), signature)

    out_dir = f"decrypted_files/{username}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/{orig_name}"
    with open(out_path, "wb") as f:
        f.write(data)
    return send_file(out_path, as_attachment=True)


# =========================
# GROUPS SYSTEM (Chat & Granular Files)
# =========================
@app.route("/groups")
def groups():
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT groups.id, groups.group_name, groups.admin 
        FROM groups JOIN group_members ON groups.id = group_members.group_id 
        WHERE group_members.username = ?
    """, (username,))
    my_groups = cursor.fetchall()

    cursor.execute("SELECT user1, user2 FROM friends WHERE user1=? OR user2=?", (username, username))
    friends_raw = cursor.fetchall()
    friends = [f[1] if f[0] == username else f[0] for f in friends_raw]
    conn.close()
    return render_template("groups.html", groups=my_groups, friends=friends)

@app.route("/create_group", methods=["POST"])
def create_group():
    if "username" not in session: return redirect("/login")
    username = session["username"]
    group_name = request.form["group_name"]
    selected_friends = request.form.getlist("members")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO groups(group_name, admin) VALUES(?, ?)", (group_name, username))
    group_id = cursor.lastrowid

    # Auto-add the admin to the group
    cursor.execute("INSERT INTO group_members(group_id, username) VALUES(?, ?)", (group_id, username))

    # Send group requests to friends instead of adding directly
    for friend in selected_friends:
        cursor.execute(
            "INSERT INTO group_requests(group_id, sender, receiver, status) VALUES(?, ?, ?, 'pending')",
            (group_id, username, friend)
        )

    conn.commit()
    conn.close()
    return redirect("/groups")

@app.route("/invite_group_members/<int:group_id>", methods=["POST"])
def invite_group_members(group_id):
    if "username" not in session: return redirect("/login")
    username = session["username"]
    selected_friends = request.form.getlist("members")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    for friend in selected_friends:
        cursor.execute(
            "SELECT * FROM group_requests WHERE group_id=? AND receiver=? AND status='pending'",
            (group_id, friend)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO group_requests(group_id, sender, receiver, status) VALUES(?, ?, ?, 'pending')",
                (group_id, username, friend)
            )
    conn.commit()
    conn.close()
    return redirect(f"/group/{group_id}")

@app.route("/accept_group/<int:req_id>")
def accept_group(req_id):
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT group_id, receiver FROM group_requests WHERE id=?", (req_id,))
    req = cursor.fetchone()
    if req and req[1] == username:
        cursor.execute("INSERT INTO group_members(group_id, username) VALUES(?, ?)", (req[0], username))
        cursor.execute("DELETE FROM group_requests WHERE id=?", (req_id,))
        conn.commit()
    conn.close()
    return redirect("/friends_page")

@app.route("/reject_group/<int:req_id>")
def reject_group(req_id):
    if "username" not in session: return redirect("/login")
    conn = sqlite3.connect("users.db")
    conn.execute("DELETE FROM group_requests WHERE id=?", (req_id,))
    conn.commit()
    conn.close()
    return redirect("/friends_page")

@app.route("/group/<int:group_id>")
def group_page(group_id):
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM group_members WHERE group_id=? AND username=?", (group_id, username))
    if not cursor.fetchone():
        conn.close()
        return "Access Denied: You are not a member of this group."

    cursor.execute("SELECT group_name, admin FROM groups WHERE id=?", (group_id,))
    group_info = cursor.fetchone()

    # Get all members
    cursor.execute("SELECT username FROM group_members WHERE group_id=?", (group_id,))
    all_members = [m[0] for m in cursor.fetchall()]
    share_members = [m for m in all_members if m != username]

    # Get friends not in group yet
    cursor.execute("SELECT user1, user2 FROM friends WHERE user1=? OR user2=?", (username, username))
    friends_raw = cursor.fetchall()
    my_friends = [f[1] if f[0] == username else f[0] for f in friends_raw]
    inviteable_friends = [f for f in my_friends if f not in all_members]

    # Get per-user clear threshold (hide messages at or before this rowid)
    cursor.execute(
        "SELECT cleared_before_rowid FROM group_chat_clears WHERE group_id=? AND username=?",
        (group_id, username)
    )
    clear_row = cursor.fetchone()
    cleared_before_rowid = clear_row[0] if clear_row else 0

    cursor.execute(
        "SELECT rowid, sender, message FROM messages WHERE receiver=? AND rowid > ?",
        (f"group_{group_id}", cleared_before_rowid)
    )
    raw_messages = cursor.fetchall()
    messages = []
    for msg in raw_messages:
        try:
            messages.append((msg[1], cipher_suite.decrypt(msg[2].encode()).decode()))
        except:
            messages.append((msg[1], "[Encrypted/Corrupted Message]"))

    cursor.execute("SELECT sender, filename, allowed_users FROM group_files WHERE group_id=?", (group_id,))
    all_files = cursor.fetchall()
    shared_files = []
    for f in all_files:
        allowed_list = f[2].split(",")
        if username in allowed_list or username == f[0]:
            shared_files.append((f[0], f[1]))

    # Pending member-suggested invites (only shown to admin)
    pending_suggestions = []
    if username == group_info[1]:  # is admin
        cursor.execute(
            "SELECT id, suggested_by, suggested_user FROM group_invite_suggestions WHERE group_id=? AND status='pending_admin'",
            (group_id,)
        )
        pending_suggestions = cursor.fetchall()

    conn.close()
    return render_template(
        "group_chat.html",
        group_id=group_id,
        group_name=group_info[0],
        admin=group_info[1],
        username=username,
        all_members=all_members,
        share_members=share_members,
        inviteable_friends=inviteable_friends,
        messages=messages,
        shared_files=shared_files,
        pending_suggestions=pending_suggestions
    )

@app.route("/upload_group_file/<int:group_id>", methods=["POST"])
def upload_group_file(group_id):
    if "username" not in session: return redirect("/login")
    username = session["username"]
    file = request.files["file"]
    selected_members = request.form.getlist("allowed_users")

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        allowed_users_str = ",".join(selected_members)
        save_folder = f"group_files/{group_id}"
        os.makedirs(save_folder, exist_ok=True)
        file.save(f"{save_folder}/{filename}")
        conn = sqlite3.connect("users.db")
        conn.execute(
            "INSERT INTO group_files (group_id, sender, filename, allowed_users) VALUES (?, ?, ?, ?)",
            (group_id, username, filename, allowed_users_str)
        )
        conn.commit()
        conn.close()
    return redirect(f"/group/{group_id}")

@app.route("/clear_group_chat/<int:group_id>", methods=["POST"])
def clear_group_chat(group_id):
    """Per-user clear — like WhatsApp. Only hides messages for the requesting user.
    Records the current highest message rowid as their clear threshold.
    Other members are completely unaffected."""
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Verify the user is actually a member
    cursor.execute("SELECT 1 FROM group_members WHERE group_id=? AND username=?", (group_id, username))
    if not cursor.fetchone():
        conn.close()
        return "Access Denied.", 403

    # Find the highest current message rowid for this group
    cursor.execute(
        "SELECT MAX(rowid) FROM messages WHERE receiver=?",
        (f"group_{group_id}",)
    )
    result = cursor.fetchone()
    max_rowid = result[0] if result[0] is not None else 0

    # Upsert the clear threshold for this user
    cursor.execute("""
        INSERT INTO group_chat_clears (group_id, username, cleared_before_rowid)
        VALUES (?, ?, ?)
        ON CONFLICT(group_id, username) DO UPDATE SET cleared_before_rowid=excluded.cleared_before_rowid
    """, (group_id, username, max_rowid))

    conn.commit()
    conn.close()
    return redirect(f"/group/{group_id}")


# =========================
# MEMBER-SUGGESTED INVITES
# =========================
@app.route("/suggest_group_member/<int:group_id>", methods=["POST"])
def suggest_group_member(group_id):
    """Any group member can suggest a friend to be added.
    Creates a pending_admin record that only the admin sees."""
    if "username" not in session: return redirect("/login")
    username = session["username"]
    suggested_user = request.form.get("suggested_user", "").strip()

    if not suggested_user or suggested_user == username:
        return redirect(f"/group/{group_id}")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Must be a member to suggest
    cursor.execute("SELECT 1 FROM group_members WHERE group_id=? AND username=?", (group_id, username))
    if not cursor.fetchone():
        conn.close()
        return "Access Denied.", 403

    # Suggested user must exist
    cursor.execute("SELECT 1 FROM users WHERE username=?", (suggested_user,))
    if not cursor.fetchone():
        conn.close()
        return redirect(f"/group/{group_id}")

    # Must not already be a member
    cursor.execute("SELECT 1 FROM group_members WHERE group_id=? AND username=?", (group_id, suggested_user))
    if cursor.fetchone():
        conn.close()
        return redirect(f"/group/{group_id}")

    # No duplicate pending suggestion
    cursor.execute(
        "SELECT 1 FROM group_invite_suggestions WHERE group_id=? AND suggested_user=? AND status='pending_admin'",
        (group_id, suggested_user)
    )
    if cursor.fetchone():
        conn.close()
        return redirect(f"/group/{group_id}")

    cursor.execute(
        "INSERT INTO group_invite_suggestions (group_id, suggested_by, suggested_user, status) VALUES (?,?,?,'pending_admin')",
        (group_id, username, suggested_user)
    )
    conn.commit()
    conn.close()
    return redirect(f"/group/{group_id}")


@app.route("/approve_suggestion/<int:suggestion_id>")
def approve_suggestion(suggestion_id):
    """Admin approves a member-suggested invite.
    Marks the suggestion approved and sends the actual group invite to the target user."""
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT group_id, suggested_user FROM group_invite_suggestions WHERE id=? AND status='pending_admin'",
        (suggestion_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return redirect("/groups")

    group_id, suggested_user = row

    # Only admin can approve
    cursor.execute("SELECT admin FROM groups WHERE id=?", (group_id,))
    admin_row = cursor.fetchone()
    if not admin_row or admin_row[0] != username:
        conn.close()
        return "Access Denied.", 403

    # Mark suggestion as approved
    cursor.execute(
        "UPDATE group_invite_suggestions SET status='approved' WHERE id=?",
        (suggestion_id,)
    )

    # Send the actual group invite (reuse existing group_requests flow)
    cursor.execute(
        "SELECT 1 FROM group_requests WHERE group_id=? AND receiver=? AND status='pending'",
        (group_id, suggested_user)
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO group_requests (group_id, sender, receiver, status) VALUES (?,?,?,'pending')",
            (group_id, username, suggested_user)
        )

    conn.commit()
    conn.close()
    return redirect(f"/group/{group_id}")


@app.route("/reject_suggestion/<int:suggestion_id>")
def reject_suggestion(suggestion_id):
    """Admin rejects a member-suggested invite."""
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT group_id FROM group_invite_suggestions WHERE id=? AND status='pending_admin'",
        (suggestion_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return redirect("/groups")

    group_id = row[0]

    cursor.execute("SELECT admin FROM groups WHERE id=?", (group_id,))
    admin_row = cursor.fetchone()
    if not admin_row or admin_row[0] != username:
        conn.close()
        return "Access Denied.", 403

    cursor.execute(
        "UPDATE group_invite_suggestions SET status='rejected' WHERE id=?",
        (suggestion_id,)
    )
    conn.commit()
    conn.close()
    return redirect(f"/group/{group_id}")

@app.route("/download_group_file/<int:group_id>/<filename>")
def download_group_file(group_id, filename):
    if "username" not in session: return redirect("/login")
    username = session["username"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT allowed_users, sender FROM group_files WHERE group_id=? AND filename=?",
        (group_id, filename)
    )
    row = cursor.fetchone()
    conn.close()

    if not row: return "File not found.", 404
    allowed_users = row[0].split(",")
    sender = row[1]
    if username not in allowed_users and username != sender:
        return "Access Denied: You do not have permission to view this file.", 403

    file_path = f"group_files/{group_id}/{filename}"
    if not os.path.exists(file_path):
        return "File not found on server.", 404
    return send_file(file_path, as_attachment=True)

@socketio.on("send_message")
def handle_message(data):
    sender = data.get("sender", "")
    receiver = data.get("receiver", "")
    message = data.get("message", "")
    if not sender or not receiver or not message:
        return
    encrypted_msg = cipher_suite.encrypt(message.encode()).decode()
    conn = sqlite3.connect("users.db")
    conn.execute(
        "INSERT INTO messages(sender, receiver, message) VALUES(?, ?, ?)",
        (sender, receiver, encrypted_msg)
    )
    conn.commit()
    conn.close()
    emit("receive_message", {"sender": sender, "receiver": receiver, "message": message}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)