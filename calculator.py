UTILITY_RATES = {
    "BATELEC_I": {
        "name": "BATELEC I (Batangas I)",
        "base_rate": 6.71,
        "other_charges": 3.60,
        "non_vat_charges": 0.00,
        "vat_rate": 0.12,
        "fixed_monthly_fee": 5.60
    },
    "BATELEC_II": {
        "name": "BATELEC II (Batangas II - Mainland)",
        "base_rate": 6.9724,
        "other_charges": 2.1627,
        "non_vat_charges": 1.5576,
        "vat_rate": 0.10914,
        "fixed_monthly_fee": 5.00
    },
    "MERALCO": {
        "name": "Meralco",
        "base_rate": 10.63,
        "other_charges": 3.29,
        "non_vat_charges": 0.00,
        "vat_rate": 0.12,
        "fixed_monthly_fee": 5.60
    }
}


def calculate_household_bill(appliances, utility_code="BATELEC_II", custom_rate=None, days=30, dormmates=2):
    default_days = max(1, int(days or 30))
    dormmates = max(1, int(dormmates or 2))

    if isinstance(custom_rate, dict) and custom_rate:
        rate_info = custom_rate
    else:
        rate_info = UTILITY_RATES.get(utility_code, UTILITY_RATES["BATELEC_II"])

    base_rate = max(0.0, float(rate_info.get("base_rate", 0)))
    other_charges = max(0.0, float(rate_info.get("other_charges", 0)))
    non_vat_charges = max(0.0, float(rate_info.get("non_vat_charges", 0)))
    vat_rate = max(0.0, float(rate_info.get("vat_rate", 0.12)))
    fixed_fee = max(0.0, float(rate_info.get("fixed_monthly_fee", 5.00)))

    total_kwh = 0.0
    shared_cost = 0.0
    personal_totals = {}
    itemized = []

    for item in appliances:
        watts = max(0.0, float(item.get("watts", 0)))
        hours = min(24.0, max(0.0, float(item.get("hours", 0))))
        active_days = min(30, max(1, int(item.get("days", default_days))))
        owner = str(item.get("owner", "Shared")).strip() or "Shared"

        kwh = (watts * hours * active_days) / 1000.0
        total_kwh += kwh

        item_base = kwh * base_rate
        item_other = kwh * other_charges
        item_non_vat = kwh * non_vat_charges
        item_vat = (item_base + item_other) * vat_rate
        item_total = item_base + item_other + item_vat + item_non_vat

        if owner == "Shared":
            shared_cost += item_total
        else:
            personal_totals[owner] = personal_totals.get(owner, 0.0) + item_total

        itemized.append({
            "name": str(item.get("name", "Appliance")).strip() or "Appliance",
            "watts": watts,
            "hours": hours,
            "days": active_days,
            "owner": owner,
            "kwh": round(kwh, 2),
            "base_cost": round(item_base, 2),
            "total_cost": round(item_total, 2)
        })

    cost_without_fees = total_kwh * base_rate
    other_cost = total_kwh * other_charges
    non_vat_cost = total_kwh * non_vat_charges
    applied_fixed = fixed_fee if total_kwh > 0 else 0.0

    vatable_subtotal = cost_without_fees + other_cost + applied_fixed
    vat_amount = vatable_subtotal * vat_rate
    total_cost_with_fees = vatable_subtotal + vat_amount + non_vat_cost
    fees_and_taxes = total_cost_with_fees - cost_without_fees

    # Dormmate fair-share calculation (Shared items + Fixed fee split equally)
    fixed_with_vat = applied_fixed * (1 + vat_rate)
    shared_pool_total = shared_cost + fixed_with_vat
    equal_shared_per_person = shared_pool_total / dormmates

    dormmate_shares = [
        {
            "owner": owner,
            "personal_cost": round(p_cost, 2),
            "shared_portion": round(equal_shared_per_person, 2),
            "total_due": round(p_cost + equal_shared_per_person, 2)
        }
        for owner, p_cost in personal_totals.items()
    ]

    return {
        "utility_name": rate_info.get("name", utility_code),
        "days": default_days,
        "dormmates": dormmates,
        "total_kwh": round(total_kwh, 2),
        "cost_without_fees": round(cost_without_fees, 2),
        "fees_and_taxes": round(fees_and_taxes, 2),
        "total_cost_with_fees": round(total_cost_with_fees, 2),
        "shared_pool_total": round(shared_pool_total, 2),
        "equal_shared_per_person": round(equal_shared_per_person, 2),
        "dormmate_shares": dormmate_shares,
        "appliances": itemized
    }


def simulate_comparison(normal_appliances, saving_appliances, utility_code="BATELEC_II", custom_rate=None, days=30, dormmates=2):
    normal = calculate_household_bill(
        normal_appliances, utility_code=utility_code, custom_rate=custom_rate, days=days, dormmates=dormmates
    )
    saving = calculate_household_bill(
        saving_appliances, utility_code=utility_code, custom_rate=custom_rate, days=days, dormmates=dormmates
    )

    kwh_saved = round(normal["total_kwh"] - saving["total_kwh"], 2)
    money_saved = round(normal["total_cost_with_fees"] - saving["total_cost_with_fees"], 2)
    percent_saved = round((money_saved / normal["total_cost_with_fees"]) * 100, 1) if normal["total_cost_with_fees"] > 0 else 0.0

    return {
        "normal": normal,
        "energy_saving": saving,
        "kwh_saved": kwh_saved,
        "money_saved": money_saved,
        "percent_saved": percent_saved
    }