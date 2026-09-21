import os
import re
import json
import time
import requests
import mysql.connector

from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from urllib.parse import quote


# ============================================================
# SETTINGS
# ============================================================

IMAGE_FOLDER = "images"

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "Itzsha@03"
MYSQL_DATABASE = "bikehub"

NUMBER_OF_IMAGES = 4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}


# ============================================================
# CREATE IMAGES FOLDER
# ============================================================

os.makedirs(IMAGE_FOLDER, exist_ok=True)


# ============================================================
# MYSQL CONNECTION
# ============================================================

try:

    db = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, brand, model
        FROM bikes
        ORDER BY id
    """)

    bikes = cursor.fetchall()

    print()
    print("=" * 70)
    print("BIKEHUB IMAGE DOWNLOADER")
    print("=" * 70)
    print("Total bikes found:", len(bikes))
    print()

except Exception as e:

    print()
    print("=" * 70)
    print("MYSQL CONNECTION ERROR")
    print("=" * 70)
    print(e)
    print()
    exit()


# ============================================================
# CLEAN FILE NAME
# ============================================================

def clean_name(text):

    text = str(text)

    text = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        text
    )

    text = re.sub(
        r"_+",
        "_",
        text
    )

    return text.strip("_")


# ============================================================
# SEARCH IMAGE URLs
# ============================================================

def search_images(bike_name):

    print()
    print("Searching:")
    print(bike_name)

    query = f'"{bike_name}" bike motorcycle'

    search_url = (
        "https://www.bing.com/images/search?q="
        + quote(query)
        + "&form=HDRSC2"
    )

    try:

        response = requests.get(
            search_url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:

            print(
                "Search failed:",
                response.status_code
            )

            return []

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        image_urls = []

        # ----------------------------------------------------
        # BING IMAGE RESULTS
        # ----------------------------------------------------

        for result in soup.select("a.iusc"):

            data = result.get("m")

            if not data:
                continue

            try:

                info = json.loads(data)

                image_url = info.get("murl")

                if image_url:
                    image_urls.append(image_url)

            except Exception:
                continue


        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------

        unique_urls = []

        seen = set()

        for url in image_urls:

            if url not in seen:

                seen.add(url)

                unique_urls.append(url)


        print(
            "Images found:",
            len(unique_urls)
        )

        return unique_urls

    except Exception as e:

        print(
            "Search error:",
            e
        )

        return []


# ============================================================
# CHECK URL
# ============================================================

def is_bad_url(url):

    if not url:
        return True

    lower = url.lower()

    bad_words = [
        "logo",
        "icon",
        "avatar",
        "sprite",
        "placeholder",
        "loader",
        "facebook",
        "instagram",
        "youtube",
        "pinterest",
        "banner",
        "advertisement"
    ]

    for word in bad_words:

        if word in lower:
            return True

    return False


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(
    image_url,
    output_file
):

    try:

        response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:

            return False


        # ----------------------------------------------------
        # OPEN IMAGE
        # ----------------------------------------------------

        image = Image.open(
            BytesIO(response.content)
        )


        # ----------------------------------------------------
        # CHECK IMAGE SIZE
        # ----------------------------------------------------

        width, height = image.size

        if width < 400 or height < 250:

            return False


        # ----------------------------------------------------
        # CONVERT TO JPG
        # ----------------------------------------------------

        image = image.convert("RGB")

        image.save(
            output_file,
            "JPEG",
            quality=95
        )

        return True

    except Exception:

        return False


# ============================================================
# REMOVE OLD DATABASE RECORDS
# ============================================================

def remove_old_images(bike_id):

    try:

        cursor.execute(
            """
            DELETE FROM bike_images
            WHERE bike_id = %s
            """,
            (bike_id,)
        )

        db.commit()

    except Exception as e:

        print(
            "Database delete error:",
            e
        )


# ============================================================
# ADD IMAGE TO DATABASE
# ============================================================

def add_image_to_database(
    bike_id,
    image_name,
    display_order
):

    try:

        cursor.execute(
            """
            INSERT INTO bike_images
            (
                bike_id,
                image_name,
                display_order
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                bike_id,
                image_name,
                display_order
            )
        )

        db.commit()

        return True

    except Exception as e:

        print(
            "Database insert error:",
            e
        )

        return False


# ============================================================
# DOWNLOAD ONE BIKE
# ============================================================

def download_bike(
    bike_id,
    brand,
    model
):

    bike_name = f"{brand} {model}"

    print()
    print("=" * 70)
    print(
        f"BIKE {bike_id}: {bike_name}"
    )
    print("=" * 70)


    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    image_urls = search_images(
        bike_name
    )


    if not image_urls:

        print(
            "No images found."
        )

        return 0


    # --------------------------------------------------------
    # REMOVE OLD DATABASE RECORDS
    # --------------------------------------------------------

    remove_old_images(
        bike_id
    )


    # --------------------------------------------------------
    # DELETE OLD FILES FOR THIS BIKE
    # --------------------------------------------------------

    for number in range(
        1,
        NUMBER_OF_IMAGES + 1
    ):

        old_file = os.path.join(
            IMAGE_FOLDER,
            f"bike_{bike_id}_{number}.jpg"
        )

        if os.path.exists(old_file):

            try:
                os.remove(old_file)
            except:
                pass


    # --------------------------------------------------------
    # DOWNLOAD IMAGES
    # --------------------------------------------------------

    downloaded = 0

    used_urls = set()


    for image_url in image_urls:

        if downloaded >= NUMBER_OF_IMAGES:
            break


        # Skip unwanted images

        if is_bad_url(image_url):
            continue


        if image_url in used_urls:
            continue


        image_number = downloaded + 1


        filename = (
            f"bike_{bike_id}_"
            f"{image_number}.jpg"
        )


        output_file = os.path.join(
            IMAGE_FOLDER,
            filename
        )


        print()
        print(
            f"Downloading {image_number}/4..."
        )


        success = download_image(
            image_url,
            output_file
        )


        if not success:

            print(
                "  Failed"
            )

            continue


        # ----------------------------------------------------
        # ADD TO DATABASE
        # ----------------------------------------------------

        database_success = add_image_to_database(
            bike_id,
            filename,
            image_number
        )


        if database_success:

            downloaded += 1

            used_urls.add(
                image_url
            )

            print(
                "  Saved:",
                filename
            )

        else:

            try:
                os.remove(output_file)
            except:
                pass


        time.sleep(0.5)


    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print()
    print(
        f"{bike_name}: "
        f"{downloaded}/4 images downloaded"
    )

    return downloaded


# ============================================================
# DOWNLOAD ALL BIKES
# ============================================================

total_images = 0
successful_bikes = 0
failed_bikes = 0


print()
print("=" * 70)
print("STARTING DOWNLOAD")
print("=" * 70)
print()


for bike in bikes:

    bike_id = bike["id"]

    brand = bike["brand"]

    model = bike["model"]


    try:

        count = download_bike(
            bike_id,
            brand,
            model
        )


        total_images += count


        if count > 0:

            successful_bikes += 1

        else:

            failed_bikes += 1


    except Exception as e:

        print()
        print(
            "ERROR:",
            brand,
            model
        )

        print(e)

        failed_bikes += 1


    # Wait between searches

    time.sleep(2)


# ============================================================
# CLOSE MYSQL
# ============================================================

cursor.close()

db.close()


# ============================================================
# FINAL RESULT
# ============================================================

print()
print()
print("=" * 70)
print("DOWNLOAD COMPLETED")
print("=" * 70)

print()

print(
    "Total bikes:",
    len(bikes)
)

print(
    "Bikes with images:",
    successful_bikes
)

print(
    "Bikes without images:",
    failed_bikes
)

print(
    "Total images:",
    total_images
)

print()

print(
    "Images saved in:"
)

print(
    os.path.abspath(IMAGE_FOLDER)
)

print()
print("=" * 70)
print("DONE")
print("=" * 70)