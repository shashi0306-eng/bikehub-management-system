import os
import mysql.connector


# ============================================================
# SETTINGS
# ============================================================

IMAGE_FOLDER = "images"

MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "Itzsha@03"
MYSQL_DATABASE = "bikehub"


# ============================================================
# CONNECT TO DATABASE
# ============================================================

try:

    db = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

    cursor = db.cursor(dictionary=True)

    print()
    print("=" * 70)
    print("BIKEHUB PHOTO SYNCHRONIZER")
    print("=" * 70)
    print()

except Exception as e:

    print("MySQL connection error:")
    print(e)
    exit()


# ============================================================
# GET ALL BIKES
# ============================================================

cursor.execute("""
    SELECT id, brand, model
    FROM bikes
    ORDER BY id
""")

bikes = cursor.fetchall()

print(
    "Total bikes found:",
    len(bikes)
)

print()


# ============================================================
# FUNCTION TO MAKE FOLDER NAME
# ============================================================

def clean_name(text):

    text = str(text)

    result = ""

    for character in text:

        if character.isalnum():

            result += character

        elif character in [" ", "-", "+"]:

            result += "_"

    while "__" in result:

        result = result.replace(
            "__",
            "_"
        )

    return result.strip("_")


# ============================================================
# SYNCHRONIZE ONE BIKE
# ============================================================

def sync_bike(bike):

    bike_id = bike["id"]

    brand = bike["brand"]

    model = bike["model"]


    # --------------------------------------------------------
    # CREATE FOLDER NAME
    # --------------------------------------------------------

    folder_name = (
        f"{bike_id:03d}_"
        f"{clean_name(brand)}_"
        f"{clean_name(model)}"
    )


    bike_folder = os.path.join(
        IMAGE_FOLDER,
        folder_name
    )


    print(
        f"Bike {bike_id}: "
        f"{brand} {model}"
    )


    # --------------------------------------------------------
    # CHECK FOLDER
    # --------------------------------------------------------

    if not os.path.exists(bike_folder):

        print(
            "  Folder not found:"
        )

        print(
            " ",
            bike_folder
        )

        print()

        return 0


    # --------------------------------------------------------
    # FIND JPG FILES
    # --------------------------------------------------------

    image_files = []


    for filename in os.listdir(
        bike_folder
    ):

        full_path = os.path.join(
            bike_folder,
            filename
        )


        if not os.path.isfile(
            full_path
        ):

            continue


        extension = os.path.splitext(
            filename
        )[1].lower()


        if extension in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        ]:

            image_files.append(
                filename
            )


    # --------------------------------------------------------
    # SORT PHOTOS
    # --------------------------------------------------------

    image_files.sort()


    # --------------------------------------------------------
    # USE MAXIMUM 4 PHOTOS
    # --------------------------------------------------------

    image_files = image_files[:4]


    if not image_files:

        print(
            "  No photos found."
        )

        print()

        return 0


    # --------------------------------------------------------
    # DELETE OLD DATABASE RECORDS
    # --------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM bike_images
        WHERE bike_id = %s
        """,
        (bike_id,)
    )


    # --------------------------------------------------------
    # INSERT CURRENT PHOTOS
    # --------------------------------------------------------

    count = 0


    for index, filename in enumerate(
        image_files,
        start=1
    ):

        # IMPORTANT:
        # Store folder + filename
        #
        # Example:
        # 001_KTM_125_Duke/001_KTM_125_Duke_1.jpg

        database_filename = (
            folder_name
            + "/"
            + filename
        )


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
                database_filename,
                index
            )
        )


        count += 1


    db.commit()


    print(
        "  Photos connected:",
        count
    )

    print()


    return count


# ============================================================
# SYNCHRONIZE ALL BIKES
# ============================================================

total_photos = 0

bikes_with_photos = 0

bikes_without_photos = 0


for bike in bikes:

    try:

        count = sync_bike(
            bike
        )


        total_photos += count


        if count > 0:

            bikes_with_photos += 1

        else:

            bikes_without_photos += 1


    except Exception as e:

        print(
            "ERROR:",
            e
        )

        print()

        bikes_without_photos += 1


# ============================================================
# CLOSE DATABASE
# ============================================================

cursor.close()

db.close()


# ============================================================
# FINAL RESULT
# ============================================================

print()
print("=" * 70)
print("PHOTO SYNCHRONIZATION COMPLETED")
print("=" * 70)
print()

print(
    "Total bikes:",
    len(bikes)
)

print(
    "Bikes with photos:",
    bikes_with_photos
)

print(
    "Bikes without photos:",
    bikes_without_photos
)

print(
    "Total photos connected:",
    total_photos
)

print()

print(
    "Your photos are being used directly from:"
)

print(
    os.path.abspath(IMAGE_FOLDER)
)

print()
print("=" * 70)
print("DONE")
print("=" * 70)