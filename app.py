import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import pymysql
from dotenv import load_dotenv
from datetime import date

load_dotenv()
app = Flask(__name__)

def get_db():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=3
    )

def init_db():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS equipment (
                    equipment_id INT AUTO_INCREMENT PRIMARY KEY,
                    equipment_name VARCHAR(100) NOT NULL,
                    serial_number VARCHAR(50) UNIQUE NOT NULL,
                    department VARCHAR(100),
                    purchase_date DATE,
                    status VARCHAR(50) DEFAULT 'Active'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_log (
                    log_id INT AUTO_INCREMENT PRIMARY KEY,
                    equipment_id INT,
                    maintenance_date DATE,
                    technician_name VARCHAR(100),
                    issue_reported TEXT,
                    resolution_notes TEXT,
                    next_due_date DATE,
                    FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id)
                )
            """)
        conn.commit()
        conn.close()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"⚠ Database connection error: {e}")
        print("  Check your .env file and ensure the MySQL server is running.")

@app.route("/")
def dashboard():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM equipment")
        total = cur.fetchone()["total"]
        cur.execute("SELECT status, COUNT(*) as count FROM equipment GROUP BY status")
        by_status = cur.fetchall()
        cur.execute("""
            SELECT e.equipment_name, e.serial_number, e.department, m.next_due_date
            FROM maintenance_log m
            JOIN equipment e ON m.equipment_id = e.equipment_id
            WHERE m.next_due_date < CURDATE()
        """)
        overdue = cur.fetchall()
    conn.close()
    return render_template("dashboard.html", total=total, by_status=by_status, overdue=overdue)

@app.route("/equipment")
def equipment_list():
    dept = request.args.get("department", "")
    status = request.args.get("status", "")
    conn = get_db()
    with conn.cursor() as cur:
        query = "SELECT * FROM equipment WHERE 1=1"
        params = []
        if dept:
            query += " AND department = %s"
            params.append(dept)
        if status:
            query += " AND status = %s"
            params.append(status)
        cur.execute(query, params)
        equipment = cur.fetchall()
    conn.close()
    return render_template("equipment_list.html", equipment=equipment, dept=dept, status=status)

@app.route("/equipment/add", methods=["GET", "POST"])
def add_equipment():
    if request.method == "POST":
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO equipment (equipment_name, serial_number, department, purchase_date, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (request.form["equipment_name"], request.form["serial_number"],
                  request.form["department"], request.form["purchase_date"], request.form["status"]))
        conn.commit()
        conn.close()
        return redirect(url_for("equipment_list"))
    return render_template("add_equipment.html")

@app.route("/equipment/<int:eid>")
def equipment_detail(eid):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM equipment WHERE equipment_id = %s", (eid,))
        equip = cur.fetchone()
        cur.execute("SELECT * FROM maintenance_log WHERE equipment_id = %s ORDER BY maintenance_date DESC", (eid,))
        logs = cur.fetchall()
    conn.close()
    return render_template("equipment_detail.html", equip=equip, logs=logs)

@app.route("/equipment/<int:eid>/status", methods=["POST"])
def update_status(eid):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("UPDATE equipment SET status = %s WHERE equipment_id = %s",
                    (request.form["status"], eid))
    conn.commit()
    conn.close()
    return redirect(url_for("equipment_detail", eid=eid))

@app.route("/maintenance/add/<int:eid>", methods=["GET", "POST"])
def add_maintenance(eid):
    if request.method == "POST":
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO maintenance_log (equipment_id, maintenance_date, technician_name,
                    issue_reported, resolution_notes, next_due_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (eid, request.form["maintenance_date"], request.form["technician_name"],
                  request.form["issue_reported"], request.form["resolution_notes"],
                  request.form["next_due_date"]))
        conn.commit()
        conn.close()
        return redirect(url_for("equipment_detail", eid=eid))
    return render_template("add_maintenance.html", eid=eid)

# Stretch goal
@app.route("/api/overdue")
def overdue_json():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.equipment_name, e.serial_number, e.department, m.next_due_date, m.technician_name
            FROM maintenance_log m
            JOIN equipment e ON m.equipment_id = e.equipment_id
            WHERE m.next_due_date < CURDATE()
        """)
        overdue = cur.fetchall()
    conn.close()
    for row in overdue:
        if row.get("next_due_date"):
            row["next_due_date"] = str(row["next_due_date"])
    return jsonify(overdue)

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port = 5000,debug=True)