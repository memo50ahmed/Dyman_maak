from flask import Flask, render_template, render_template_string, request, jsonify, session, redirect, url_for
import os
import pandas as pd
from werkzeug.utils import secure_filename
import re
import json
import firebase_admin 
from firebase_admin import credentials,db
app = Flask(__name__)
app.secret_key = 'x!7R$ecretK3y2025'   
bank=False
# === إعداد Firebase ===
cred = credentials.Certificate("always-with-y-firebase-adminsdk-fbsvc-bd01d918b5.json")  # عدّل الاسم حسب ملفك
firebase_admin.initialize_app(cred, {
  'databaseURL': "https://always-with-y-default-rtdb.firebaseio.com"
})

@app.route('/place/<name>')
def show_place(name):
    try:
        # تطابق التنسيق مع المفتاح في قاعدة البيانات
        short_name = name.lower().replace(" ", "_")
        ref = db.reference(f'places/{short_name}')
        place_data = ref.get()

        if not place_data:
            return f"❌ المكان غير موجود: {short_name}", 404

        return render_template("place.html", place=place_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"🔥 حدث خطأ: {str(e)}", 500

# ========== عرض صفحة الأدمن ==========
@app.route('/admin/<name>')
def show_admin_place(name):
    try:
        # مهم: تحويل الاسم بنفس طريقة الإدخال إلى Firebase
        short_name = name.lower().replace(" ", "_")
        ref = db.reference(f'places/{short_name}')
        place_data = ref.get()

        if not place_data:
            return f"❌ المكان غير موجود: {short_name}", 404
        return render_template("admin_place.html", place=place_data, place_key=short_name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"🔥 حدث خطأ: {str(e)}", 500
       
@app.route("/")
def home():
    return render_template("index.html")

@app.route('/info')
def info():
    ref = db.reference('places')
    places_data = ref.get() 
    places = []
    for key, data in places_data.items():
        places.append((
            data["link_photo"],
        
            key,
            data["link_pa"],
            data["details_url"],
            data["description"]
        ))


    return render_template('info.html', place=places)

@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")



user_state = {
    "location": "",
    "lookingForHotel": False,
    "lookingForBank": False,
    "lookingForHospital": False,
    "lookingForSchool": False,
    "unknownQuestion": ""
}



@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_input = data.get("message", "")
    response, iframe = process_input(user_input)
    return jsonify({"response": response, "iframe": iframe})

def process_input(user_input):
    global user_state
    response = "❓ I'm not sure I understand that."
    iframe = ""

    def match(pattern): 
        return re.search(pattern, user_input, re.IGNORECASE)

    # === Match for general place types ===
    if match(r'\b(hospital|hotel|bank|school)s?\b'):
        found_type = match(r'\b(hospital|hotel|bank|school)s?\b').group(1)
        location = match(r'in\s+(.+)$').group(1) if match(r'in\s+(.+)$') else ""
        places = get_places_by_type(found_type)

        if places:
            if location:
                first_place = places[next(iter(places))]
                iframe = iframe_to_html(first_place.get("iframe_url", ""))
                response = f"🔍 Found {found_type}s in {location}:{iframe}"
            else:
                place_list = "\n".join([f"- {p['name_place']}" for p in places.values()])
                response = f"🔍 Found {found_type}s:\n{place_list}"
            user_state.update({
                "lookingFor": found_type,
                "location": location,
                "selected_place": None
            })
        else:
            if location:
                response = f"❌ No {found_type}s found in {location}."

    # === If user types a specific place name ===
    elif user_state.get("lookingFor"):
        place_name = user_input.strip().lower().replace(" ", "_")
        ref = db.reference(f'places/{place_name}')
        place = ref.get()
        if place and place.get("place_type", "").lower() == user_state["lookingFor"].lower():
            response = f"{place['name_place']}:\n📍 {place['description']}"
            iframe = iframe_to_html(place.get("iframe_url", ""))
            user_state["lookingFor"] = None
        else:
            response = f"❌ Couldn't find a {user_state['lookingFor']} named '{user_input}'."

    else:
        response = "🧠 Try asking about hospitals, hotels, banks, or schools — or name a place directly."

    return response, iframe

def get_places_by_type(place_type):
    ref = db.reference("places")
    all_places = ref.get() or {}
    return {
        key: val for key, val in all_places.items()
        if val.get("place_type", "").lower() == place_type.lower()
    }

def get_place_by_name(name):
    ref = db.reference("places")
    all_places = ref.get() or {}
    return all_places.get(name)

def get_place_by_location(location):
    ref = db.reference("places")
    all_places = ref.get() or {}
    return {
        key: val for key, val in all_places.items()
        if val.get("location", "").lower() == location.lower()
    }

def iframe_to_html(iframe_code):
    if not iframe_code:
        return ""
    return f"{iframe_code}"
@app.route('/map')
def map():
    ref = db.reference('places')
    places_data = ref.get() or {}

    landmarks = []
    for key, data in places_data.items():
        landmarks.append({
            "lat": (data.get("lat", 0)),
            "lng": (data.get("lng", 0)),
            "name_place": f'{data.get("name_place", "")}' ,
            "url": key,
            "size": 0.3  # ثابت أو يمكن تخصيصه
        })

    return render_template("map.html", landmarks=landmarks)





@app.route('/import_excel', methods=['GET', 'POST'])
def import_excel():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('excel_file')
        if not file:
            return render_template("upload_excel.html", error="No file selected.")

        filename = secure_filename(file.filename)
        file_path = os.path.join("uploads", filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(file_path)

        try:
            df = pd.read_excel(file_path)

            # Ensure necessary columns exist
            required_cols = {"Place Name", "Type", "Location", "Coordinates", "Notes"}
            if not required_cols.issubset(set(df.columns)):
                return render_template("upload_excel.html", error="Invalid column names in Excel file.")

            for _, row in df.iterrows():
                name = row['Place Name'].strip()
                place_type = row['Type'].strip()
                location = row['Location'].strip()
                coords = row['Coordinates'].split(",")
                lat = coords[0].strip()
                pic=row['Photo Link'].strip() 
                lng = coords[1].strip()
                notes = row['Notes'].strip()
                iframe_url = row['Iframe URL'].strip()
                short_name = name.lower().replace(" ", "_")
                ref = db.reference(f"places/{short_name}")
                ref.set({
                    "name_place": name,
                    "place_type": place_type,
                    "city": location,
                    "link_photo": pic,
                    "lat": lat,
                    "lng": lng,
                    "iframe_url": iframe_url,
                    "description": notes,
                    "iframe_url": "",
                    "link_pa": f"place/{short_name}",
                    "details_url": f"admin/{short_name}",
                })

            return render_template("upload_excel.html", error=None, success="Excel imported successfully!")

        except Exception as e:
            return render_template("upload_excel.html", error=f"Error: {str(e)}")

    return render_template("upload_excel.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == '000':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')
@app.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    ref = db.reference('places')
    places_data = ref.get() or {}
    places = []
    for key, data in places_data.items():
        places.append((
            data["link_photo"],
            key,
            data["link_pa"],
            data["details_url"],
            data["description"]
        ))
    return render_template("admin_dashboard.html", place=places)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/delete/<place_id>', methods=['POST'])
def delete_place(place_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        db.reference(f'/places/{place_id}').delete()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return f"Error deleting place: {e}", 500


# ========== صفحة إضافة مكان ==========
@app.route('/add', methods=['GET', 'POST'])
def add_place():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        lat = request.form.get('lat', '').strip()
        place_type = request.form.get('place_type', '').strip()
        iframe_raw = request.form.get('iframe_url', '').strip()
        lng = request.form.get('lng', '').strip()
        link_photo = request.form.get('link_photo', '').strip()
        name_place = request.form.get('name_place', '').strip()
        description = request.form.get('description', '').strip()
        city = request.form.get('city', '').strip()
        short_name = name_place.lower().replace(" ", "_")
        ref = db.reference(f"places/{short_name}")

        if ref.get() is not None:
            return render_template("add_place.html", error="❗المكان موجود مسبقًا.", place=request.form)

        # ✅ تحويل رابط Google Maps إلى iframe تلقائيًا
        if "google.com/maps" in iframe_raw:
            iframe_url = f'''
                <iframe src="{iframe_raw.replace(' ', '')}&output=embed"
                        width="600" height="450" style="border:0;" allowfullscreen=""
                        loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
            '''
        else:
            iframe_url = iframe_raw  # احتياطيًا لو المستخدم أدخل كود iframe مباشرة

        ref.set({
            "lat": lat,
            "place_type": place_type,
            "lng": lng,
            "link_photo": link_photo,
            "iframe_url": iframe_url,
            "name_place": name_place,
            "city": city,
            "link_pa": f"place/{short_name}",
            "details_url": f"admin/{short_name}",
            "description": description
        })

        return redirect(url_for('admin_dashboard'))

    return render_template("add_place.html")

@app.route('/generated/<filename>')
def generated_html(filename):
    try:
        return render_template(filename)
    except:
        return "Page not found", 404
    
@app.route('/update-place', methods=['POST']) 
def update_place():
    data = request.get_json()

    key = data.get('key')
    name = data.get('name_place', '').strip()
    description = data.get('description', '').strip()
    city = data.get('city', '').strip()
    link_photo = data.get('link_photo', '').strip()
    iframe_url = data.get('iframe_url', '').strip()
    place_type = data.get('place_type', '').strip()
    lat = data.get('lat', '').strip()
    lng = data.get('lng', '').strip()


    if not key or not name or not description or not link_photo:
        return jsonify({'error': '❌ Missing required fields'}), 400

    try:
        ref = db.reference('places').child(key)
        ref.update({
            'name_place': name,
            'description': description,
            'link_photo': link_photo,
            'city': city,
            'lat': lat,
            'lng': lng,
            'iframe_url': iframe_url,
            'place_type': place_type
        })

        return jsonify({'message': '✅ Place updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=8000, debug=True)
