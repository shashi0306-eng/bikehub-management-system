from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory
)

import mysql.connector
import os
import re

from werkzeug.utils import secure_filename


# IMPORTANT: Set these environment variables before running the app:
# MYSQL_PASSWORD = your local MySQL root password
# FLASK_SECRET_KEY = a long random secret key
# The real values are intentionally NOT stored in this source file.


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():

    db_config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE", "bikehub")
    }

    ssl_ca = os.getenv("MYSQL_SSL_CA")

    if ssl_ca:
        db_config["ssl_ca"] = ssl_ca
        db_config["ssl_verify_cert"] = True
        db_config["ssl_verify_identity"] = True

    return mysql.connector.connect(**db_config)
    


# =========================================================
# IMAGE HELPERS
# =========================================================

def clean_folder_name(text):
    text = str(text).strip()

    text = text.replace(" ", "_")
    text = text.replace("-", "_")
    text = text.replace("+", "_")

    text = re.sub(
        r"[^A-Za-z0-9_]",
        "",
        text
    )

    while "__" in text:
        text = text.replace(
            "__",
            "_"
        )

    return text.strip("_")


# =========================================================
# IMAGE ROOT FOLDERS
# =========================================================

def get_bike_image_roots():

    roots = [
        os.path.join(
            app.root_path,
            "images"
        ),

        os.path.join(
            app.root_path,
            "static",
            "images"
        )
    ]

    # Return existing folders.
    # Also create /images automatically.
    main_images = os.path.join(
        app.root_path,
        "images"
    )

    os.makedirs(
        main_images,
        exist_ok=True
    )

    result = []

    for root in roots:
        if os.path.isdir(root):
            result.append(root)

    return result


# =========================================================
# FIND FILE INSIDE IMAGE ROOT
# =========================================================

def find_image_file(filename):

    if not filename:
        return None

    filename = str(filename).replace(
        "\\",
        "/"
    ).lstrip("/")

    for root in get_bike_image_roots():

        # -------------------------------------------------
        # Direct path
        # -------------------------------------------------

        direct_path = os.path.join(
            root,
            filename
        )

        if os.path.isfile(direct_path):
            return (
                root,
                filename
            )

        # -------------------------------------------------
        # Recursive search
        # -------------------------------------------------

        target_name = os.path.basename(
            filename
        ).lower()

        for current_root, directories, files in os.walk(root):

            for current_file in files:

                if current_file.lower() == target_name:

                    relative_path = os.path.relpath(
                        os.path.join(
                            current_root,
                            current_file
                        ),
                        root
                    )

                    relative_path = relative_path.replace(
                        "\\",
                        "/"
                    )

                    return (
                        root,
                        relative_path
                    )

    return None


# =========================================================
# GET PRIMARY BIKE IMAGE
# =========================================================

def get_primary_bike_image(
    bike_id,
    brand=None,
    model=None
):

    """
    Finds the first image for a bike.

    Supported formats:

    1. Database upload:
       images/bike_4_1.jpg
       images/bike_4_2.jpg

    2. Old folder format:
       images/004_KTM_250_Duke/
       004_KTM_250_Duke_1.jpg

    3. Older flat format:
       images/4_ktm_250.jpg
       images/4_KTM_250_Duke.jpg

    4. Generic:
       images/4_*.jpg
    """

    try:
        bike_id = int(bike_id)
    except (
        ValueError,
        TypeError
    ):
        return None


    # =====================================================
    # 1. DATABASE IMAGE
    # =====================================================

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                image_name
            FROM bike_images
            WHERE bike_id = %s
            ORDER BY
                display_order,
                id
            LIMIT 1
            """,
            (bike_id,)
        )

        image = cursor.fetchone()

        cursor.close()
        conn.close()

        if image and image[0]:

            result = find_image_file(
                image[0]
            )

            if result:

                return result[1]

    except mysql.connector.Error:
        pass


    # =====================================================
    # 2. CURRENT FLAT FORMAT
    # =====================================================

    for root in get_bike_image_roots():

        files = []

        try:

            for filename in os.listdir(root):

                file_path = os.path.join(
                    root,
                    filename
                )

                if not os.path.isfile(
                    file_path
                ):
                    continue

                extension = os.path.splitext(
                    filename
                )[1].lower()

                if extension not in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                ):
                    continue

                match = re.fullmatch(
                    rf"bike_{bike_id}_(\d+)"
                    rf"\.(jpg|jpeg|png|webp)",
                    filename,
                    re.IGNORECASE
                )

                if match:

                    number = int(
                        match.group(1)
                    )

                    files.append(
                        (
                            number,
                            filename.lower(),
                            filename
                        )
                    )

        except OSError:
            continue

        if files:

            files.sort(
                key=lambda item: (
                    item[0],
                    item[1]
                )
            )

            return files[0][2]


    # =====================================================
    # 3. OLD FOLDER FORMAT
    # =====================================================

    if (
        brand is not None
        and model is not None
    ):

        brand_clean = clean_folder_name(
            brand
        )

        model_clean = clean_folder_name(
            model
        )

        folder_name = (
            f"{bike_id:03d}_"
            f"{brand_clean}_"
            f"{model_clean}"
        )

        for root in get_bike_image_roots():

            folder_path = os.path.join(
                root,
                folder_name
            )

            if not os.path.isdir(
                folder_path
            ):
                continue

            files = []

            try:

                for filename in os.listdir(
                    folder_path
                ):

                    file_path = os.path.join(
                        folder_path,
                        filename
                    )

                    if not os.path.isfile(
                        file_path
                    ):
                        continue

                    extension = os.path.splitext(
                        filename
                    )[1].lower()

                    if extension not in (
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp"
                    ):
                        continue

                    match = re.search(
                        r"_(\d+)\.(jpg|jpeg|png|webp)$",
                        filename,
                        re.IGNORECASE
                    )

                    if match:

                        number = int(
                            match.group(1)
                        )

                    else:

                        number = 9999

                    files.append(
                        (
                            number,
                            filename.lower(),
                            filename
                        )
                    )

            except OSError:
                continue

            if files:

                files.sort(
                    key=lambda item: (
                        item[0],
                        item[1]
                    )
                )

                return (
                    folder_name
                    + "/"
                    + files[0][2]
                )


    # =====================================================
    # 4. OLD FLAT FILE NAMES
    # =====================================================

    possible_names = []

    if brand is not None:
        brand_clean = clean_folder_name(
            brand
        )
    else:
        brand_clean = ""

    if model is not None:
        model_clean = clean_folder_name(
            model
        )
    else:
        model_clean = ""


    if brand_clean and model_clean:

        possible_names.extend(
            [
                f"{bike_id}_{brand_clean}_{model_clean}.jpg",
                f"{bike_id}_{brand_clean}_{model_clean}.jpeg",
                f"{bike_id}_{brand_clean}_{model_clean}.png",
                f"{bike_id}_{brand_clean}_{model_clean}.webp",

                f"{bike_id:03d}_{brand_clean}_{model_clean}.jpg",
                f"{bike_id:03d}_{brand_clean}_{model_clean}.jpeg",
                f"{bike_id:03d}_{brand_clean}_{model_clean}.png",
                f"{bike_id:03d}_{brand_clean}_{model_clean}.webp"
            ]
        )


    for filename in possible_names:

        result = find_image_file(
            filename
        )

        if result:

            return result[1]


    # =====================================================
    # 5. SEARCH ANY IMAGE STARTING WITH BIKE ID
    # =====================================================

    prefixes = [
        f"{bike_id}_",
        f"{bike_id:03d}_",
        f"bike_{bike_id}_"
    ]

    for root in get_bike_image_roots():

        candidates = []

        try:

            for current_root, directories, files in os.walk(root):

                for filename in files:

                    extension = os.path.splitext(
                        filename
                    )[1].lower()

                    if extension not in (
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp"
                    ):
                        continue

                    lower_name = filename.lower()

                    if any(
                        lower_name.startswith(
                            prefix.lower()
                        )
                        for prefix in prefixes
                    ):

                        relative_path = os.path.relpath(
                            os.path.join(
                                current_root,
                                filename
                            ),
                            root
                        )

                        relative_path = relative_path.replace(
                            "\\",
                            "/"
                        )

                        candidates.append(
                            relative_path
                        )

        except OSError:
            continue

        if candidates:

            candidates.sort(
                key=lambda x: x.lower()
            )

            return candidates[0]


    return None


# =========================================================
# GET ALL GALLERY IMAGES FROM DATABASE
# =========================================================

def get_gallery_images_from_db(
    bike_id
):

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                image_name,
                display_order
            FROM bike_images
            WHERE bike_id = %s
            ORDER BY
                display_order,
                id
            """,
            (bike_id,)
        )

        images = cursor.fetchall()

        cursor.close()
        conn.close()

        valid_images = []

        for image in images:

            image_name = image[1]

            result = find_image_file(
                image_name
            )

            if result:

                # Keep DB structure.
                valid_images.append(
                    image
                )

        return valid_images

    except mysql.connector.Error:

        return []


# =========================================================
# GET ALL IMAGES FROM OLD FOLDER
# =========================================================

def get_gallery_images_from_folder(
    bike_id,
    brand,
    model
):

    gallery_images = []

    try:
        bike_id = int(
            bike_id
        )
    except (
        ValueError,
        TypeError
    ):
        return gallery_images


    brand_clean = clean_folder_name(
        brand
    )

    model_clean = clean_folder_name(
        model
    )

    folder_name = (
        f"{bike_id:03d}_"
        f"{brand_clean}_"
        f"{model_clean}"
    )


    for root in get_bike_image_roots():

        folder_path = os.path.join(
            root,
            folder_name
        )

        if not os.path.isdir(
            folder_path
        ):
            continue

        files = []

        try:

            filenames = os.listdir(
                folder_path
            )

        except OSError:

            filenames = []


        for filename in filenames:

            file_path = os.path.join(
                folder_path,
                filename
            )

            if not os.path.isfile(
                file_path
            ):
                continue

            extension = os.path.splitext(
                filename
            )[1].lower()

            if extension not in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            ):
                continue

            match = re.search(
                r"_(\d+)\.(jpg|jpeg|png|webp)$",
                filename,
                re.IGNORECASE
            )

            if match:

                number = int(
                    match.group(1)
                )

            else:

                number = 9999

            files.append(
                (
                    number,
                    filename
                )
            )


        files.sort(
            key=lambda item: (
                item[0],
                item[1].lower()
            )
        )


        for number, filename in files:

            gallery_images.append(
                (
                    0,
                    folder_name
                    + "/"
                    + filename,
                    number
                )
            )


        if gallery_images:
            break


    return gallery_images


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# =========================================================
# USER REGISTRATION
# =========================================================

@app.route(
    "/register",
    methods=[
        "GET",
        "POST"
    ]
)
def register():

    error = None

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if not re.fullmatch(
            r"[A-Za-z ]+",
            name
        ):

            error = (
                "Name should contain "
                "only alphabets and spaces."
            )

        elif not re.fullmatch(
            r"[0-9]{10}",
            mobile
        ):

            error = (
                "Phone number should contain "
                "exactly 10 digits."
            )

        elif len(password) < 8:

            error = (
                "Password must contain "
                "at least 8 characters."
            )

        elif not re.search(
            r"[A-Z]",
            password
        ):

            error = (
                "Password must contain "
                "at least 1 uppercase letter."
            )

        elif not re.search(
            r"[a-z]",
            password
        ):

            error = (
                "Password must contain "
                "at least 1 lowercase letter."
            )

        elif not re.search(
            r"[0-9]",
            password
        ):

            error = (
                "Password must contain "
                "at least 1 number."
            )

        elif not re.search(
            r"[^A-Za-z0-9]",
            password
        ):

            error = (
                "Password must contain "
                "at least 1 special character."
            )


        if error:

            return render_template(
                "register.html",
                error=error
            )


        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    mobile,
                    email,
                    password
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    mobile,
                    email,
                    password
                )
            )

            conn.commit()

            return redirect(
                url_for(
                    "login"
                )
            )

        except mysql.connector.IntegrityError:

            return render_template(
                "register.html",
                error="Email already registered."
            )

        finally:

            cursor.close()
            conn.close()


    return render_template(
        "register.html"
    )


# =========================================================
# USER LOGIN
# =========================================================

@app.route(
    "/login",
    methods=[
        "GET",
        "POST"
    ]
)
def login():

    if request.method == "POST":

        email = request.form[
            "email"
        ]

        password = request.form[
            "password"
        ]


        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email
            FROM users
            WHERE email = %s
            AND password = %s
            """,
            (
                email,
                password
            )
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()


        if user:

            session[
                "user_id"
            ] = user[0]

            session[
                "user_name"
            ] = user[1]

            session[
                "user_email"
            ] = user[2]

            return redirect(
                url_for(
                    "dashboard"
                )
            )


        return (
            "Invalid email or password."
        )


    return render_template(
        "login.html"
    )


# =========================================================
# USER DASHBOARD
# =========================================================

@app.route(
    "/dashboard"
)
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for(
                "login"
            )
        )


    return render_template(
        "dashboard.html",
        user_name=session.get(
            "user_name"
        )
    )


# =========================================================
# BROWSE BIKES
# =========================================================

@app.route(
    "/bikes"
)
def bikes():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM bikes
        ORDER BY id
        """
    )

    bikes_data = cursor.fetchall()


    bikes_with_images = []

    for bike in bikes_data:

        image_path = get_primary_bike_image(
            bike[0],
            bike[1],
            bike[2]
        )

        bikes_with_images.append(
            tuple(bike)
            + (
                image_path,
            )
        )


    cursor.close()
    conn.close()


    return render_template(
        "bikes.html",
        bikes=bikes_with_images
    )


# =========================================================
# BIKE DETAILS
# =========================================================

@app.route(
    "/bike/<int:bike_id>"
)
def bike_details(
    bike_id
):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM bikes
        WHERE id = %s
        """,
        (bike_id,)
    )

    bike = cursor.fetchone()

    cursor.close()
    conn.close()


    if bike is None:

        return "Bike not found."


    # -----------------------------------------------------
    # DATABASE PHOTOS
    # -----------------------------------------------------

    gallery_images = (
        get_gallery_images_from_db(
            bike_id
        )
    )


    # -----------------------------------------------------
    # OLD FOLDER PHOTOS
    # -----------------------------------------------------

    if not gallery_images:

        gallery_images = (
            get_gallery_images_from_folder(
                bike_id,
                bike[1],
                bike[2]
            )
        )


    # -----------------------------------------------------
    # IF STILL EMPTY, FIND PRIMARY IMAGE
    # -----------------------------------------------------

    if not gallery_images:

        primary_image = (
            get_primary_bike_image(
                bike_id,
                bike[1],
                bike[2]
            )
        )

        if primary_image:

            gallery_images = [
                (
                    0,
                    primary_image,
                    1
                )
            ]


    return render_template(
        "bike_details.html",
        bike=bike,
        gallery_images=gallery_images
    )


# =========================================================
# SEARCH & FILTER
# =========================================================

@app.route(
    "/search",
    methods=[
        "GET",
        "POST"
    ]
)
def search():

    conn = get_db_connection()
    cursor = conn.cursor()


    if request.method == "GET":

        search_text = request.args.get(
            "search",
            ""
        ).strip()

        brand = request.args.get(
            "brand",
            ""
        ).strip()

        cc = request.args.get(
            "cc",
            ""
        ).strip()

        price = request.args.get(
            "price",
            ""
        ).strip()

        mileage = request.args.get(
            "mileage",
            ""
        ).strip()

        sort = request.args.get(
            "sort",
            ""
        ).strip()

    else:

        search_text = request.form.get(
            "search",
            ""
        ).strip()

        brand = request.form.get(
            "brand",
            ""
        ).strip()

        cc = request.form.get(
            "cc",
            ""
        ).strip()

        price = request.form.get(
            "price",
            ""
        ).strip()

        mileage = request.form.get(
            "mileage",
            ""
        ).strip()

        sort = request.form.get(
            "sort",
            ""
        ).strip()


    query = (
        "SELECT * "
        "FROM bikes "
        "WHERE 1=1"
    )

    values = []


    # SEARCH

    if search_text:

        query += """
            AND
            (
                brand LIKE %s
                OR model LIKE %s
            )
        """

        values.extend(
            [
                "%" + search_text + "%",
                "%" + search_text + "%"
            ]
        )


    # BRAND

    if brand:

        query += (
            " AND brand = %s"
        )

        values.append(
            brand
        )


    # CC

    if cc == "100-125":

        query += (
            " AND cc BETWEEN %s AND %s"
        )

        values.extend(
            [
                100,
                125
            ]
        )

    elif cc == "126-160":

        query += (
            " AND cc BETWEEN %s AND %s"
        )

        values.extend(
            [
                126,
                160
            ]
        )

    elif cc == "161-200":

        query += (
            " AND cc BETWEEN %s AND %s"
        )

        values.extend(
            [
                161,
                200
            ]
        )

    elif cc == "201-250":

        query += (
            " AND cc BETWEEN %s AND %s"
        )

        values.extend(
            [
                201,
                250
            ]
        )

    elif cc == "251+":

        query += (
            " AND cc >= %s"
        )

        values.append(
            251
        )


    # PRICE

    if price == "0-150000":

        query += (
            " AND price <= %s"
        )

        values.append(
            150000
        )

    elif price == "150000-200000":

        query += """
            AND price > %s
            AND price <= %s
        """

        values.extend(
            [
                150000,
                200000
            ]
        )

    elif price == "200000-300000":

        query += """
            AND price > %s
            AND price <= %s
        """

        values.extend(
            [
                200000,
                300000
            ]
        )

    elif price == "300000+":

        query += (
            " AND price > %s"
        )

        values.append(
            300000
        )


    # MILEAGE

    if mileage:

        try:

            query += (
                " AND mileage >= %s"
            )

            values.append(
                float(mileage)
            )

        except (
            ValueError,
            TypeError
        ):

            pass


    # SORT

    if sort == "low":

        query += (
            " ORDER BY price ASC"
        )

    elif sort == "high":

        query += (
            " ORDER BY price DESC"
        )

    elif sort == "mileage":

        query += (
            " ORDER BY mileage DESC"
        )

    elif sort == "cc":

        query += (
            " ORDER BY cc ASC"
        )

    elif sort == "name":

        query += (
            " ORDER BY brand ASC, model ASC"
        )

    else:

        query += (
            " ORDER BY id ASC"
        )


    cursor.execute(
        query,
        tuple(values)
    )

    bikes_data = cursor.fetchall()


    bikes_with_images = []

    for bike in bikes_data:

        image_path = get_primary_bike_image(
            bike[0],
            bike[1],
            bike[2]
        )

        bikes_with_images.append(
            tuple(bike)
            + (
                image_path,
            )
        )


    cursor.close()
    conn.close()


    return render_template(
        "search.html",
        bikes=bikes_with_images
    )


# =========================================================
# BIKE COMPARISON
# =========================================================

@app.route(
    "/compare",
    methods=[
        "GET",
        "POST"
    ]
)
def compare():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM bikes
        ORDER BY brand, model
        """
    )

    bikes_data = cursor.fetchall()

    selected_bikes = []


    if request.method == "POST":

        bike_ids = request.form.getlist(
            "bike_ids"
        )

        if bike_ids:

            placeholders = ",".join(
                ["%s"] * len(bike_ids)
            )

            query = f"""
                SELECT *
                FROM bikes
                WHERE id IN ({placeholders})
            """

            cursor.execute(
                query,
                bike_ids
            )

            selected_bikes = (
                cursor.fetchall()
            )


    cursor.close()
    conn.close()


    return render_template(
        "compare.html",
        bikes=bikes_data,
        selected_bikes=selected_bikes
    )


# =========================================================
# SMART RECOMMENDATION
# =========================================================

@app.route(
    "/recommendation",
    methods=[
        "GET",
        "POST"
    ]
)
def recommendation():

    recommendations = []


    if request.method == "GET":

        return render_template(
            "recommendation.html",
            recommendations=[]
        )


    budget_text = request.form.get(
        "budget",
        ""
    ).strip()

    cc_range = request.form.get(
        "cc_range",
        ""
    ).strip()

    mileage_text = request.form.get(
        "mileage",
        ""
    ).strip()

    usage = request.form.get(
        "usage",
        ""
    ).strip().lower()


    try:

        budget = float(
            budget_text
        )

    except (
        ValueError,
        TypeError
    ):

        budget = 0


    try:

        min_mileage = float(
            mileage_text
        )

    except (
        ValueError,
        TypeError
    ):

        min_mileage = 0


    conditions = [
        "price <= %s"
    ]

    values = [
        budget
    ]


    # CC RANGE

    if cc_range:

        if "-" in cc_range:

            parts = cc_range.split("-")

            if len(parts) == 2:

                try:

                    min_cc = int(
                        parts[0]
                    )

                    max_cc = int(
                        parts[1]
                    )

                    conditions.append(
                        "cc BETWEEN %s AND %s"
                    )

                    values.extend(
                        [
                            min_cc,
                            max_cc
                        ]
                    )

                except ValueError:

                    pass


        elif cc_range.endswith("+"):

            try:

                min_cc = int(
                    cc_range.replace(
                        "+",
                        ""
                    )
                )

                conditions.append(
                    "cc >= %s"
                )

                values.append(
                    min_cc
                )

            except ValueError:

                pass


    # MILEAGE

    if min_mileage > 0:

        conditions.append(
            "mileage >= %s"
        )

        values.append(
            min_mileage
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    try:

        if usage in (
            "daily",
            "city",
            "commute"
        ):

            order_by = (
                "mileage DESC, "
                "price ASC"
            )

        elif usage == "highway":

            order_by = (
                "cc DESC, "
                "power DESC"
            )

        elif usage == "tour":

            order_by = (
                "cc DESC, "
                "fuel_capacity DESC"
            )

        elif usage == "sport":

            order_by = (
                "power DESC, "
                "cc DESC"
            )

        else:

            order_by = (
                "mileage DESC, "
                "price ASC"
            )


        query = (
            "SELECT * "
            "FROM bikes "
            "WHERE "
            + " AND ".join(
                conditions
            )
            + " ORDER BY "
            + order_by
            + " LIMIT 12"
        )


        cursor.execute(
            query,
            tuple(values)
        )

        bikes_data = cursor.fetchall()


        for bike in bikes_data:

            image_path = get_primary_bike_image(
                bike[0],
                bike[1],
                bike[2]
            )

            recommendations.append(
                tuple(bike)
                + (
                    image_path,
                )
            )


    finally:

        cursor.close()
        conn.close()


    return render_template(
        "recommendation.html",
        recommendations=recommendations
    )


# =========================================================
# COST CALCULATOR
# =========================================================

@app.route(
    "/cost_calculator",
    methods=[
        "GET",
        "POST"
    ]
)
def cost_calculator():

    result = None


    if request.method == "POST":

        try:

            distance = float(
                request.form[
                    "distance"
                ]
            )

            mileage = float(
                request.form[
                    "mileage"
                ]
            )

            fuel_price = float(
                request.form[
                    "fuel_price"
                ]
            )


            if mileage > 0:

                fuel_used = (
                    distance / mileage
                )

                total_cost = (
                    fuel_used
                    * fuel_price
                )

                result = {

                    "fuel_used":
                        round(
                            fuel_used,
                            2
                        ),

                    "total_cost":
                        round(
                            total_cost,
                            2
                        )
                }

        except (
            ValueError,
            TypeError,
            KeyError
        ):

            result = None


    return render_template(
        "cost_calculator.html",
        result=result
    )


# =========================================================
# MAINTENANCE
# =========================================================

@app.route(
    "/maintenance",
    methods=[
        "GET",
        "POST"
    ]
)
def maintenance():

    result = None


    if request.method == "POST":

        try:

            service = float(
                request.form.get(
                    "service",
                    0
                )
            )

            oil = float(
                request.form.get(
                    "oil",
                    0
                )
            )

            tyres = float(
                request.form.get(
                    "tyres",
                    0
                )
            )

            other = float(
                request.form.get(
                    "other",
                    0
                )
            )


            result = (
                service
                + oil
                + tyres
                + other
            )

        except (
            ValueError,
            TypeError
        ):

            result = None


    return render_template(
        "maintenance.html",
        result=result
    )


# =========================================================
# BIKE SCORE
# =========================================================

@app.route(
    "/bike_score",
    methods=[
        "GET",
        "POST"
    ]
)
def bike_score():

    bikes = []
    result = None

    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *
        FROM bikes
        ORDER BY brand, model
        """
    )

    bikes = cursor.fetchall()


    if request.method == "POST":

        bike_id = request.form.get(
            "bike_id"
        )


        cursor.execute(
            """
            SELECT *
            FROM bikes
            WHERE id = %s
            """,
            (bike_id,)
        )

        bike = cursor.fetchone()


        if bike:

            price = float(
                bike[4]
            )

            mileage = float(
                bike[5]
            )

            cc = float(
                bike[3]
            )


            # PRICE SCORE

            if price <= 150000:

                price_score = 30

            elif price <= 200000:

                price_score = 25

            elif price <= 300000:

                price_score = 20

            elif price <= 500000:

                price_score = 15

            else:

                price_score = 10


            # MILEAGE SCORE

            if mileage >= 50:

                mileage_score = 30

            elif mileage >= 45:

                mileage_score = 27

            elif mileage >= 40:

                mileage_score = 24

            elif mileage >= 35:

                mileage_score = 20

            elif mileage >= 30:

                mileage_score = 16

            else:

                mileage_score = 12


            # PERFORMANCE SCORE

            if cc >= 500:

                performance_score = 40

            elif cc >= 300:

                performance_score = 35

            elif cc >= 200:

                performance_score = 30

            elif cc >= 160:

                performance_score = 25

            elif cc >= 125:

                performance_score = 20

            else:

                performance_score = 15


            overall_score = (
                price_score
                + mileage_score
                + performance_score
            )


            result = {

                "bike":
                    bike,

                "price_score":
                    price_score,

                "mileage_score":
                    mileage_score,

                "performance_score":
                    performance_score,

                "overall_score":
                    overall_score
            }


    cursor.close()
    conn.close()


    return render_template(
        "bike_score.html",
        bikes=bikes,
        result=result
    )


# =========================================================
# IMAGE SERVING
# =========================================================

@app.route(
    "/images/<path:filename>"
)
def bike_image(
    filename
):

    """
    Serve images from:

    /images
    /static/images

    Also searches subfolders.
    This fixes old filenames such as:

        /images/4_ktm_250.jpg

    and newer filenames such as:

        /images/bike_4_1.jpg
    """

    filename = filename.replace(
        "\\",
        "/"
    )


    # -----------------------------------------------------
    # SECURITY / NORMALIZATION
    # -----------------------------------------------------

    filename = filename.lstrip("/")


    # -----------------------------------------------------
    # DIRECT OR RECURSIVE SEARCH
    # -----------------------------------------------------

    result = find_image_file(
        filename
    )


    if result:

        image_root = result[0]
        relative_path = result[1]

        return send_from_directory(
            image_root,
            relative_path
        )


    # -----------------------------------------------------
    # CASE-INSENSITIVE SEARCH BY BASENAME
    # -----------------------------------------------------

    target = os.path.basename(
        filename
    ).lower()


    for image_root in get_bike_image_roots():

        try:

            for current_root, directories, files in os.walk(
                image_root
            ):

                for current_file in files:

                    if current_file.lower() == target:

                        relative_path = os.path.relpath(
                            os.path.join(
                                current_root,
                                current_file
                            ),
                            image_root
                        )

                        relative_path = relative_path.replace(
                            "\\",
                            "/"
                        )

                        return send_from_directory(
                            image_root,
                            relative_path
                        )

        except OSError:
            continue


    return (
        "Image not found: "
        + filename,
        404
    )


# =========================================================
# RECOMMENDATION IMAGE
# =========================================================

@app.route(
    "/bike_recommendation_image/<int:bike_id>"
)
def bike_recommendation_image(
    bike_id
):

    relative_path = (
        get_primary_bike_image(
            bike_id
        )
    )


    # -----------------------------------------------------
    # GET BRAND + MODEL IF NEEDED
    # -----------------------------------------------------

    if not relative_path:

        try:

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    brand,
                    model
                FROM bikes
                WHERE id = %s
                """,
                (bike_id,)
            )

            bike = cursor.fetchone()

            cursor.close()
            conn.close()


            if bike:

                relative_path = (
                    get_primary_bike_image(
                        bike_id,
                        bike[0],
                        bike[1]
                    )
                )

        except mysql.connector.Error:

            relative_path = None


    if not relative_path:

        return (
            "Image not found",
            404
        )


    relative_path = relative_path.replace(
        "\\",
        "/"
    )


    result = find_image_file(
        relative_path
    )


    if result:

        return send_from_directory(
            result[0],
            result[1]
        )


    return (
        "Image not found",
        404
    )


# =========================================================
# BOOK TEST RIDE
# =========================================================

@app.route(
    "/book_test_ride/<int:bike_id>",
    methods=[
        "GET",
        "POST"
    ]
)
def book_test_ride(
    bike_id
):

    if "user_id" not in session:

        return redirect(
            url_for(
                "login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *
        FROM bikes
        WHERE id = %s
        """,
        (bike_id,)
    )

    bike = cursor.fetchone()


    if bike is None:

        cursor.close()
        conn.close()

        return "Bike not found."


    if request.method == "POST":

        name = request.form[
            "name"
        ]

        mobile = request.form[
            "mobile"
        ]

        email = request.form[
            "email"
        ]

        test_date = request.form[
            "test_date"
        ]

        test_time = request.form[
            "test_time"
        ]

        location = request.form[
            "location"
        ]


        cursor.execute(
            """
            INSERT INTO test_rides
            (
                user_id,
                bike_id,
                name,
                mobile,
                email,
                test_date,
                test_time,
                location,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'Pending'
            )
            """,
            (
                session[
                    "user_id"
                ],
                bike_id,
                name,
                mobile,
                email,
                test_date,
                test_time,
                location
            )
        )


        conn.commit()

        cursor.close()
        conn.close()


        return redirect(
            url_for(
                "my_test_rides"
            )
        )


    cursor.close()
    conn.close()


    return render_template(
        "book_test_ride.html",
        bike=bike
    )


# =========================================================
# MY TEST RIDES
# =========================================================

@app.route(
    "/my_test_rides"
)
def my_test_rides():

    if "user_id" not in session:

        return redirect(
            url_for(
                "login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            t.id,
            b.brand,
            b.model,
            t.name,
            t.mobile,
            t.email,
            t.test_date,
            t.test_time,
            t.location,
            t.status
        FROM test_rides t
        JOIN bikes b
        ON t.bike_id = b.id
        WHERE t.user_id = %s
        ORDER BY t.id DESC
        """,
        (
            session[
                "user_id"
            ],
        )
    )


    bookings = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "my_test_rides.html",
        bookings=bookings
    )


# =========================================================
# ADMIN TEST RIDES
# =========================================================

@app.route(
    "/admin_test_rides",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_test_rides():

    if "admin_id" not in session:
        return redirect(
            url_for(
                "admin_login"
            )
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # UPDATE TEST RIDE STATUS
    # -----------------------------------------------------

    if request.method == "POST":

        booking_id = request.form.get(
            "booking_id"
        )

        status = request.form.get(
            "status"
        )

        if booking_id and status:

            cursor.execute(
                """
                UPDATE test_rides
                SET status = %s
                WHERE id = %s
                """,
                (
                    status,
                    booking_id
                )
            )

            conn.commit()

    # -----------------------------------------------------
    # GET ALL TEST RIDES
    # -----------------------------------------------------

    cursor.execute(
        """
        SELECT
            t.id,
            b.brand,
            b.model,
            t.name,
            t.mobile,
            t.email,
            t.test_date,
            t.test_time,
            t.location,
            t.status
        FROM test_rides t
        JOIN bikes b
        ON t.bike_id = b.id
        ORDER BY t.id DESC
        """
    )

    bookings = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin_test_rides.html",
        bookings=bookings
    )


# =========================================================
# DELETE TEST RIDE
# =========================================================

@app.route(
    "/delete_test_ride/<int:booking_id>",
    methods=["POST"]
)
def delete_test_ride(booking_id):

    if "admin_id" not in session:
        return redirect(
            url_for(
                "admin_login"
            )
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            DELETE FROM test_rides
            WHERE id = %s
            """,
            (
                booking_id,
            )
        )

        conn.commit()

    except Exception as e:

        conn.rollback()

        print(
            "Error deleting test ride:",
            e
        )

    finally:

        cursor.close()
        conn.close()

    return redirect(
        url_for(
            "admin_test_rides"
        )
    )


# =========================================================
# ADMIN BIKE PHOTOS
# =========================================================
@app.route(
    "/admin_bike_images/<int:bike_id>",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_bike_images(
    bike_id
):

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *
        FROM bikes
        WHERE id = %s
        """,
        (bike_id,)
    )

    bike = cursor.fetchone()


    if bike is None:

        cursor.close()
        conn.close()

        return "Bike not found."


    if request.method == "POST":

        files = request.files.getlist(
            "photos"
        )


        image_folder = os.path.join(
            app.root_path,
            "images"
        )

        os.makedirs(
            image_folder,
            exist_ok=True
        )


        cursor.execute(
            """
            SELECT
                COALESCE(
                    MAX(display_order),
                    0
                )
            FROM bike_images
            WHERE bike_id = %s
            """,
            (bike_id,)
        )


        last_order = cursor.fetchone()[0]


        allowed_extensions = {
            "jpg",
            "jpeg",
            "png",
            "webp"
        }


        for file in files:

            if (
                not file
                or not file.filename
            ):
                continue


            original_name = secure_filename(
                file.filename
            )


            if "." not in original_name:
                continue


            extension = (
                original_name
                .rsplit(
                    ".",
                    1
                )[1]
                .lower()
            )


            if extension not in allowed_extensions:
                continue


            last_order += 1


            filename = (
                f"bike_{bike_id}_"
                f"{last_order}."
                f"{extension}"
            )


            file_path = os.path.join(
                image_folder,
                filename
            )


            file.save(
                file_path
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
                    filename,
                    last_order
                )
            )


        conn.commit()

        cursor.close()
        conn.close()


        return redirect(
            url_for(
                "admin_bike_images",
                bike_id=bike_id
            )
        )


    cursor.execute(
        """
        SELECT
            id,
            image_name,
            display_order
        FROM bike_images
        WHERE bike_id = %s
        ORDER BY
            display_order,
            id
        """,
        (bike_id,)
    )


    images = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "admin_bike_images.html",
        bike=bike,
        images=images
    )


# =========================================================
# DELETE BIKE PHOTO
# =========================================================

@app.route(
    "/delete_bike_image/<int:image_id>"
)
def delete_bike_image(
    image_id
):

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            bike_id,
            image_name
        FROM bike_images
        WHERE id = %s
        """,
        (image_id,)
    )


    image = cursor.fetchone()


    if image is None:

        cursor.close()
        conn.close()

        return "Image not found."


    bike_id = image[0]
    image_name = image[1]


    cursor.execute(
        """
        DELETE FROM bike_images
        WHERE id = %s
        """,
        (image_id,)
    )

    conn.commit()


    cursor.close()
    conn.close()


    # -----------------------------------------------------
    # DELETE ACTUAL FILE
    # -----------------------------------------------------

    result = find_image_file(
        image_name
    )


    if result:

        try:

            os.remove(
                os.path.join(
                    result[0],
                    result[1]
                )
            )

        except OSError:
            pass


    return redirect(
        url_for(
            "admin_bike_images",
            bike_id=bike_id
        )
    )


# =========================================================
# CUSTOMER DOUBTS
# =========================================================

@app.route(
    "/ask_doubt",
    methods=[
        "GET",
        "POST"
    ]
)
def ask_doubt():

    if "user_id" not in session:

        return redirect(
            url_for(
                "login"
            )
        )


    error = None


    if request.method == "POST":

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        question = request.form.get(
            "question",
            ""
        ).strip()


        if not subject:

            error = (
                "Please enter a subject."
            )

        elif not question:

            error = (
                "Please enter your question."
            )

        elif len(subject) > 150:

            error = (
                "Subject should not be "
                "more than 150 characters."
            )

        else:

            conn = get_db_connection()
            cursor = conn.cursor()


            cursor.execute(
                """
                INSERT INTO customer_doubts
                (
                    user_id,
                    subject,
                    question,
                    status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    'Pending'
                )
                """,
                (
                    session[
                        "user_id"
                    ],
                    subject,
                    question
                )
            )


            conn.commit()

            cursor.close()
            conn.close()


            return redirect(
                url_for(
                    "my_doubts"
                )
            )


    return render_template(
        "ask_doubt.html",
        error=error
    )


# =========================================================
# MY DOUBTS
# =========================================================

@app.route(
    "/my_doubts"
)
def my_doubts():

    if "user_id" not in session:

        return redirect(
            url_for(
                "login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            subject,
            question,
            admin_reply,
            status,
            created_at,
            replied_at
        FROM customer_doubts
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (
            session[
                "user_id"
            ],
        )
    )


    doubts = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "my_doubts.html",
        doubts=doubts
    )


# =========================================================
# ADMIN DOUBTS
# =========================================================

@app.route(
    "/admin_doubts",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_doubts():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    if request.method == "POST":

        doubt_id = request.form.get(
            "doubt_id",
            ""
        )

        reply = request.form.get(
            "reply",
            ""
        ).strip()


        if doubt_id and reply:

            cursor.execute(
                """
                UPDATE customer_doubts
                SET
                    admin_reply = %s,
                    status = 'Answered',
                    replied_at =
                        CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    reply,
                    doubt_id
                )
            )

            conn.commit()


    cursor.execute(
        """
        SELECT
            d.id,
            u.name,
            u.mobile,
            u.email,
            d.subject,
            d.question,
            d.admin_reply,
            d.status,
            d.created_at,
            d.replied_at
        FROM customer_doubts d
        JOIN users u
        ON d.user_id = u.id
        ORDER BY
            CASE
                WHEN d.status = 'Pending'
                THEN 0
                ELSE 1
            END,
            d.id DESC
        """
    )


    doubts = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "admin_doubts.html",
        doubts=doubts
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin_login",
    methods=[
        "GET",
        "POST"
    ]
)
def admin_login():

    if request.method == "POST":

        username = request.form[
            "username"
        ]

        password = request.form[
            "password"
        ]


        conn = get_db_connection()
        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT
                id,
                username
            FROM admin
            WHERE username = %s
            AND password = %s
            """,
            (
                username,
                password
            )
        )


        admin = cursor.fetchone()

        cursor.close()
        conn.close()


        if admin:

            session[
                "admin_id"
            ] = admin[0]

            session[
                "admin_username"
            ] = admin[1]


            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )


        return (
            "Invalid admin username "
            "or password."
        )


    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    "/admin_dashboard"
)
def admin_dashboard():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    return render_template(
        "admin_dashboard.html"
    )


# =========================================================
# ADMIN MANAGE BIKES
# =========================================================

@app.route(
    "/admin_bikes"
)
def admin_bikes():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            brand,
            model,
            cc,
            price,
            mileage,
            power,
            torque,
            fuel_capacity,
            availability,
            vehicle_type
        FROM bikes
        ORDER BY id DESC
        """
    )


    bikes_data = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "admin_bikes.html",
        bikes=bikes_data
    )


# =========================================================
# ADMIN ADD BIKE
# =========================================================

@app.route(
    "/add_bike",
    methods=[
        "GET",
        "POST"
    ]
)
def add_bike():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    if request.method == "POST":

        brand = request.form[
            "brand"
        ]

        model = request.form[
            "model"
        ]

        cc = request.form[
            "cc"
        ]

        price = request.form[
            "price"
        ]

        mileage = request.form[
            "mileage"
        ]

        power = request.form[
            "power"
        ]

        torque = request.form[
            "torque"
        ]

        fuel_capacity = request.form[
            "fuel_capacity"
        ]

        availability = request.form[
            "availability"
        ]

        vehicle_type = request.form[
            "vehicle_type"
        ]


        conn = get_db_connection()
        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT
                COALESCE(
                    MAX(id),
                    0
                ) + 1
            FROM bikes
            """
        )


        next_id = cursor.fetchone()[0]


        cursor.execute(
            """
            INSERT INTO bikes
            (
                id,
                brand,
                model,
                cc,
                price,
                mileage,
                power,
                torque,
                fuel_capacity,
                availability,
                vehicle_type
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                next_id,
                brand,
                model,
                cc,
                price,
                mileage,
                power,
                torque,
                fuel_capacity,
                availability,
                vehicle_type
            )
        )


        conn.commit()

        cursor.close()
        conn.close()


        return redirect(
            url_for(
                "admin_bikes"
            )
        )


    return render_template(
        "add_bike.html"
    )


# =========================================================
# ADMIN EDIT BIKE
# =========================================================

@app.route(
    "/edit_bike/<int:bike_id>",
    methods=[
        "GET",
        "POST"
    ]
)
def edit_bike(
    bike_id
):

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    if request.method == "POST":

        brand = request.form[
            "brand"
        ]

        model = request.form[
            "model"
        ]

        cc = request.form[
            "cc"
        ]

        price = request.form[
            "price"
        ]

        mileage = request.form[
            "mileage"
        ]

        power = request.form[
            "power"
        ]

        torque = request.form[
            "torque"
        ]

        fuel_capacity = request.form[
            "fuel_capacity"
        ]

        availability = request.form[
            "availability"
        ]

        vehicle_type = request.form[
            "vehicle_type"
        ]


        cursor.execute(
            """
            UPDATE bikes
            SET
                brand = %s,
                model = %s,
                cc = %s,
                price = %s,
                mileage = %s,
                power = %s,
                torque = %s,
                fuel_capacity = %s,
                availability = %s,
                vehicle_type = %s
            WHERE id = %s
            """,
            (
                brand,
                model,
                cc,
                price,
                mileage,
                power,
                torque,
                fuel_capacity,
                availability,
                vehicle_type,
                bike_id
            )
        )


        conn.commit()

        cursor.close()
        conn.close()


        return redirect(
            url_for(
                "admin_bikes"
            )
        )


    cursor.execute(
        """
        SELECT *
        FROM bikes
        WHERE id = %s
        """,
        (bike_id,)
    )


    bike = cursor.fetchone()

    cursor.close()
    conn.close()


    if bike is None:

        return "Bike not found."


    return render_template(
        "edit_bike.html",
        bike=bike
    )


# =========================================================
# ADMIN DELETE BIKE
# =========================================================

@app.route(
    "/delete_bike/<int:bike_id>"
)
def delete_bike(
    bike_id
):

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    # Delete photos from database first
    cursor.execute(
        """
        SELECT
            image_name
        FROM bike_images
        WHERE bike_id = %s
        """,
        (bike_id,)
    )

    images = cursor.fetchall()


    cursor.execute(
        """
        DELETE FROM bike_images
        WHERE bike_id = %s
        """,
        (bike_id,)
    )


    cursor.execute(
        """
        DELETE FROM bikes
        WHERE id = %s
        """,
        (bike_id,)
    )


    conn.commit()

    cursor.close()
    conn.close()


    # Delete actual image files

    for image in images:

        result = find_image_file(
            image[0]
        )

        if result:

            try:

                os.remove(
                    os.path.join(
                        result[0],
                        result[1]
                    )
                )

            except OSError:
                pass


    return redirect(
        url_for(
            "admin_bikes"
        )
    )


# =========================================================
# ADMIN USERS
# =========================================================

@app.route(
    "/admin_users"
)
def admin_users():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            name,
            mobile,
            email
        FROM users
        ORDER BY id DESC
        """
    )


    users = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "admin_users.html",
        users=users
    )


# =========================================================
# ADMIN DATABASE
# =========================================================

@app.route(
    "/admin_database"
)
def admin_database():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin_login"
            )
        )


    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            brand,
            model,
            cc,
            price,
            mileage,
            power,
            torque,
            fuel_capacity,
            availability,
            vehicle_type
        FROM bikes
        ORDER BY id
        """
    )


    bikes_data = cursor.fetchall()

    cursor.close()
    conn.close()


    return render_template(
        "admin_database.html",
        bikes=bikes_data
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route(
    "/admin_logout"
)
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_username",
        None
    )


    return redirect(
        url_for(
            "admin_login"
        )
    )


# =========================================================
# USER LOGOUT
# =========================================================

@app.route(
    "/logout"
)
def logout():

    session.clear()


    return redirect(
        url_for(
            "home"
        )
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )