"""
Local food database seed — 300+ common foods including Central Asian / Uzbek cuisine
and universal staples. Seeded into FoodCache on first boot so search works offline.
Nutrients are per 100g unless noted.
"""
from sqlalchemy.orm import Session
from backend.models.database import FoodCache


# Foods legitimately at all-zero macros (water-only / pure supplement powders).
# Anything else with all-zero macros must be rejected — that is C1's trust bug.
ZERO_MACRO_ALLOWED = {
    "Creatine Monohydrate (5g serving)",
    "Water",
}


def is_zero_macro(cal: float, pro: float, carb: float, fat: float) -> bool:
    return (cal or 0) == 0 and (pro or 0) == 0 and (carb or 0) == 0 and (fat or 0) == 0


FOOD_DATABASE = [
    # ─── PROTEINS ────────────────────────────────────────────────────────────
    {"name": "Chicken Breast (raw)", "cal": 120, "pro": 22.5, "carb": 0, "fat": 2.6, "fibre": 0},
    {"name": "Chicken Breast (grilled)", "cal": 165, "pro": 31, "carb": 0, "fat": 3.6, "fibre": 0},
    {"name": "Chicken Thigh (raw)", "cal": 177, "pro": 18.3, "carb": 0, "fat": 11.0, "fibre": 0},
    {"name": "Chicken Thigh (grilled)", "cal": 209, "pro": 26, "carb": 0, "fat": 11.5, "fibre": 0},
    {"name": "Beef Mince (lean 5%)", "cal": 137, "pro": 20.7, "carb": 0, "fat": 5.5, "fibre": 0},
    {"name": "Beef Mince (20% fat)", "cal": 215, "pro": 17.2, "carb": 0, "fat": 16.0, "fibre": 0},
    {"name": "Beef Steak (sirloin)", "cal": 207, "pro": 26, "carb": 0, "fat": 11, "fibre": 0},
    {"name": "Lamb (leg, raw)", "cal": 191, "pro": 20.8, "carb": 0, "fat": 11.6, "fibre": 0},
    {"name": "Lamb Chops (grilled)", "cal": 268, "pro": 25.5, "carb": 0, "fat": 17.9, "fibre": 0},
    {"name": "Pork Tenderloin", "cal": 143, "pro": 21.8, "carb": 0, "fat": 5.6, "fibre": 0},
    {"name": "Turkey Breast", "cal": 104, "pro": 21.9, "carb": 0, "fat": 1.2, "fibre": 0},
    {"name": "Salmon (raw)", "cal": 208, "pro": 20, "carb": 0, "fat": 13, "fibre": 0},
    {"name": "Tuna (canned in water)", "cal": 116, "pro": 26, "carb": 0, "fat": 1.0, "fibre": 0},
    {"name": "Tuna (canned in oil)", "cal": 198, "pro": 25.5, "carb": 0, "fat": 10.9, "fibre": 0},
    {"name": "Sardines (canned)", "cal": 208, "pro": 24.6, "carb": 0, "fat": 11.5, "fibre": 0},
    {"name": "Egg (whole)", "cal": 155, "pro": 12.6, "carb": 1.1, "fat": 10.6, "fibre": 0},
    {"name": "Egg White", "cal": 52, "pro": 10.9, "carb": 0.7, "fat": 0.2, "fibre": 0},
    {"name": "Egg Yolk", "cal": 322, "pro": 15.9, "carb": 3.6, "fat": 26.5, "fibre": 0},
    {"name": "Shrimp (raw)", "cal": 99, "pro": 18.9, "carb": 0.9, "fat": 1.7, "fibre": 0},
    {"name": "Greek Yoghurt (plain, 0%)", "cal": 59, "pro": 10, "carb": 3.6, "fat": 0.4, "fibre": 0},
    {"name": "Greek Yoghurt (2%)", "cal": 73, "pro": 9.9, "carb": 3.5, "fat": 1.9, "fibre": 0},
    {"name": "Cottage Cheese (low fat)", "cal": 72, "pro": 12.5, "carb": 2.7, "fat": 1.0, "fibre": 0},
    {"name": "Whey Protein Powder", "cal": 370, "pro": 75, "carb": 10, "fat": 4, "fibre": 0},
    {"name": "Casein Protein Powder", "cal": 358, "pro": 72, "carb": 10, "fat": 2.5, "fibre": 0},

    # ─── DAIRY ───────────────────────────────────────────────────────────────
    {"name": "Milk (whole)", "cal": 61, "pro": 3.2, "carb": 4.8, "fat": 3.3, "fibre": 0},
    {"name": "Milk (2%)", "cal": 50, "pro": 3.4, "carb": 4.9, "fat": 2.0, "fibre": 0},
    {"name": "Milk (skimmed)", "cal": 34, "pro": 3.4, "carb": 4.8, "fat": 0.1, "fibre": 0},
    {"name": "Cheddar Cheese", "cal": 402, "pro": 24.9, "carb": 1.3, "fat": 33.1, "fibre": 0},
    {"name": "Mozzarella (part skim)", "cal": 254, "pro": 24.3, "carb": 2.2, "fat": 15.9, "fibre": 0},
    {"name": "Feta Cheese", "cal": 264, "pro": 14.2, "carb": 4.1, "fat": 21.3, "fibre": 0},
    {"name": "Butter", "cal": 717, "pro": 0.9, "carb": 0.1, "fat": 81.1, "fibre": 0},
    {"name": "Kefir (plain)", "cal": 61, "pro": 3.5, "carb": 4.8, "fat": 3.3, "fibre": 0},

    # ─── GRAINS & CARBS ──────────────────────────────────────────────────────
    {"name": "White Rice (raw)", "cal": 365, "pro": 7.1, "carb": 80, "fat": 0.7, "fibre": 0.4},
    {"name": "White Rice (cooked)", "cal": 130, "pro": 2.7, "carb": 28.2, "fat": 0.3, "fibre": 0.4},
    {"name": "Brown Rice (raw)", "cal": 370, "pro": 7.9, "carb": 77.2, "fat": 2.9, "fibre": 3.5},
    {"name": "Brown Rice (cooked)", "cal": 111, "pro": 2.6, "carb": 23, "fat": 0.9, "fibre": 1.8},
    {"name": "Basmati Rice (cooked)", "cal": 121, "pro": 3.5, "carb": 25.2, "fat": 0.4, "fibre": 0.5},
    {"name": "Oats (rolled, dry)", "cal": 389, "pro": 16.9, "carb": 66.3, "fat": 6.9, "fibre": 10.6},
    {"name": "Oatmeal (cooked with water)", "cal": 71, "pro": 2.5, "carb": 12, "fat": 1.5, "fibre": 1.7},
    {"name": "Bread (white)", "cal": 265, "pro": 9.0, "carb": 49.4, "fat": 3.2, "fibre": 2.7},
    {"name": "Bread (whole wheat)", "cal": 247, "pro": 13.0, "carb": 41.3, "fat": 4.2, "fibre": 6.8},
    {"name": "Lavash (flatbread)", "cal": 277, "pro": 9.3, "carb": 54.4, "fat": 1.2, "fibre": 2.0},
    {"name": "Pasta (dry)", "cal": 371, "pro": 13.0, "carb": 74.7, "fat": 1.5, "fibre": 3.2},
    {"name": "Pasta (cooked)", "cal": 158, "pro": 5.8, "carb": 30.9, "fat": 0.9, "fibre": 1.8},
    {"name": "Quinoa (cooked)", "cal": 120, "pro": 4.4, "carb": 21.3, "fat": 1.9, "fibre": 2.8},
    {"name": "Bulgur (cooked)", "cal": 83, "pro": 3.1, "carb": 18.6, "fat": 0.2, "fibre": 4.5},
    {"name": "Buckwheat (raw)", "cal": 343, "pro": 13.3, "carb": 71.5, "fat": 3.4, "fibre": 10.0},
    {"name": "Buckwheat (cooked)", "cal": 92, "pro": 3.4, "carb": 19.9, "fat": 0.6, "fibre": 2.7},
    {"name": "Millet (cooked)", "cal": 119, "pro": 3.5, "carb": 23.7, "fat": 1.0, "fibre": 1.3},
    {"name": "Cornflakes", "cal": 357, "pro": 7.1, "carb": 80.9, "fat": 0.4, "fibre": 2.4},
    {"name": "Sweet Potato (raw)", "cal": 86, "pro": 1.6, "carb": 20.1, "fat": 0.1, "fibre": 3.0},
    {"name": "Sweet Potato (baked)", "cal": 90, "pro": 2.0, "carb": 20.7, "fat": 0.1, "fibre": 3.3},
    {"name": "Potato (boiled)", "cal": 87, "pro": 1.9, "carb": 20.1, "fat": 0.1, "fibre": 1.8},
    {"name": "Potato (baked)", "cal": 93, "pro": 2.5, "carb": 21.2, "fat": 0.1, "fibre": 2.2},
    {"name": "Potato (fried / chips)", "cal": 312, "pro": 3.4, "carb": 41.4, "fat": 15.0, "fibre": 3.8},

    # ─── VEGETABLES ──────────────────────────────────────────────────────────
    {"name": "Broccoli (raw)", "cal": 34, "pro": 2.8, "carb": 6.6, "fat": 0.4, "fibre": 2.6},
    {"name": "Spinach (raw)", "cal": 23, "pro": 2.9, "carb": 3.6, "fat": 0.4, "fibre": 2.2},
    {"name": "Cucumber", "cal": 15, "pro": 0.7, "carb": 3.6, "fat": 0.1, "fibre": 0.5},
    {"name": "Tomato", "cal": 18, "pro": 0.9, "carb": 3.9, "fat": 0.2, "fibre": 1.2},
    {"name": "Bell Pepper (red)", "cal": 31, "pro": 1.0, "carb": 6.0, "fat": 0.3, "fibre": 2.1},
    {"name": "Onion", "cal": 40, "pro": 1.1, "carb": 9.3, "fat": 0.1, "fibre": 1.7},
    {"name": "Garlic", "cal": 149, "pro": 6.4, "carb": 33.1, "fat": 0.5, "fibre": 2.1},
    {"name": "Carrot (raw)", "cal": 41, "pro": 0.9, "carb": 9.6, "fat": 0.2, "fibre": 2.8},
    {"name": "Cabbage (raw)", "cal": 25, "pro": 1.3, "carb": 5.8, "fat": 0.1, "fibre": 2.5},
    {"name": "Lettuce (iceberg)", "cal": 14, "pro": 0.9, "carb": 2.9, "fat": 0.1, "fibre": 1.2},
    {"name": "Avocado", "cal": 160, "pro": 2.0, "carb": 8.5, "fat": 14.7, "fibre": 6.7},
    {"name": "Mushrooms (white)", "cal": 22, "pro": 3.1, "carb": 3.3, "fat": 0.3, "fibre": 1.0},
    {"name": "Zucchini (raw)", "cal": 17, "pro": 1.2, "carb": 3.1, "fat": 0.3, "fibre": 1.0},
    {"name": "Eggplant (raw)", "cal": 25, "pro": 1.0, "carb": 5.9, "fat": 0.2, "fibre": 3.0},
    {"name": "Green Beans", "cal": 31, "pro": 1.8, "carb": 7.1, "fat": 0.1, "fibre": 3.4},
    {"name": "Cauliflower", "cal": 25, "pro": 1.9, "carb": 5.0, "fat": 0.3, "fibre": 2.0},
    {"name": "Asparagus", "cal": 20, "pro": 2.2, "carb": 3.9, "fat": 0.1, "fibre": 2.1},
    {"name": "Kale (raw)", "cal": 49, "pro": 4.3, "carb": 8.8, "fat": 0.9, "fibre": 3.6},

    # ─── FRUITS ──────────────────────────────────────────────────────────────
    {"name": "Banana", "cal": 89, "pro": 1.1, "carb": 22.8, "fat": 0.3, "fibre": 2.6},
    {"name": "Apple", "cal": 52, "pro": 0.3, "carb": 13.8, "fat": 0.2, "fibre": 2.4},
    {"name": "Orange", "cal": 47, "pro": 0.9, "carb": 11.8, "fat": 0.1, "fibre": 2.4},
    {"name": "Blueberries", "cal": 57, "pro": 0.7, "carb": 14.5, "fat": 0.3, "fibre": 2.4},
    {"name": "Strawberries", "cal": 32, "pro": 0.7, "carb": 7.7, "fat": 0.3, "fibre": 2.0},
    {"name": "Watermelon", "cal": 30, "pro": 0.6, "carb": 7.6, "fat": 0.2, "fibre": 0.4},
    {"name": "Grapes", "cal": 69, "pro": 0.7, "carb": 18.1, "fat": 0.2, "fibre": 0.9},
    {"name": "Mango", "cal": 60, "pro": 0.8, "carb": 15.0, "fat": 0.4, "fibre": 1.6},
    {"name": "Pomegranate", "cal": 83, "pro": 1.7, "carb": 18.7, "fat": 1.2, "fibre": 4.0},
    {"name": "Peach", "cal": 39, "pro": 0.9, "carb": 9.5, "fat": 0.3, "fibre": 1.5},
    {"name": "Pineapple", "cal": 50, "pro": 0.5, "carb": 13.1, "fat": 0.1, "fibre": 1.4},
    {"name": "Kiwi", "cal": 61, "pro": 1.1, "carb": 14.7, "fat": 0.5, "fibre": 3.0},
    {"name": "Lemon", "cal": 29, "pro": 1.1, "carb": 9.3, "fat": 0.3, "fibre": 2.8},
    {"name": "Dates (dried)", "cal": 277, "pro": 1.8, "carb": 75, "fat": 0.2, "fibre": 6.7},

    # ─── LEGUMES ─────────────────────────────────────────────────────────────
    {"name": "Chickpeas (cooked)", "cal": 164, "pro": 8.9, "carb": 27.4, "fat": 2.6, "fibre": 7.6},
    {"name": "Lentils (cooked)", "cal": 116, "pro": 9.0, "carb": 20.1, "fat": 0.4, "fibre": 7.9},
    {"name": "Black Beans (cooked)", "cal": 132, "pro": 8.9, "carb": 23.7, "fat": 0.5, "fibre": 8.7},
    {"name": "Kidney Beans (cooked)", "cal": 127, "pro": 8.7, "carb": 22.8, "fat": 0.5, "fibre": 6.4},
    {"name": "Soy Beans (cooked)", "cal": 173, "pro": 16.6, "carb": 9.9, "fat": 9.0, "fibre": 6.0},
    {"name": "Tofu (firm)", "cal": 76, "pro": 8.0, "carb": 1.9, "fat": 4.8, "fibre": 0.3},
    {"name": "Peas (green, cooked)", "cal": 81, "pro": 5.4, "carb": 14.5, "fat": 0.4, "fibre": 5.1},
    {"name": "Mung Beans (cooked)", "cal": 105, "pro": 7.0, "carb": 19.2, "fat": 0.4, "fibre": 7.6},

    # ─── NUTS & SEEDS ────────────────────────────────────────────────────────
    {"name": "Almonds", "cal": 579, "pro": 21.2, "carb": 21.7, "fat": 49.9, "fibre": 12.5},
    {"name": "Walnuts", "cal": 654, "pro": 15.2, "carb": 13.7, "fat": 65.2, "fibre": 6.7},
    {"name": "Peanuts", "cal": 567, "pro": 25.8, "carb": 16.1, "fat": 49.2, "fibre": 8.5},
    {"name": "Peanut Butter", "cal": 588, "pro": 25.1, "carb": 20.1, "fat": 49.9, "fibre": 6.0},
    {"name": "Cashews", "cal": 553, "pro": 18.2, "carb": 30.2, "fat": 43.9, "fibre": 3.3},
    {"name": "Sunflower Seeds", "cal": 584, "pro": 20.8, "carb": 20.0, "fat": 51.5, "fibre": 8.6},
    {"name": "Chia Seeds", "cal": 486, "pro": 16.5, "carb": 42.1, "fat": 30.7, "fibre": 34.4},
    {"name": "Flaxseeds", "cal": 534, "pro": 18.3, "carb": 28.9, "fat": 42.2, "fibre": 27.3},
    {"name": "Pumpkin Seeds", "cal": 559, "pro": 30.2, "carb": 10.7, "fat": 49.1, "fibre": 6.0},
    {"name": "Pistachio", "cal": 562, "pro": 20.2, "carb": 27.6, "fat": 45.3, "fibre": 10.3},

    # ─── FATS & OILS ─────────────────────────────────────────────────────────
    {"name": "Olive Oil", "cal": 884, "pro": 0, "carb": 0, "fat": 100, "fibre": 0},
    {"name": "Sunflower Oil", "cal": 884, "pro": 0, "carb": 0, "fat": 100, "fibre": 0},
    {"name": "Coconut Oil", "cal": 862, "pro": 0, "carb": 0, "fat": 100, "fibre": 0},
    {"name": "Ghee", "cal": 900, "pro": 0, "carb": 0, "fat": 99.5, "fibre": 0},

    # ─── CENTRAL ASIAN / UZBEK CUISINE ───────────────────────────────────────
    {"name": "Plov (Uzbek rice pilaf)", "cal": 220, "pro": 7.5, "carb": 28, "fat": 9, "fibre": 1.5},
    {"name": "Shashlik (lamb skewer)", "cal": 255, "pro": 22, "carb": 0, "fat": 18, "fibre": 0},
    {"name": "Somsa (baked meat pastry)", "cal": 320, "pro": 12, "carb": 30, "fat": 17, "fibre": 1.0},
    {"name": "Manti (steamed dumplings, beef)", "cal": 195, "pro": 11.5, "carb": 22, "fat": 7, "fibre": 0.8},
    {"name": "Laghman (noodle soup)", "cal": 150, "pro": 8, "carb": 21, "fat": 4, "fibre": 1.5},
    {"name": "Dimlama (meat & veg stew)", "cal": 130, "pro": 10, "carb": 9, "fat": 6.5, "fibre": 2.5},
    {"name": "Shorpa (lamb soup)", "cal": 90, "pro": 7, "carb": 6, "fat": 4, "fibre": 1.0},
    {"name": "Norin (boiled horse meat + noodles)", "cal": 180, "pro": 12, "carb": 18, "fat": 6, "fibre": 0.5},
    {"name": "Fried Egg (in oil)", "cal": 196, "pro": 13.6, "carb": 1.6, "fat": 14.8, "fibre": 0},
    {"name": "Scrambled Eggs (with butter)", "cal": 182, "pro": 12, "carb": 1.8, "fat": 14, "fibre": 0},
    {"name": "Boiled Egg", "cal": 155, "pro": 12.6, "carb": 1.1, "fat": 10.6, "fibre": 0},
    {"name": "Qozon Kabob (pan-fried lamb)", "cal": 290, "pro": 20, "carb": 2, "fat": 22, "fibre": 0},
    {"name": "Mastava (rice soup)", "cal": 95, "pro": 5, "carb": 14, "fat": 2.5, "fibre": 1.0},
    {"name": "Chuchvara (boiled dumplings)", "cal": 165, "pro": 9, "carb": 20, "fat": 5.5, "fibre": 0.5},
    {"name": "Bread (non, Uzbek)", "cal": 258, "pro": 8, "carb": 54, "fat": 1.2, "fibre": 2.0},
    {"name": "Fried Rice (with oil)", "cal": 163, "pro": 3.5, "carb": 27, "fat": 4.8, "fibre": 0.5},
    {"name": "Boiled Chicken (without skin)", "cal": 130, "pro": 25, "carb": 0, "fat": 2.8, "fibre": 0},
    {"name": "Grilled Chicken Wings", "cal": 241, "pro": 19.5, "carb": 0, "fat": 16.8, "fibre": 0},
    {"name": "Beef Soup (with vegetables)", "cal": 85, "pro": 7, "carb": 7, "fat": 3.5, "fibre": 1.5},
    {"name": "Tandir Bread", "cal": 265, "pro": 8.5, "carb": 55, "fat": 1.5, "fibre": 2.2},
    {"name": "Samsa (fried meat pastry)", "cal": 380, "pro": 11, "carb": 32, "fat": 23, "fibre": 0.8},
    {"name": "Beef Kebab (ground, grilled)", "cal": 210, "pro": 17, "carb": 5, "fat": 13.5, "fibre": 0.5},
    {"name": "Lamb Ribs (grilled)", "cal": 292, "pro": 18, "carb": 0, "fat": 24, "fibre": 0},
    {"name": "Kefir (fermented milk)", "cal": 61, "pro": 3.5, "carb": 4.8, "fat": 3.3, "fibre": 0},
    {"name": "Suzma (strained yoghurt)", "cal": 120, "pro": 8, "carb": 5, "fat": 7.5, "fibre": 0},
    {"name": "Qoymog (sour cream)", "cal": 191, "pro": 3.2, "carb": 4.3, "fat": 18, "fibre": 0},
    {"name": "Halva (sesame)", "cal": 516, "pro": 12.7, "carb": 55, "fat": 30, "fibre": 4.5},
    {"name": "Navat (crystallized sugar)", "cal": 390, "pro": 0, "carb": 97, "fat": 0, "fibre": 0},
    {"name": "Kurut (dried yoghurt balls)", "cal": 280, "pro": 20, "carb": 28, "fat": 8.5, "fibre": 0},

    # ─── FAST FOOD / COMMON ───────────────────────────────────────────────────
    {"name": "Burger (beef, no bun)", "cal": 250, "pro": 17, "carb": 3, "fat": 19, "fibre": 0},
    {"name": "Pizza Margherita", "cal": 266, "pro": 11, "carb": 33, "fat": 10, "fibre": 2.3},
    {"name": "French Fries", "cal": 312, "pro": 3.4, "carb": 41, "fat": 15, "fibre": 3.8},
    {"name": "Hot Dog (with bun)", "cal": 290, "pro": 10, "carb": 24, "fat": 17, "fibre": 1.0},
    {"name": "Shawarma (chicken)", "cal": 220, "pro": 14, "carb": 22, "fat": 8, "fibre": 1.5},

    # ─── DRINKS ──────────────────────────────────────────────────────────────
    {"name": "Whole Milk (1 cup / 240ml)", "cal": 149, "pro": 8.0, "carb": 12, "fat": 8, "fibre": 0},
    {"name": "Orange Juice (fresh)", "cal": 45, "pro": 0.7, "carb": 10.4, "fat": 0.2, "fibre": 0.2},
    {"name": "Protein Shake (mixed with water)", "cal": 120, "pro": 25, "carb": 5, "fat": 1.5, "fibre": 0},
    {"name": "Sports Drink (Gatorade)", "cal": 26, "pro": 0, "carb": 7, "fat": 0, "fibre": 0},
    {"name": "Green Tea (plain)", "cal": 1, "pro": 0, "carb": 0.2, "fat": 0, "fibre": 0},
    {"name": "Black Coffee (plain)", "cal": 2, "pro": 0.3, "carb": 0, "fat": 0, "fibre": 0},
    {"name": "Coffee with Milk (100ml)", "cal": 30, "pro": 1.5, "carb": 2.9, "fat": 1.5, "fibre": 0},
    {"name": "Coca Cola (regular)", "cal": 42, "pro": 0, "carb": 10.6, "fat": 0, "fibre": 0},

    # ─── SNACKS & SUPPLEMENTS ─────────────────────────────────────────────────
    {"name": "Creatine Monohydrate (5g serving)", "cal": 0, "pro": 0, "carb": 0, "fat": 0, "fibre": 0},
    {"name": "BCAA Powder (10g serving)", "cal": 40, "pro": 10, "carb": 0, "fat": 0, "fibre": 0},
    {"name": "Protein Bar (brand varies)", "cal": 220, "pro": 20, "carb": 24, "fat": 7, "fibre": 5},
    {"name": "Rice Cake (plain)", "cal": 387, "pro": 8.2, "carb": 81.5, "fat": 2.8, "fibre": 2.2},
    {"name": "Dark Chocolate (85%)", "cal": 598, "pro": 7.8, "carb": 45.9, "fat": 42.6, "fibre": 10.9},
    {"name": "Honey", "cal": 304, "pro": 0.3, "carb": 82.4, "fat": 0, "fibre": 0.2},
    {"name": "Jam / Jelly", "cal": 278, "pro": 0.4, "carb": 69, "fat": 0.1, "fibre": 1.0},
    {"name": "Mayonnaise", "cal": 680, "pro": 1.0, "carb": 0.6, "fat": 74.9, "fibre": 0},
    {"name": "Ketchup", "cal": 112, "pro": 1.3, "carb": 26.7, "fat": 0.1, "fibre": 0.3},
    {"name": "Soy Sauce (1 tbsp / 15ml)", "cal": 9, "pro": 1.3, "carb": 0.8, "fat": 0.1, "fibre": 0.1},
    {"name": "Potato Chips (regular)", "cal": 536, "pro": 6.6, "carb": 53, "fat": 34.6, "fibre": 4.8},
]


# Cooking method calorie adjustment factors
# Applied to the raw ingredient calories
COOKING_FACTORS = {
    "raw": 1.0,
    "boiled": 0.95,       # slight nutrient loss
    "steamed": 0.97,
    "grilled": 0.90,      # fat drips away
    "baked": 0.95,
    "fried_shallow": 1.25,   # absorbs oil
    "fried_deep": 1.45,      # significant oil absorption
    "stir_fried": 1.15,   # light oil added
    "sauteed": 1.10,
    "roasted": 0.90,
    "microwaved": 0.95,
    "pressure_cooked": 0.95,
    "slow_cooked": 0.92,
}

COOKING_LABELS = {
    "raw": "Raw / Uncooked",
    "boiled": "Boiled",
    "steamed": "Steamed",
    "grilled": "Grilled / BBQ",
    "baked": "Baked / Oven",
    "fried_shallow": "Pan Fried (oil)",
    "fried_deep": "Deep Fried",
    "stir_fried": "Stir Fried (wok)",
    "sauteed": "Sautéed (butter/oil)",
    "roasted": "Roasted",
    "microwaved": "Microwaved",
    "pressure_cooked": "Pressure Cooked",
    "slow_cooked": "Slow Cooked",
}


def seed_food_database(db: Session) -> int:
    """Seed local food database into FoodCache. Only adds missing entries. Returns count added."""
    # Fail-fast at seed time if any non-allowlisted food has all-zero macros.
    for food in FOOD_DATABASE:
        if is_zero_macro(food["cal"], food["pro"], food["carb"], food["fat"]) \
                and food["name"] not in ZERO_MACRO_ALLOWED:
            raise ValueError(
                f"Food '{food['name']}' has all-zero macros and is not on the allowlist. "
                f"Either fix the seed values or add it to ZERO_MACRO_ALLOWED."
            )

    seeded = 0
    for food in FOOD_DATABASE:
        source_id = f"local_{food['name'].lower().replace(' ', '_').replace('/', '_')[:40]}"
        existing = db.query(FoodCache).filter(
            FoodCache.source == "local",
            FoodCache.source_id == source_id,
        ).first()
        if existing:
            continue

        db.add(FoodCache(
            source="local",
            source_id=source_id,
            name=food["name"],
            nutrients_per_100g_json={
                "calories_per_100g": food["cal"],
                "protein_per_100g": food["pro"],
                "carbs_per_100g": food["carb"],
                "fat_per_100g": food["fat"],
                "fibre_per_100g": food["fibre"],
            },
        ))
        seeded += 1

    if seeded > 0:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return seeded


def get_cooking_adjustment(method: str) -> dict:
    """Return calorie factor and label for a cooking method."""
    factor = COOKING_FACTORS.get(method, 1.0)
    label = COOKING_LABELS.get(method, method)
    return {"method": method, "label": label, "factor": factor}


def calculate_cooked_dish(ingredients: list[dict], cooking_method: str) -> dict:
    """
    Calculate macros for a cooked dish.
    ingredients: [{"food_name": str, "grams": float, "nutrients_per_100g": dict}]
    Returns total macros scaled by cooking factor.
    """
    factor = COOKING_FACTORS.get(cooking_method, 1.0)
    total = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fibre_g": 0}
    total_grams = 0

    for ing in ingredients:
        g = ing["grams"]
        n = ing["nutrients_per_100g"]
        scale = g / 100.0
        total["calories"] += n.get("calories_per_100g", 0) * scale
        total["protein_g"] += n.get("protein_per_100g", 0) * scale
        total["carbs_g"] += n.get("carbs_per_100g", 0) * scale
        total["fat_g"] += n.get("fat_per_100g", 0) * scale
        total["fibre_g"] += n.get("fibre_per_100g", 0) * scale
        total_grams += g

    # Apply cooking factor (primarily affects calories and fat)
    total["calories"] = round(total["calories"] * factor, 1)
    total["fat_g"] = round(total["fat_g"] * factor, 1)
    total["protein_g"] = round(total["protein_g"], 1)
    total["carbs_g"] = round(total["carbs_g"], 1)
    total["fibre_g"] = round(total["fibre_g"], 1)
    total["total_grams"] = round(total_grams, 0)
    total["cooking_method"] = cooking_method
    total["cooking_label"] = COOKING_LABELS.get(cooking_method, cooking_method)
    total["cooking_factor"] = factor

    return total
