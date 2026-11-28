import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from calculator import (
    UTILITY_RATES,
    calculate_household_bill,
    simulate_comparison
)
from database import (
    init_db,
    create_user,
    authenticate_user,
    save_profile,
    get_user_profiles,
    delete_profile
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "enertrack-dev-secret-key-change-me")
init_db()

APPLIANCE_PRESETS = [
    {"name": "Stand Fan (Standard)", "watts": 65, "default_hours": 10, "category": "Cooling"},
    {"name": "DC Inverter Stand Fan", "watts": 30, "default_hours": 10, "category": "Cooling"},
    {"name": "Non-Inverter Aircon (1.0 HP)", "watts": 900, "default_hours": 8, "category": "Cooling"},
    {"name": "Inverter Aircon (1.0 HP)", "watts": 600, "default_hours": 8, "category": "Cooling"},
    {"name": "Refrigerator (Two-Door Inverter)", "watts": 120, "default_hours": 24, "category": "Kitchen"},
    {"name": "Refrigerator (Standard)", "watts": 180, "default_hours": 24, "category": "Kitchen"},
    {"name": "Rice Cooker (Cooking Mode)", "watts": 700, "default_hours": 1, "category": "Kitchen"},
    {"name": "Electric Kettle", "watts": 1500, "default_hours": 0.5, "category": "Kitchen"},
    {"name": "LED TV (43-inch)", "watts": 75, "default_hours": 5, "category": "Entertainment"},
    {"name": "Desktop Computer + Monitor", "watts": 250, "default_hours": 6, "category": "Work/Study"},
    {"name": "Laptop", "watts": 65, "default_hours": 6, "category": "Work/Study"},
    {"name": "LED Light Bulb (9W)", "watts": 9, "default_hours": 8, "category": "Lighting"},
    {"name": "Washing Machine (Top Load)", "watts": 500, "default_hours": 1, "category": "Laundry"},
    {"name": "Flat Iron", "watts": 1000, "default_hours": 0.5, "category": "Laundry"}
]

ENERGY_TIPS = [
    {
        "category": "Cooling",
        "title": "Set Aircon to 24°C–25°C with Fan Assist",
        "detail": "Every 1°C lower increases aircon power draw by 6–10%. Pairing a 25°C aircon with a 30W DC fan circulates cool air for much less electricity."
    },
    {
        "category": "Kitchen",
        "title": "Avoid Leaving the Rice Cooker on 'Keep Warm'",
        "detail": "A rice cooker on 'Keep Warm' still draws 40–70W continuously. Unplug it once rice is cooked and reheat portions as needed."
    },
    {
        "category": "Kitchen",
        "title": "Keep Refrigerator Coils Clean & Door Seals Tight",
        "detail": "Leave at least 3 inches of clearance behind the fridge so heat escapes easily, and avoid putting hot food directly inside."
    },
    {
        "category": "Standby Power",
        "title": "Unplug 'Vampire' Electronics",
        "detail": "TVs, microwave displays, and chargers still draw phantom power when plugged in. Use power strips with switches to cut standby load."
    },
    {
        "category": "Laundry",
        "title": "Iron Clothes in One Weekly Batch",
        "detail": "Heating up a 1,000W flat iron takes the most electricity. Ironing everything in a single session avoids repeated heat-up cycles."
    }
]


def generate_personalized_tips(calculated_result):
    appliances = calculated_result.get("appliances", [])
    if not appliances:
        return []

    dynamic_tips = []
    # Sort appliances from highest kWh to lowest so the biggest energy hogs appear first
    sorted_apps = sorted(appliances, key=lambda x: x["kwh"], reverse=True)

    for app_item in sorted_apps:
        name = app_item["name"]
        lower_name = name.lower()
        watts = app_item["watts"]
        hours = app_item["hours"]
        cost = app_item["total_cost"]

        # 1. Non-Inverter Aircon -> Inverter Upgrade Tip
        if ("aircon" in lower_name or "ac" in lower_name) and "non-inverter" in lower_name and watts >= 750:
            est_savings = round(cost * 0.35, 2)
            dynamic_tips.append({
                "category": "Cooling Upgrade",
                "appliance": name,
                "priority": "High Impact",
                "title": f"Upgrade '{name}' to an Inverter Unit",
                "detail": f"Your {watts}W non-inverter aircon runs {hours} hrs/day (₱{cost:,.2f}/mo). Switching to a 1.0 HP inverter can save ~₱{est_savings:,.2f}/month."
            })

        # 2. Any Aircon with Long Daily Hours -> Thermostat & Timer Tip
        elif ("aircon" in lower_name or "ac" in lower_name) and hours >= 6:
            est_savings = round(cost * 0.15, 2)
            dynamic_tips.append({
                "category": "Cooling Habit",
                "appliance": name,
                "priority": "High Impact",
                "title": f"Set '{name}' to 25°C & Use Sleep Timer",
                "detail": f"Running for {hours} hrs/day makes this a major load. Raising the thermostat to 25°C and cutting 1 hour via timer saves ~₱{est_savings:,.2f}/month."
            })

        # 3. Standard Stand Fan -> DC Inverter Fan Tip
        elif "fan" in lower_name and watts >= 55 and hours >= 8:
            est_savings = round(cost * (1 - (30 / watts)), 2)
            dynamic_tips.append({
                "category": "Cooling Upgrade",
                "appliance": name,
                "priority": "Smart Swap",
                "title": f"Switch '{name}' to a 30W DC Fan",
                "detail": f"At {watts}W for {hours} hrs/day, replacing this with a 30W DC inverter fan cuts its cost by more than half (~₱{est_savings:,.2f}/month saved)."
            })

        # 4. Old / High-Wattage Refrigerator -> Efficiency Check
        elif ("fridge" in lower_name or "refrigerator" in lower_name) and watts >= 150:
            est_savings = round(cost * 0.30, 2)
            dynamic_tips.append({
                "category": "Kitchen",
                "appliance": name,
                "priority": "High Impact",
                "title": f"Check Door Seals & Coils on '{name}'",
                "detail": f"Continuous 24/7 draw at {watts}W costs ₱{cost:,.2f}/mo. Keep 3 inches of back clearance, or consider an inverter model to save ~₱{est_savings:,.2f}/month."
            })

        # 5. Rice Cooker -> Keep Warm Warning
        elif "rice cooker" in lower_name and hours >= 2:
            est_savings = round(cost * 0.50, 2)
            dynamic_tips.append({
                "category": "Kitchen",
                "appliance": name,
                "priority": "Quick Win",
                "title": f"Unplug '{name}' After Cooking",
                "detail": f"You logged {hours} hrs/day—if part of that is 'Keep Warm' mode, unplugging after cooking saves ~₱{est_savings:,.2f}/month."
            })

        # 6. High-Wattage Heating Appliances (Iron, Kettle, Heater)
        elif watts >= 1000 and hours >= 0.5:
            est_savings = round(cost * 0.20, 2)
            dynamic_tips.append({
                "category": "High-Wattage Load",
                "appliance": name,
                "priority": "Quick Win",
                "title": f"Batch Usage for '{name}' ({watts}W)",
                "detail": f"High-wattage heating elements spike demand during startup. Batching usage into fewer sessions saves ~₱{est_savings:,.2f}/month."
            })

        # 7. Work/Entertainment Devices Left On Long Hours
        elif any(k in lower_name for k in ["desktop", "pc", "tv", "monitor", "computer", "laptop"]) and hours >= 6:
            est_savings = round(cost * 0.25, 2)
            dynamic_tips.append({
                "category": "Standby & Screen",
                "appliance": name,
                "priority": "Smart Habit",
                "title": f"Enable Auto-Sleep & Eco Brightness on '{name}'",
                "detail": f"Running {hours} hrs/day costs ₱{cost:,.2f}/mo. Enabling 10-minute sleep timers and lowering brightness saves ~₱{est_savings:,.2f}/month."
            })

    # Fallback general tips if user has fewer than 3 specific matches
    if len(dynamic_tips) < 3:
        for fallback in ENERGY_TIPS:
            if len(dynamic_tips) >= 6:
                break
            dynamic_tips.append({
                "category": fallback["category"],
                "appliance": "General Household",
                "priority": "General Tip",
                "title": fallback["title"],
                "detail": fallback["detail"]
            })

    return dynamic_tips[:6]


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not full_name or not email or "@" not in email or len(password) < 6:
            flash("Please provide your name, a valid email, and a password (at least 6 characters).", "danger")
            return render_template("register.html")

        user_id = create_user(full_name, email, password)
        if not user_id:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        session["user_id"] = user_id
        session["user_name"] = full_name
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(email, password)

        if not user:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template(
        "index.html",
        user_name=session.get("user_name"),
        utilities=UTILITY_RATES,
        presets=APPLIANCE_PRESETS,
        tips=ENERGY_TIPS
    )


@app.route("/api/calculate", methods=["POST"])
@login_required
def api_calculate():
    try:
        data = request.get_json(force=True) or {}
        result = calculate_household_bill(
            appliances=data.get("appliances", []),
            utility_code=data.get("utility_code", "BATELEC_II"),
            custom_rate=data.get("custom_rate"),
            days=int(data.get("days", 30)),
            dormmates=int(data.get("dormmates", 2))
        )
        result["tips"] = generate_personalized_tips(result)
        return jsonify(result)
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid calculation input: {e}"}), 400


@app.route("/api/simulate", methods=["POST"])
@login_required
def api_simulate():
    try:
        data = request.get_json(force=True) or {}
        result = simulate_comparison(
            normal_appliances=data.get("normal_appliances", []),
            saving_appliances=data.get("saving_appliances", []),
            utility_code=data.get("utility_code", "BATELEC_II"),
            custom_rate=data.get("custom_rate"),
            days=int(data.get("days", 30)),
            dormmates=int(data.get("dormmates", 2))
        )
        return jsonify(result)
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid simulation input: {e}"}), 400


@app.route("/api/what-if", methods=["POST"])
@login_required
def api_what_if():
    try:
        data = request.get_json(force=True) or {}
        utility_code = data.get("utility_code", "BATELEC_II")
        custom_rate = data.get("custom_rate")
        old_days = int(data.get("old_days", 30))
        new_days = int(data.get("new_days", old_days))

        before = calculate_household_bill(
            [{"name": data.get("name", "Current"), "watts": float(data["old_watts"]), "hours": float(data["old_hours"]), "days": old_days}],
            utility_code=utility_code,
            custom_rate=custom_rate
        )
        after = calculate_household_bill(
            [{"name": data.get("new_name", "Updated"), "watts": float(data["new_watts"]), "hours": float(data["new_hours"]), "days": new_days}],
            utility_code=utility_code,
            custom_rate=custom_rate
        )

        diff_kwh = round(after["total_kwh"] - before["total_kwh"], 2)
        diff_cost = round(after["total_cost_with_fees"] - before["total_cost_with_fees"], 2)

        return jsonify({
            "old_cost": before["total_cost_with_fees"],
            "new_cost": after["total_cost_with_fees"],
            "kwh_change": diff_kwh,
            "monthly_bill_change": diff_cost,
            "annual_bill_change": round(diff_cost * 12, 2)
        })
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid What-If parameters: {e}"}), 400


@app.route("/api/profiles", methods=["GET"])
@login_required
def api_get_profiles():
    return jsonify(get_user_profiles(session["user_id"]))


@app.route("/api/profiles", methods=["POST"])
@login_required
def api_save_profile():
    data = request.get_json(force=True) or {}
    name = data.get("profile_name", "").strip()
    if not name:
        return jsonify({"error": "Profile name is required"}), 400

    new_id = save_profile(
        user_id=session["user_id"],
        profile_name=name,
        utility_code=data.get("utility_code", "BATELEC_II"),
        appliances=data.get("appliances", [])
    )
    return jsonify({"id": new_id, "message": "Profile saved!"}), 201


@app.route("/api/profiles/<int:profile_id>", methods=["DELETE"])
@login_required
def api_delete_profile(profile_id):
    deleted = delete_profile(session["user_id"], profile_id)
    if not deleted:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"message": "Profile deleted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)