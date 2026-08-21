import frappe


def _p(
	code,
	name,
	main,
	secondary,
	series,
	thickness,
	glass,
	rate,
	minimum=0,
	operable_rate=0,
	approval_reason=None,
):
	return {
		"item_code": code,
		"item_name": name,
		"main": main,
		"secondary": secondary,
		"series": series,
		"thickness": thickness,
		"glass": glass,
		"rate": rate,
		"minimum": minimum,
		"operable_rate": operable_rate,
		"approval_reason": approval_reason,
	}


PRODUCTS = [
	_p(
		"OTEC-WIN-110-AWNING",
		"110 System Awning Window",
		"Windows",
		"Awning Window",
		"110 System",
		1.8,
		"5mm + 20A + 5mm",
		8400,
		1.35,
		11400,
	),
	_p(
		"OTEC-WIN-110-CASEMENT",
		"110 System Casement Window",
		"Windows",
		"Casement Window",
		"110 System",
		1.8,
		"5mm + 20A + 5mm",
		8400,
		1.35,
		11400,
	),
	_p(
		"OTEC-WIN-110-FIXED",
		"110 System Fixed Window",
		"Windows",
		"Fixed Window",
		"110 System",
		1.8,
		"5mm + 20A + 5mm",
		8400,
		1.35,
	),
	_p(
		"OTEC-WIN-70-AWNING",
		"70 Series Awning Window",
		"Windows",
		"Awning Window",
		"70 Series",
		1.8,
		"5mm + 20A + 5mm",
		7400,
		1.35,
		6700,
	),
	_p(
		"OTEC-WIN-70-CASEMENT",
		"70 Series Casement Window",
		"Windows",
		"Casement Window",
		"70 Series",
		1.8,
		"5mm + 20A + 5mm",
		7400,
		1.35,
		6700,
	),
	_p(
		"OTEC-WIN-70-FIXED",
		"70 Series Fixed Window",
		"Windows",
		"Fixed Window",
		"70 Series",
		1.8,
		"5mm + 20A + 5mm",
		7200,
		1.35,
	),
	_p(
		"OTEC-WIN-SLIDE-80-2T",
		"Sliding Window 2 Tracks (80 Series)",
		"Windows",
		"Sliding Window",
		"80 Series - 2 Tracks",
		2,
		"5mm + 14A + 5mm",
		9614,
		1,
	),
	_p(
		"OTEC-WIN-SLIDE-120-3T",
		"Sliding Window 3 Tracks (120 Series)",
		"Windows",
		"Sliding Window",
		"120 Series - 3 Tracks",
		2,
		"5mm + 14A + 5mm",
		11134,
		1,
	),
	_p(
		"OTEC-WIN-SLIDEUP-83",
		"Slide Up Window (83 Series)",
		"Windows",
		"Slide Up Window",
		"83 Series",
		1.4,
		"5mm + 14A + 5mm",
		12380,
	),
	_p(
		"OTEC-WIN-FOLD-70",
		"Folding Window (70 Series)",
		"Windows",
		"Folding Window",
		"70 Series",
		1.6,
		"8mm",
		10860,
		2,
	),
	_p(
		"OTEC-WIN-FOLDUP-55",
		"Fold Up Window (55 Series)",
		"Windows",
		"Fold Up Window",
		"55 Series",
		1.4,
		"8mm",
		11620,
	),
	_p(
		"OTEC-WIN-FOLDUP-70",
		"Fold Up Window (70 Series)",
		"Windows",
		"Fold Up Window",
		"70 Series",
		1.4,
		"8mm",
		10860,
	),
	_p(
		"OTEC-WIN-LOUVER-70",
		"Glass Louver Window (70 Series)",
		"Windows",
		"Glass Louver",
		"70 Series",
		1.4,
		"6mm",
		15800,
		1.35,
	),
	_p(
		"OTEC-WIN-SWIVEL-115",
		"Swivel Window with/without Casement",
		"Windows",
		"Swivel Window",
		"115mm Frame",
		1.4,
		"5mm + 14A + 5mm",
		11400,
		0,
		14000,
	),
	_p(
		"OTEC-WIN-TILT-TURN",
		"Tilt and Turn Window",
		"Windows",
		"Tilt and Turn",
		"Standard",
		0,
		"5mm + 14A + 5mm",
		9400,
		0,
		7500,
		"Aluminum thickness is missing from the source price list.",
	),
	_p(
		"OTEC-DOOR-FOLD-68",
		"Folding Door (68 Series)",
		"Doors",
		"Folding Door",
		"68 Series",
		2,
		"5mm + 20A + 5mm",
		16415,
		1.6,
	),
	_p(
		"OTEC-DOOR-FOLD-NARROW-4516",
		"Folding Narrow Door (45x16)",
		"Doors",
		"Folding Door",
		"45x16 Narrow",
		2,
		"6mm",
		9345.6,
	),
	_p(
		"OTEC-DOOR-SLIDE-3565-2T",
		"Sliding Door 2 Tracks (35x65)",
		"Doors",
		"Sliding Door",
		"35x65 - 2 Tracks",
		2,
		"5mm + 14A + 5mm",
		10710,
		1.8,
	),
	_p(
		"OTEC-DOOR-SLIDE-3565-3T",
		"Sliding Door 3 Tracks (35x65)",
		"Doors",
		"Sliding Door",
		"35x65 - 3 Tracks",
		2,
		"5mm + 14A + 5mm",
		12160,
		1.8,
	),
	_p(
		"OTEC-DOOR-SLIDE-208-3T",
		"Sliding Door 3 Tracks (208 Series)",
		"Doors",
		"Sliding Door",
		"208 Series - 3 Tracks",
		2,
		"5mm + 20A + 5mm",
		14600,
	),
	_p(
		"OTEC-DOOR-SLIDE-135",
		"135 Series Sliding Door",
		"Doors",
		"Sliding Door",
		"135 Series",
		2,
		"6mm + 12A + 6mm",
		16300,
		0,
		0,
		"Source price list requires confirmation from Ar. Psalms.",
	),
	_p(
		"OTEC-DOOR-SWING-70",
		"Swing Door (70 Series)",
		"Doors",
		"Swing Door",
		"70 Series",
		1.8,
		"8mm",
		12000,
		1.8,
	),
	_p(
		"OTEC-DOOR-SWING-110-SCREEN",
		"Swing Door (110 Series) with Screen",
		"Doors",
		"Swing Door",
		"110 Series",
		1.4,
		"5mm + 14A + 5mm",
		9350,
		1.8,
		20000,
	),
	_p(
		"OTEC-DOOR-NARROW-FIXED",
		"Narrow Frame Fixed Partition",
		"Doors",
		"Narrow Frame",
		"45x16 Fixed",
		2,
		"8mm",
		6756,
	),
	_p(
		"OTEC-DOOR-NARROW-1T",
		"Narrow Frame 1 Track Sliding",
		"Doors",
		"Narrow Frame",
		"45x16 - 1 Track",
		2,
		"8mm",
		8585.6,
	),
	_p(
		"OTEC-DOOR-NARROW-3575-2T",
		"Narrow Frame 2 Tracks (35x75)",
		"Doors",
		"Narrow Frame",
		"35x75 - 2 Tracks",
		4,
		"5mm + 14A + 5mm",
		12850,
	),
	_p(
		"OTEC-DOOR-NARROW-3575-3T",
		"Narrow Frame 3 Tracks (35x75)",
		"Doors",
		"Narrow Frame",
		"35x75 - 3 Tracks",
		4,
		"5mm + 14A + 5mm",
		13100,
	),
	_p(
		"OTEC-DOOR-NARROW-2T",
		"Narrow Frame 2 Track Sliding",
		"Doors",
		"Narrow Frame",
		"45x16 - 2 Tracks",
		2,
		"8mm",
		8889.6,
	),
	_p(
		"OTEC-DOOR-TELE-3T-BOTTOM",
		"Telescopic 3 Track Sliding - Bottom Track",
		"Doors",
		"Telescopic Door",
		"3 Tracks - Bottom",
		2,
		"8mm",
		10561.6,
	),
	_p(
		"OTEC-DOOR-TELE-3T-NOBOTTOM",
		"Telescopic 3 Track Sliding - No Bottom Track",
		"Doors",
		"Telescopic Door",
		"3 Tracks - No Bottom",
		2,
		"8mm",
		10561.6,
	),
	_p(
		"OTEC-DOOR-TELE-4T-BOTTOM",
		"Telescopic 4 Track Sliding - Bottom Track",
		"Doors",
		"Telescopic Door",
		"4 Tracks - Bottom",
		2,
		"8mm",
		11017.6,
	),
	_p(
		"OTEC-DOOR-TELE-4T-NOBOTTOM",
		"Telescopic 4 Track Sliding - No Bottom Track",
		"Doors",
		"Telescopic Door",
		"4 Tracks - No Bottom",
		2,
		"8mm",
		11017.6,
	),
	_p(
		"OTEC-DOOR-TELE-5T",
		"Telescopic 5 Track Sliding",
		"Doors",
		"Telescopic Door",
		"5 Tracks",
		2,
		"8mm",
		11400,
	),
	_p(
		"OTEC-DOOR-TELE-6T",
		"Telescopic 6 Track Sliding",
		"Doors",
		"Telescopic Door",
		"6 Tracks",
		2,
		"8mm",
		12780,
	),
	_p(
		"OTEC-DOOR-PT-3550-2T",
		"PT Door (35x50) - 2 Tracks",
		"Doors",
		"PT Door",
		"35x50 - 2 Tracks",
		2,
		"5mm + 14A + 5mm",
		14544,
	),
	_p(
		"OTEC-DOOR-PT-3550-3T",
		"PT Door (35x50) - 3 Tracks",
		"Doors",
		"PT Door",
		"35x50 - 3 Tracks",
		2,
		"5mm + 14A + 5mm",
		17584,
	),
	_p(
		"OTEC-DOOR-PT-NARROW-4MM-2T",
		"Narrow Frame PT Door - 2 Tracks",
		"Doors",
		"PT Door",
		"Narrow 4mm - 2 Tracks",
		4,
		"5mm + 14A + 5mm",
		12850,
	),
	_p(
		"OTEC-DOOR-PT-NARROW-4MM-3T",
		"Narrow Frame PT Door - 3 Tracks",
		"Doors",
		"PT Door",
		"Narrow 4mm - 3 Tracks",
		4,
		"5mm + 14A + 5mm",
		13100,
		0,
		0,
		"The source workbook duplicated the 2-track label; normalized as 3 tracks.",
	),
	_p(
		"OTEC-DOOR-PT-3570-2T",
		"PT Door (35x70) - 2 Tracks",
		"Doors",
		"PT Door",
		"35x70 - 2 Tracks",
		2,
		"5mm + 14A + 5mm",
		13480,
	),
	_p(
		"OTEC-DOOR-PT-3570-3T",
		"PT Door (35x70) - 3 Tracks",
		"Doors",
		"PT Door",
		"35x70 - 3 Tracks",
		2,
		"5mm + 14A + 5mm",
		17584,
	),
	_p(
		"OTEC-DOOR-PT-NARROW-3516-2T",
		"Narrow Frame PT Door (35x16) - 2 Tracks",
		"Doors",
		"PT Door",
		"35x16 - 2 Tracks",
		2,
		"8mm",
		13480,
	),
	_p(
		"OTEC-DOOR-PT-NARROW-3516-3T",
		"Narrow Frame PT Door (35x16) - 3 Tracks",
		"Doors",
		"PT Door",
		"35x16 - 3 Tracks",
		2,
		"8mm",
		17584,
	),
	_p(
		"OTEC-DOOR-PIVOT-HEAVY",
		"Pivot Door - Heavy Duty",
		"Doors",
		"Pivot Door",
		"Heavy Duty",
		2,
		"8mm",
		15000,
		0,
		6840,
	),
	_p(
		"OTEC-DOOR-PIVOT-18",
		"Pivot Door - 18 Series Narrow",
		"Doors",
		"Pivot Door",
		"18 Series Narrow",
		3,
		"8mm",
		28680,
	),
	_p(
		"OTEC-DOOR-GHOST-60",
		"Ghost Door (60mm Frame)",
		"Doors",
		"Barn/Ghost Door",
		"60mm Frame",
		3,
		"8mm",
		10710,
	),
	_p(
		"OTEC-DOOR-SLIDE-SWING-1T",
		"Slide and Swing Door - 1 Track",
		"Doors",
		"Slide and Swing",
		"110mm Frame - 1 Track",
		2,
		"5mm + 12A + 5mm",
		12185,
		3,
	),
]


ADDONS = {
	"Integrated Grills": (2700, "Per SQM"),
	"High Visibility Metal Screen": (2500, "Per Panel"),
	"Fixed Metal Screen": (2500, "Per Panel"),
	"Key Lockset": (2500, "Per Piece"),
	"Key Lockset (Narrow)": (2000, "Per Piece"),
	"Pair of Big Handles": (2000, "Per Pair"),
	"Locksets (208 Series)": (8000, "Flat"),
	"Buffers / Soft Close": (1800, "Per Piece"),
	"Ground Rail Buffer": (960, "Per Piece"),
	"Handle Key Lock": (2000, "Per Piece"),
	"Linkage (No Bottom Track)": (6600, "Flat"),
	"Pocket Rail": (0, "Per SQM"),
	"Mirror Type Slim Profile": (2500, "Per SQM"),
	"Soft Screen": (4306, "Per SQM"),
	"Aluminum Strips in Insulated Glass": (800, "Per SQM"),
}

ALUMINUM_THICKNESSES = ("1.4", "1.6", "1.8", "2.0", "3.0", "4.0")
GLASS_TYPES = (
	"Laminated Glass",
	"Triple Glass",
	"Low-E Glass",
	"Reflective Glass",
	"Tinted Glass",
	"Bullet-proof Glass",
)
GLASS_COLORS = ("Clear", "Bronze", "Euro Gray", "Blue")


RULES = [
	*[
		(code, "Integrated Grills", "Per SQM")
		for code in ("OTEC-WIN-110-AWNING", "OTEC-WIN-110-CASEMENT", "OTEC-WIN-110-FIXED")
	],
	("OTEC-WIN-SLIDEUP-83", "High Visibility Metal Screen", "Per Panel"),
	("OTEC-WIN-LOUVER-70", "Fixed Metal Screen", "Per Panel"),
	("OTEC-DOOR-FOLD-68", "Key Lockset", "Per Piece"),
	("OTEC-DOOR-FOLD-NARROW-4516", "Key Lockset (Narrow)", "Per Piece"),
	("OTEC-DOOR-SLIDE-3565-3T", "Key Lockset", "Per Piece"),
	("OTEC-DOOR-SLIDE-3565-3T", "Pair of Big Handles", "Per Pair"),
	(
		"OTEC-DOOR-SLIDE-208-3T",
		"Locksets (208 Series)",
		"Flat",
		8000,
		True,
		"The source does not state whether ₱8,000 is per lockset or per row.",
	),
	("OTEC-DOOR-SWING-110-SCREEN", "Key Lockset", "Per Piece"),
	*[
		(code, "Buffers / Soft Close", "Per Piece")
		for code in (
			"OTEC-DOOR-NARROW-FIXED",
			"OTEC-DOOR-NARROW-1T",
			"OTEC-DOOR-NARROW-3575-2T",
			"OTEC-DOOR-NARROW-3575-3T",
			"OTEC-DOOR-NARROW-2T",
		)
	],
	*[
		(code, "Ground Rail Buffer", "Per Piece")
		for code in (
			"OTEC-DOOR-NARROW-FIXED",
			"OTEC-DOOR-NARROW-1T",
			"OTEC-DOOR-NARROW-3575-2T",
			"OTEC-DOOR-NARROW-3575-3T",
			"OTEC-DOOR-NARROW-2T",
		)
	],
	("OTEC-DOOR-TELE-3T-BOTTOM", "Handle Key Lock", "Per Piece"),
	("OTEC-DOOR-TELE-3T-NOBOTTOM", "Linkage (No Bottom Track)", "Flat"),
	("OTEC-DOOR-TELE-4T-BOTTOM", "Pocket Rail", "Per SQM", 1700),
	("OTEC-DOOR-TELE-4T-NOBOTTOM", "Pocket Rail", "Per SQM", 1700),
	(
		"OTEC-DOOR-TELE-5T",
		"Pocket Rail",
		"Per SQM",
		0,
		True,
		"No 5-track pocket rail rate is stated in the source.",
	),
	("OTEC-DOOR-GHOST-60", "Mirror Type Slim Profile", "Per SQM"),
	("OTEC-DOOR-SLIDE-SWING-1T", "Soft Screen", "Per SQM"),
]


def setup_catalog():
	_ensure_item_group()
	_seed_specification_masters()
	for product in PRODUCTS:
		_upsert_item(product)
		_upsert_configuration(product)
		_seed_item_specification_options(product["item_code"])
	_seed_addons()
	rules = list(RULES)
	for product in PRODUCTS:
		if "A +" in product["glass"]:
			rules.append((product["item_code"], "Aluminum Strips in Insulated Glass", "Per SQM"))
	for rule in rules:
		_upsert_rule(rule)
	_seed_approved_alternative_configurations()
	frappe.db.commit()


def _ensure_item_group():
	if not frappe.db.exists("Item Group", "OTEC Products"):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": "OTEC Products",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)


def _upsert_item(product):
	values = {
		"item_name": product["item_name"],
		"item_group": "OTEC Products",
		"stock_uom": "Nos",
		"is_stock_item": 0,
		"is_sales_item": 1,
		"custom_company": _otec_company(),
		"otec_main_product_category": product["main"],
		"otec_secondary_product_category": product["secondary"],
		"otec_series": product["series"],
		"otec_minimum_sqm": product["minimum"],
		"otec_sqm_rate": product["rate"],
		"otec_operable_available": 1 if product["operable_rate"] else 0,
		"otec_operable_rate": product["operable_rate"],
		"otec_aluminum_thickness": f"{float(product['thickness']):.1f}" if product["thickness"] else "",
		"otec_glass_specification": product["glass"],
		"otec_color": "Gray",
	}
	if frappe.db.exists("Item", product["item_code"]):
		frappe.db.set_value("Item", product["item_code"], values, update_modified=False)
	else:
		frappe.get_doc({"doctype": "Item", "item_code": product["item_code"], **values}).insert(
			ignore_permissions=True
		)


def _otec_company():
	preferred = "OTEC International Trade Corporation"
	if frappe.db.exists("Company", preferred):
		return preferred
	return frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value("Company")


def _upsert_configuration(product, suffix="STD", label=None, rate=None, approval_reason=None):
	code = f"{product['item_code']}-{suffix}"
	reason = approval_reason if approval_reason is not None else product.get("approval_reason")
	values = {
		"item_code": product["item_code"],
		"configuration_label": label or f"Standard {product['series']}",
		"active": 1,
		"is_default": 1 if suffix == "STD" else 0,
		"sqm_rate": product["rate"] if rate is None else rate,
		"operable_available": 1 if product["operable_rate"] else 0,
		"operable_rate": product["operable_rate"],
		"requires_approval": 1 if reason else 0,
		"approval_reason": reason,
	}
	if frappe.db.exists("OTEC Product Configuration", code):
		frappe.db.set_value("OTEC Product Configuration", code, values, update_modified=False)
	else:
		frappe.get_doc(
			{"doctype": "OTEC Product Configuration", "configuration_code": code, **values}
		).insert(ignore_permissions=True)


def _seed_specification_masters():
	pending = (
		"Rate pending OTEC confirmation. Pricing approval is required until a confirmed price is entered."
	)
	for thickness in ALUMINUM_THICKNESSES:
		_insert_missing_master(
			"OTEC Aluminum Thickness",
			thickness,
			{
				"thickness_code": thickness,
				"thickness_mm": float(thickness),
				"rate_per_sqm": 0,
				"active": 1,
				"requires_approval": 1,
				"approval_reason": pending,
			},
		)
	for glass_type in GLASS_TYPES:
		_insert_missing_master(
			"OTEC Glass Type",
			glass_type,
			{
				"glass_type": glass_type,
				"rate_per_sqm": 0,
				"active": 1,
				"requires_approval": 1,
				"approval_reason": pending,
			},
		)
	for color in GLASS_COLORS:
		values = {"glass_color": color, "rate_per_sqm": 0, "active": 1}
		if color == "Clear":
			values.update({"requires_approval": 0, "approval_reason": ""})
		else:
			values.update({"requires_approval": 1, "approval_reason": pending})
		_insert_missing_master("OTEC Glass Color", color, values)


def _insert_missing_master(doctype, name, values):
	# Never overwrite rates maintained by OTEC during a later migration.
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def _seed_item_specification_options(item_code):
	item = frappe.get_doc("Item", item_code)
	changed = False
	option_sets = (
		("otec_allowed_aluminum_thicknesses", "aluminum_thickness", ALUMINUM_THICKNESSES),
		("otec_allowed_glass_types", "glass_type", GLASS_TYPES),
		("otec_allowed_glass_colors", "glass_color", GLASS_COLORS),
	)
	for table_field, link_field, options in option_sets:
		if not item.get(table_field):
			for option in options:
				item.append(table_field, {link_field: option})
			changed = True
	if changed:
		item.save(ignore_permissions=True)


def _seed_addons():
	for name, (rate, basis) in ADDONS.items():
		values = {"rate": rate, "default_pricing_basis": basis, "active": 1}
		if frappe.db.exists("OTEC Add-on", name):
			frappe.db.set_value("OTEC Add-on", name, values, update_modified=False)
		else:
			frappe.get_doc({"doctype": "OTEC Add-on", "addon_name": name, **values}).insert(
				ignore_permissions=True
			)


def _upsert_rule(rule):
	item_code, add_on, basis, *optional = rule
	rate_override = optional[0] if optional else 0
	requires_approval = optional[1] if len(optional) > 1 else False
	notes = optional[2] if len(optional) > 2 else None
	rule_code = f"{item_code}::{add_on}"
	values = {
		"item_code": item_code,
		"add_on": add_on,
		"active": 1,
		"pricing_basis": basis,
		"rate_override": rate_override,
		"default_quantity": 1,
		"requires_approval": requires_approval,
		"notes": notes,
		"incompatible_add_ons": "Fixed Metal Screen, High Visibility Metal Screen"
		if add_on == "Soft Screen"
		else "",
	}
	if frappe.db.exists("OTEC Item Add-on Rule", rule_code):
		frappe.db.set_value("OTEC Item Add-on Rule", rule_code, values, update_modified=False)
	else:
		frappe.get_doc({"doctype": "OTEC Item Add-on Rule", "rule_code": rule_code, **values}).insert(
			ignore_permissions=True
		)


def _seed_approved_alternative_configurations():
	for item_code in ("OTEC-DOOR-PT-NARROW-3516-2T", "OTEC-DOOR-PT-NARROW-3516-3T"):
		product = next(p for p in PRODUCTS if p["item_code"] == item_code)
		_upsert_configuration(
			product,
			suffix="HALF-GLASS-ALUMINUM",
			label="Half Glass / Half Aluminum | Office confirmation required",
			rate=11500,
			approval_reason="The source lists ₱11,500/SQM but does not clearly distinguish the 2-track and 3-track application.",
		)
