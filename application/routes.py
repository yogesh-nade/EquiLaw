from application import app
from flask import render_template, request, redirect, flash, url_for , jsonify
import requests
from bson import ObjectId
import json
from .forms import RegisterForm, LoginForm , QueryForm , ReplyForm
from application import db
from datetime import datetime
from werkzeug.security import generate_password_hash ,check_password_hash
from PyPDF2 import PdfReader


NEWS_API_KEY = ""
OPENROUTER_API_KEY = ""


@app.route("/")
def index():
   
    return render_template("index.html")


@app.route("/register", methods=['POST', 'GET'])
def register():
    if request.method == "POST":
        form = RegisterForm(request.form)
        username = form.username.data
        email = form.email.data
        password = form.password.data
        hashed_password = generate_password_hash(password)

        result=db.users.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "date_registered": datetime.utcnow()
        })

        user_id = str(result.inserted_id)  # Get the inserted MongoDB ID

        flash("Registration successful", "success")
        return redirect(url_for("home", id=user_id))
    else:
        form = RegisterForm()
    return render_template("register.html", form=form)


@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        form = LoginForm(request.form)
        email = form.email.data
        password = form.password.data

        user = db.users.find_one({"email": email})
        if user and check_password_hash(user["password"], password):
            user_id = str(user["_id"])  # Convert MongoDB ID to string
            flash("Login successful", "success")
            return redirect(url_for("home", id=user_id))  # Redirect with user ID
        else:
            flash("Invalid email or password", "danger")
    else:
         form = LoginForm()
    return render_template("login.html",form=form)



@app.route('/profile/<id>')
def profile(id):
    # Render user profile page
    user_details = db.users.find_one({"_id": ObjectId(id)})
    return render_template('profile.html', user=user_details)


@app.route('/logout')
def logout():
    # Perform logout action
    flash("Logged out succesfully", "success")
    return render_template('index.html')



@app.route("/home/<id>")
def home(id):
    latest_news = []
    # for item in db.news.find().sort("date_published", -1):
    #     item["_id"] = str(item["_id"])  # Convert MongoDB ID to string
    #     latest_news.append(item)
    url = f"https://newsapi.org/v2/everything?q=legal+india&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    news_data = response.json()

    if news_data["status"] == "ok":
        articles = news_data["articles"]  # Extract articles
    else:
        articles = []

    user_details = db.users.find_one({"_id": ObjectId(id)})  # Fetch user details

    return render_template("home.html", news=articles, user=user_details)

    

@app.route("/community/<id>")
def community(id):
    # Fetch Queries
    user_queries = db.queries.find({"questioner_id": id})  # User's queries
    other_queries = db.queries.find({"questioner_id": {"$ne": id}})  # Other users' queries

    user_details = db.users.find_one({"_id": ObjectId(id)})
    return render_template("community.html", user_queries=user_queries, other_queries=other_queries,user=user_details)


@app.route("/nearby_lawyer/<id>")
def nearby_lawyer(id):
    
    user_details = db.users.find_one({"_id": ObjectId(id)})
    # Fetch all lawyers from the collection
    lawyers_detail = list(db.lawyers.find({}))
    
   # Get unique domains and cities for dropdowns
    domains = sorted(set(lawyer["domain"] for lawyer in lawyers_detail))
    cities = sorted(set(lawyer["city_of_practice"] for lawyer in lawyers_detail))
    
    # Convert lawyers_detail to JSON-serializable format
    lawyers_json = json.dumps(lawyers_detail, default=str)
    
    return render_template("nearby_lawyer.html", user=user_details, lawyers=lawyers_json, domains=domains, cities=cities)




@app.route("/post_query/<id>", methods=['POST', 'GET'])
def post_query(id):
    form = QueryForm()
    
    if request.method == "POST" and form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        domain = form.domain.data

        db.queries.insert_one({  
            "questioner_id": id,
            "title": title,
            "description": description,
            "domain": domain,
            "date_posted": datetime.utcnow(),
            "replies": []  # Empty list to store future replies
        })

        flash("Query posted successfully", "success")
        return redirect(url_for("community", id=id))
    
    return render_template("post_query.html", form=form)



@app.route("/reply/<query_id>/<id>", methods=["GET", "POST"])
def reply(query_id,id):
    query = db.queries.find_one({"_id": ObjectId(query_id)})
    if not query:
        flash("Query not found!", "danger")
        return redirect(url_for('community', id=id))

    form = ReplyForm()
    replyer = db.users.find_one({"_id": ObjectId(id)})
    username = replyer.get("username", "Unknown User")  

    if form.validate_on_submit():
        reply_data = {
            "replyer": username, 
            "text": form.reply_text.data,
            "timestamp": datetime.utcnow() 
        }
        db.queries.update_one({"_id": ObjectId(query_id)}, {"$push": {"replies": reply_data}})
        flash("Reply posted successfully!", "success")
        return redirect(url_for('community', id=id))

    return render_template("reply.html", form=form, query=query)















# AI assistance 
@app.route('/AI_assistance/<id>')
def AI_assistance(id):
    user_details = db.users.find_one({"_id": ObjectId(id)})
    return render_template('AI_assistance.html',user=user_details)

@app.route('/chat', methods=['POST'])
def chat():
    # Get the user's message from the request
    user_message = request.json['message']

    # Prepare the payload for the OpenRouter API
    payload = {
        "model": "",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_message
                    }
                ]
            }
        ]
    }

    # Send the request to the OpenRouter API
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",  # Optional
                "X-Title": "Flask Chat App"  # Optional
            },
            data=json.dumps(payload)
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            # Extract the response from OpenRouter
            openrouter_response = response.json()
            chat_response = openrouter_response['choices'][0]['message']['content']
            return jsonify({'response': chat_response})
        else:
            # Handle errors
            return jsonify({'error': f"OpenRouter API error: {response.status_code} - {response.text}"}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500




# pdf chat 
# Store uploaded PDF text
uploaded_text = ""

@app.route('/document_assistance/<id>')
def document_assistance(id):
    user_details = db.users.find_one({"_id": ObjectId(id)})
    return render_template('document_assistance.html',user=user_details)

@app.route('/upload', methods=['POST'])
def upload_pdf():
    global uploaded_text
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and file.filename.endswith('.pdf'):
        # Extract text from PDF
        reader = PdfReader(file)
        uploaded_text = ""
        for page in reader.pages:
            uploaded_text += page.extract_text()
        return jsonify({'message': 'PDF uploaded successfully'}), 200
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400

@app.route('/chat_with_document', methods=['POST'])
def document_chat():
    global uploaded_text
    user_message = request.json['message']

    if not uploaded_text:
        return jsonify({'error': 'No PDF uploaded. Please upload a PDF first.'}), 400

    # Combine user message with extracted PDF text
    prompt = f"The following text is extracted from a PDF:\n\n{uploaded_text}\n\nQuestion: {user_message}\nAnswer:"

    # Prepare the payload for the OpenRouter API
    payload = {
        "model": "",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    # Send the request to the OpenRouter API
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",  # Optional
                "X-Title": "Chat with PDF"  # Optional
            },
            data=json.dumps(payload)
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            # Extract the response from OpenRouter
            openrouter_response = response.json()
            chat_response = openrouter_response['choices'][0]['message']['content']
            return jsonify({'response': chat_response})
        else:
            # Handle errors
            return jsonify({'error': f"OpenRouter API error: {response.status_code} - {response.text}"}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500
